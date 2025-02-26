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
            name="Frau Musterfrau",  # Exact name from the payslip
            expected_gross=3214.00,  # Actual Brutto from the payslip
            expected_net=2000.00,    # Intentionally wrong net amount
            expected_deductions=1214.00  # Adjusted for the discrepancy
        ),
        # Add variations of the employee data to match different AI extractions
        models.Employee(
            id="12345",  # Alternative ID format
            name="Marion Musterfrau",  # Alternative name format
            expected_gross=3214.00,  # Same values as they should match
            expected_net=2000.00,    # Same intentionally wrong net amount
            expected_deductions=1214.00  # Adjusted for the discrepancy
        ),
        # This variation demonstrates fraud detection - intentionally wrong net amount
        models.Employee(
            id="55566",  # Another possible ID format
            name="Frau Marion Musterfrau",  # Another name variation
            expected_gross=3214.00,  # Correct gross amount
            expected_net=2000.00,    # Intentionally wrong net amount
            expected_deductions=1214.00  # Adjusted for the discrepancy
        )
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