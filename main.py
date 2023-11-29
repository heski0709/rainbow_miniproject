import io
import uuid
import cv2
import uvicorn
import numpy as np
from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from models import Attendance, Employee, Base
from typing import Optional
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

Base.metadata.create_all(bind=engine)

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

def get_feats(bytes_list: list[bytes]):
    """
    이미지 바이너리 목록을 받아 각 이미지의 얼굴 특징 벡터를 계산합니다.
    
    Args:
        bytes_list (list[bytes]): 이미지 바이너리 목록

    Returns:
        List[np.ndarray]: 이미지에서 추출된 얼굴 특징 벡터 목록
    """
    bytes_io_list = createBytesIo(bytes_list)
    open_images = BytesIoImageOpen(bytes_io_list)
    cv_images = [cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR) for image in open_images]
    faces = [module.get(image) for image in cv_images]
    feats = [face[0].normed_embedding for face in faces]
    
    return feats

def init(db: Session = next(get_db())):
    """
    초기화 함수입니다. 데이터베이스로부터 이미지를 가져와 얼굴 특징 벡터를 계산하고 feats 변수에 캐싱합니다.
    
    Args:
        db (Session, optional): 데이터베이스 세션 객체. Defaults to next(get_db()).

    Returns:
        None
    """
    global feats
    cols = db.query(Employee)
    img_binarys = [col.img_binary for col in cols]
    feats = get_feats(img_binarys)

@app.get('/', summary="인덱스 페이지")
def index(request: Request, ads: Optional[str] = Cookie(None)):
    """
    인덱스 페이지를 반환합니다. 'ads' 쿠키가 있는 경우 '/main?q={ads}'로 리디렉션됩니다.
    
    Args:
        request (Request): FastAPI의 Request 객체
        ads (Optional[str], optional): 'ads' 쿠키. Defaults to Cookie(None).

    Returns:
        Union[RedirectResponse, TemplateResponse]: 리디렉션 또는 템플릿 응답
    """
    if ads is not None:
        return RedirectResponse(f'/main?q={ads}')
    
    return templates.TemplateResponse('index.html', {'request': request})
    
@app.get('/main', summary="메인 페이지")
async def main(request: Request, q: uuid.UUID = Query(None), db: Session = Depends(get_db)):
    """
    메인 페이지를 반환하거나 요청된 출결 ID에 해당하는 정보를 데이터베이스에서 가져오고 정보가 없을 경우 에러를 띄웁니다.
    정보가 존재한다면 'ads' 쿠키에 출결 ID를 담아 set-cookie 응답을 보냅니다.

    Args:
        request (Request): FastAPI의 Request 객체
        q (uuid.UUID, optional): 출결 ID. Defaults to Query(None).
        db (Session, optional): 데이터베이스 세션 객체. Defaults to Depends(get_db).

    Returns:
        Union[Dict[str, Union[str, int]], TemplateResponse]: 에러 또는 템플릿 응답
    """
    
    query = db.query(Attendance).filter(Attendance.id == q).first()
    
    if query is None:
        return {'error': 'error', 'statusCode': BAD_REQUEST}
    
    # 출근한 시간에서 하루가 지나면 만료되도록 설정
    expire = query.start + timedelta(days=1)
    response = templates.TemplateResponse('main.html', {'request': request, 'query': query})
    response.set_cookie(key='ads', value=q, expires=expire.astimezone(timezone.utc), httponly=True)
    return response

@app.get('/video', response_class=HTMLResponse, summary="얼굴인식 로그인 페이지")
async def videoLogin(request: Request):
    """
    얼굴인식 로그인 페이지를 반환합니다.

    Args:
        request (Request): FastAPI의 Request 객체

    Returns:
        Union[RedirectResponse, TemplateResponse]: 리디렉션 또는 템플릿 응답
    """
    return templates.TemplateResponse('video.html', {'request': request})

