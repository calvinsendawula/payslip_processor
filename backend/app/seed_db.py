from sqlalchemy.orm import Session
from app.database import engine, Base
from app.models import Employee

# Create tables
Base.metadata.create_all(bind=engine)

# Create a test employee
test_employee = Employee(
    id="EMP456",
    name="Jane Smith",
    expected_gross=6000.00,
    expected_net=4500.00,
    expected_deductions=1500.00
)

# Add to database
with Session(engine) as session:
    # Clear existing data
    session.query(Employee).delete()
    # Add new test data
    session.add(test_employee)
    session.commit()

print("Test data added to database!") 