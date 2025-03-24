from sqlalchemy.orm import Session
from . import models, database

def seed_database():
    # Create tables first
    models.Base.metadata.create_all(bind=database.engine)
    
    db = Session(database.engine)
    
    # Clear existing data
    db.query(models.Employee).delete()
    db.commit()
    
    # Add sample employees with expected values
    employees = [
        # Genuine employee that would match the actual extracted data from the payslip
        models.Employee(
            id="EMP001",  # Made up ID for genuine employee
            name="Erika Mustermann",  # Name that should match the extracted data
            expected_gross=2124.00,  # Gross amount that should match extracted data
            expected_net=1374.78,    # Net amount that should match extracted data
            expected_deductions=749.22  # Calculated deductions
        ),
        # Fake employee 1
        models.Employee(
            id="EMP002",
            name="Hans Mueller",
            expected_gross=3500.00,
            expected_net=2200.50,
            expected_deductions=1299.50
        ),
        # Fake employee 2
        models.Employee(
            id="EMP003",
            name="Michael Schmidt",
            expected_gross=4200.00,
            expected_net=2650.75,
            expected_deductions=1549.25
        ),
        # Fake employee 3
        models.Employee(
            id="EMP004",
            name="Anna Klein",
            expected_gross=3100.00,
            expected_net=1980.25,
            expected_deductions=1119.75
        ),
        # Fake employee 4
        models.Employee(
            id="EMP005",
            name="Maria Weber",
            expected_gross=2800.00,
            expected_net=1820.30,
            expected_deductions=979.70
        )
    ]
    
    db.add_all(employees)
    db.commit()
    
    print(f"Added {len(employees)} sample employees to the database")
    db.close()

if __name__ == "__main__":
    seed_database() 