@app.get('/register', summary="회원등록 페이지")
async def register(request: Request):
    """
    회원등록 페이지를 반환합니다.

    Args:
        request (Request): FastAPI의 Request 객체

    Returns:
        Union[RedirectResponse, TemplateResponse]: 리디렉션 또는 템플릿 응답
    """
    return templates.TemplateResponse('register.html', {'request': request})
    
@app.post('/register', status_code=CREATED, summary="회원등록 정보 추가")
async def register(file: UploadFile = File(None), name: str = Form(...), phone: str = Form(...), db: Session = Depends(get_db)):
    """
    회원등록 정보를 받아 데이터베이스에 추가하고, 이미지 파일을 처리하여 얼굴 특징 벡터를 계산합니다.

    Args:
        file (UploadFile, optional): 업로드된 이미지 파일. Defaults to File(None).
        name (str): 이름
        phone (str): 전화번호
        db (Session, optional): 데이터베이스 세션 객체. Defaults to Depends(get_db).

    Returns:
        Union[JSONResponse, RedirectResponse]: 에러 또는 리디렉션 응답
    """
    
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
    
    employee = Employee(name=name, phone=phone, img_binary=read_file)
    
    db.add(employee)
    db.commit()
    
    global feats
    feat = get_feats([read_file])
    feats += feat
    
    for item in feats:
        print(item)
    
    return RedirectResponse("/", status_code=302)

@app.get('/leave', summary='퇴근')
async def leave(request: Request, ads: Optional[str] = Cookie(None), db: Session = Depends(get_db)):

    """
    사용자의 퇴근을 처리하고, 'ads' 쿠키를 삭제합니다.

    Args:
        request (Request): FastAPI의 Request 객체
        ads (Optional[str], optional): 광고 쿠키. Defaults to Cookie(None).
        db (Session, optional): 데이터베이스 세션 객체. Defaults to Depends(get_db).

    Returns:
        Union[Dict[str, Union[str, int]], TemplateResponse]: 에러 또는 템플릿 응답
    """
    query = db.query(Attendance).filter(Attendance.id == uuid.UUID(ads)).filter(Attendance.end == None).first()
    
    if query is None:
        return {'error': 'error', 'statusCode': BAD_REQUEST}
    
    query.end = datetime.now()
    db.commit()
    
    response = templates.TemplateResponse('index.html', {'request': request})
    response.delete_cookie('ads')
    return response
    
@app.websocket('/ws', name="웹소켓 연결")
async def websocket_endpoint(websocket: WebSocket, db: Session = Depends(get_db)):
    """
    웹소켓 연결을 처리하고, 이미지를 분석하여 출석을 기록합니다.

    Args:
        websocket (WebSocket): FastAPI의 WebSocket 객체
        db (Session, optional): 데이터베이스 세션 객체. Defaults to Depends(get_db).

    Returns:
        None
    """
    await websocket.accept()
    today = datetime.now().date()
    try:
        while True:
            data = await websocket.receive_bytes()
            
            buffer = io.BytesIO(data)
            image = Image.open(buffer)
            cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            face = module.get(cv_image)

            # # 데이터 처리 로직
            if (len(face) != 1):
                continue

            global feats
            sims = np.dot(feats, np.array(face[0].normed_embedding, dtype=np.float32))
            
            for index, sim in enumerate(sims):
                if sim > 0.55:
                    employee = db.query(Employee).all()
                    attendance = db.query(Attendance).filter(Attendance.employee_id == employee[index].id).filter(func.date(Attendance.start) == today).first()

                    if attendance == None:
                        attendance = Attendance(id = uuid.uuid4(), employee_id=employee[index].id)
                        db.add(attendance)
                        db.commit()
            
                    await websocket.send_json({
                            'data': f'{employee[index].name}님 확인되셨습니다.', 
                            'start': attendance.start.strftime("%Y-%m-%d %H:%M:%S"), 
                            'statusCode': OK,
                            'url': f'/main?q={attendance.id}'
                    })
    except Exception as e:
        print(f"WebSocket Error: {e}")

init()

if __name__ == "__main__":
    uvicorn.run(app=app, port=8000)
