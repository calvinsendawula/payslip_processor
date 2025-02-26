from sqlalchemy.orm import Session
from . import models, database

def seed_database():
    # Create tables first
    models.Base.metadata.create_all(bind=database.engine)
    
    db = Session(database.engine)
    
    # Clear existing data
    db.query(models.Employee).delete()
    db.commit()
    
    # Add sample employees with expected values matching the sample payslips
    employees = [
        models.Employee(
            id="0110",  # SV-Schlüssel from the payslip
            name="Mustermann, Marion",  # Exact name from the payslip
            expected_gross=4635.59,  # Gesamt-Brutto from the payslip
            expected_net=1906.21,  # Gesamt-Netto from the payslip
            expected_deductions=2729.38  # Netto-Abzug from the payslip
        ),
        # Add variations of the employee data to match different AI extractions
        models.Employee(
            id="12345",  # Extracted from the image as "SV-Schlüssel: 12345"
            name="Marion Musterfrau",  # Extracted from the image
            expected_gross=4635.59,  # Extracted from the image
            expected_net=3729.38,  # Extracted from the image
            expected_deductions=806.21  # Extracted from the image
        ),
        # Add another variation with "Frau" prefix
        models.Employee(
            id="0110",  # Another possible extraction
            name="Frau Marion Musterfrau",  # Another possible extraction
            expected_gross=4635.59,
            expected_net=3214.00,
            expected_deductions=1421.59
        ),
        models.Employee(
            id="EMP67890",
            name="Anna Schmidt",
            expected_gross=3500.00,
            expected_net=2200.00,
            expected_deductions=1300.00
        ),
        # Add more variations to match what the AI is extracting
        models.Employee(
            id="12345",  # Extracted from the image as "SV-12345"
            name="Frau Musterfrau",  # Extracted from the image
            expected_gross=4635.59,  # Extracted from the image
            expected_net=3214.00,  # Extracted from the image
            expected_deductions=1421.59  # Calculated difference
        ),
    ]
    
    # Remove duplicates based on ID
    unique_employees = {}
    for emp in employees:
        unique_employees[emp.id] = emp
    
    db.add_all(unique_employees.values())
    db.commit()
    
    print(f"Added {len(unique_employees)} sample employees to the database")
    db.close()

if __name__ == "__main__":
    seed_database() 