from http.client import BAD_REQUEST, OK
import io
from json import JSONEncoder
import uuid
import cv2
import uvicorn
import models
import numpy as np
from PIL import Image
from insightface.app import FaceAnalysis
from fastapi import Depends, FastAPI, Query, Request, Response, UploadFile, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from utils import BytesIoImageOpen, createBytesIo

models.Base.metadata.create_all(bind=engine)

module = FaceAnalysis(allowed_modules=['detection', 'recognition'],providers=['CPUExecutionProvider'])
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

@app.get('/')
def read_item(request: Request):
    
    return templates.TemplateResponse('index.html', {'request': request})

@app.post('/image')
async def facialAnalysis(file: UploadFile, db: Session = Depends(get_db)):
    global feats
    
    content = await file.read()
    buffer = io.BytesIO(content)
    image = Image.open(buffer)
    cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    face = module.get(cv_image)
    
    if (len(face) > 1 or len(face) == 0):
        return Response(
            JSONEncoder().encode({'statusCode': BAD_REQUEST}), 
            status_code=BAD_REQUEST, media_type='application/json')
    
    sims = np.dot(feats, np.array(face[0].normed_embedding, dtype=np.float32))
    
    for sim in sims:
        if sim > 0.7:
            print('동일인 입니다.')
            attendance = models.Attendance(id = uuid.uuid4())
            db.add(attendance)
            db.commit()
            
            return {'result': 'success', 
                    'start': attendance.start, 
                    'statusCode': OK,
                    'url': f'/main?q={attendance.id}'}
        
    return Response(
                JSONEncoder().encode({'statusCode': BAD_REQUEST}), 
                status_code=BAD_REQUEST, media_type='application/json')

@app.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket, db: Session = Depends(get_db)):
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_bytes()
            buffer = io.BytesIO(data)
            image = Image.open(buffer)
            cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            face = module.get(cv_image)
            # print(face)

            # # 데이터 처리 로직
            if (len(face) > 1 or len(face) == 0):
                continue
            
            sims = np.dot(feats, np.array(face[0].normed_embedding, dtype=np.float32))
            
            for sim in sims:
                if sim > 0.7:
                    print('동일인 입니다.')
                    attendance = models.Attendance(id = uuid.uuid4())
                    db.add(attendance)
                    db.commit()
            
                    await websocket.send_json(data={
                            'result': 'success', 
                            'start': attendance.start.strftime("%Y-%m-%d %H:%M:%S"), 
                            'statusCode': OK,
                            'url': f'/main?q={attendance.id}'
                    })
    except Exception as e:
        print(f"WebSocket Error: {e}")
    # finally:
    #     # 연결 종료 시 처리
    #     await websocket.close()

@app.get('/main')
async def main(request: Request, q: uuid.UUID = Query(None), db: Session = Depends(get_db)):
    query = db.query(models.Attendance).filter(models.Attendance.id == q).first()
    
    if query is None:
        return {'error': 'error', 'statusCode': BAD_REQUEST}
    
    return templates.TemplateResponse('main.html', {'request': request})
    
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
