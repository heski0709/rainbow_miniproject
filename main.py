import datetime
import io
from typing import Optional
import uuid
import cv2
import uvicorn
import models
import numpy as np
from http.client import BAD_REQUEST, CREATED, OK
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from PIL import Image
from insightface.app import FaceAnalysis
from fastapi import Cookie, Depends, FastAPI, File, Form, Query, Request, UploadFile, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from utils import BytesIoImageOpen, createBytesIo

models.Base.metadata.create_all(bind=engine)

module = FaceAnalysis(allowed_modules=['detection', 'recognition'],providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
module.prepare(ctx_id=0, det_size=(640, 640))

app = FastAPI()
app.mount('/static', StaticFiles(directory='static'), name='static')

templates = Jinja2Templates(directory='templates')
feats = None

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        # 마지막에 무조건 닫음
        db.close()

class Main:
    @app.get('/')
    def index(request: Request, ads: Optional[str] = Cookie(None)):

        if ads is not None:
            return RedirectResponse(f'/main?q={ads}')
        
        return templates.TemplateResponse('index.html', {'request': request})
        
    @app.get('/main')
    async def main(request: Request, q: uuid.UUID = Query(None), db: Session = Depends(get_db)):
        query = db.query(models.Attendance).filter(models.Attendance.id == q).first()
        
        if query is None:
            return {'error': 'error', 'statusCode': BAD_REQUEST}
        
        response = templates.TemplateResponse('main.html', {'request': request})
        response.set_cookie('ads', q, 43200, httponly=True)
        return response
    
    @app.get('/video', response_class=HTMLResponse)
    async def videoLogin(request: Request):
        return templates.TemplateResponse('video.html', {'request': request})
    
    @app.get('/register', response_class=HTMLResponse)
    async def register(request: Request):
         return templates.TemplateResponse('register.html', {'request': request})
        
    @app.post('/register', status_code=CREATED)
    async def register(file: UploadFile = File(None), name: str = Form(...), phone: str = Form(...), db: Session = Depends(get_db)):
        global feats
        
        if name is None or phone is None or file is None:
            return JSONResponse(status_code=BAD_REQUEST, content={'error': '입력 값이 정상적이지 않습니다.'})
        
        content_type = file.content_type

        if content_type == 'image/png':
            contents = await file.read()
            nparr = np.frombuffer(contents, np.uint8)
            
            # OpenCV를 사용하여 이미지 읽기
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            # JPEG로 변환 (quality를 조정하여 압축 수준 설정 가능)
            _, encoded_image = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 90])

            read_file = encoded_image.tobytes()

        else:    
            read_file = await file.read()
        
        employee = models.Employee(name=name, phone=phone, img_binary=read_file)
        
        db.add(employee)
        db.commit()
        
        global feats
        bytes_io_list = createBytesIo([read_file])
        open_images = BytesIoImageOpen(bytes_io_list)
        cv_images = [cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR) for image in open_images]
        faces = [module.get(image) for image in cv_images]
        feat = [face[0].normed_embedding for face in faces]
        feats += feat
        
        for item in feats:
            print(item)
        
        return RedirectResponse("/", status_code=302)
    
    @app.get('/leave')
    async def leave(request: Request, ads: Optional[str] = Cookie(None)):

        query = db.query(models.Attendance).filter(models.Attendance.id == uuid.UUID(ads)).filter(models.Attendance.end == None).first()
        
        if query is None:
            return {'error': 'error', 'statusCode': BAD_REQUEST}
        
        query.end = datetime.datetime.now()
        db.commit()
        
        response = templates.TemplateResponse('index.html', {'request': request})
        response.delete_cookie('ads')
        
        return response
        
    @app.websocket('/ws')
    async def websocket_endpoint(websocket: WebSocket, db: Session = Depends(get_db)):
        global feats
        await websocket.accept()

        try:
            while True:
                data = await websocket.receive_bytes()
                
                buffer = io.BytesIO(data)
                image = Image.open(buffer)
                cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                face = module.get(cv_image)

                print(len(face))
                # # 데이터 처리 로직
                if (len(face) > 1 or len(face) == 0):
                    continue
                
                sims = np.dot(feats, np.array(face[0].normed_embedding, dtype=np.float32))
                
                for index, sim in enumerate(sims):
                    print(sim)
                    if sim > 0.65:
                        employee = db.query(models.Employee)
                        attendance = models.Attendance(id = uuid.uuid4(), employee_id=employee[index].id)
                        db.add(attendance)
                        db.commit()
                
                        await websocket.send_json(data={
                                'data': f'{employee[index].name}님 확인되셨습니다.', 
                                'start': attendance.start.strftime("%Y-%m-%d %H:%M:%S"), 
                                'statusCode': OK,
                                'url': f'/main?q={attendance.id}'
                        })
        except Exception as e:
            print(f"WebSocket Error: {e}")

if __name__ == "__main__":
    db = SessionLocal()
    cols = db.query(models.Employee)
    img_binarys = [col.img_binary for col in cols]
    bytes_io_list = createBytesIo(img_binarys)
    open_images = BytesIoImageOpen(bytes_io_list)
    cv_images = [cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR) for image in open_images]
    faces = [module.get(image) for image in cv_images]
    feats = [face[0].normed_embedding for face in faces]
    
    uvicorn.run(app=app, port=8000)
