from sqlalchemy import Column, String, Float
from .database import Base

class Employee(Base):
    __tablename__ = "employees"

    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    expected_gross = Column(Float)
    expected_net = Column(Float)
    expected_deductions = Column(Float) 