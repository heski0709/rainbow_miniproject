from datetime import datetime
from sqlalchemy import VARCHAR, Column, DateTime, Integer, LargeBinary, String, Uuid

from database import Base


class Attendance(Base):
    __tablename__ = 'attendance'
    id = Column(Uuid, primary_key=True, autoincrement=None)
    start = Column(DateTime, default=datetime.now)
    end = Column(DateTime, default=None)

class Employee(Base):
    __tablename__ = 'employee'
    id = Column(Integer, primary_key=True)
    name = Column(VARCHAR)
    phone = Column(VARCHAR)
    img_binary = Column(LargeBinary)
