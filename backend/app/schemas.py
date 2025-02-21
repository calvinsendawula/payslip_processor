from pydantic import BaseModel

class PayslipSchema(BaseModel):
    """Schema for payslip data extraction"""
    employee: dict = {
        "name": "str",
        "id": "str"
    }
    payment: dict = {
        "gross": 0,
        "net": 0,
        "deductions": 0
    }

class EmployeeRecord(BaseModel):
    """Database model for employee records"""
    id: str
    name: str
    expected_gross: float
    expected_net: float
    expected_deductions: float 