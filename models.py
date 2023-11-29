from datetime import datetime
from sqlalchemy import BLOB, VARCHAR, Column, DateTime, ForeignKey, Integer, LargeBinary, String, Uuid

from database import Base


class Attendance(Base):
    __tablename__ = 'attendance'
    id = Column(Uuid, primary_key=True, autoincrement=None)
    employee_id = Column(Integer, ForeignKey("employee.id"))
    start = Column(DateTime, default=datetime.now)
    end = Column(DateTime, default=None)

class Employee(Base):
    __tablename__ = 'employee'
    id = Column(Integer, primary_key=True)
    name = Column(VARCHAR)
    phone = Column(VARCHAR)
    img_binary = Column(LargeBinary)
