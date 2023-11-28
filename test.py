import os

from database import SessionLocal
import models

def table_insert():
    db = SessionLocal()
    images = os.listdir('./images')
    for image in images:
        with open(f'images/{image}', 'rb') as file:
            file_byte = file.read()
            emp = models.Employee(img_binary=file_byte)
            db.add(emp)
            db.commit()
            
table_insert()