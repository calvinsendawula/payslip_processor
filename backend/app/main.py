from fastapi import FastAPI, File, UploadFile, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
import json
import os
import logging
import re

from . import models, schemas, database
from .database import engine, get_db
from .qwen_processor import get_qwen_processor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load schema for validation
def load_schema():
    try:
        # Use os.path for cross-platform compatibility
        schema_path = os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'schema.json'))
        with open(schema_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading schema: {str(e)}")
        return None

@app.get("/")
def read_root():
    return {"message": "Payslip Processor API is running"}

@app.post("/api/extract-payslip")
async def extract_payslip(file: UploadFile = File(...)):
    """
    Extract information from a payslip without validation.
    Returns the extracted employee name, gross amount, and net amount.
    """
    try:
        # Get the file content
        content = await file.read()
        
        # Get file extension to determine processing method
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        # Process file based on file type
        processor = get_qwen_processor()
        
        if file_ext in ['.pdf']:
            result = processor.process_pdf_file(content)
        elif file_ext in ['.jpg', '.jpeg', '.png']:
            result = processor.process_image_file(content)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format. Please upload a PDF or image file.")
        
        if not result:
            raise HTTPException(status_code=404, detail="No valid data could be extracted from the document.")
        
        # Return the extracted data
        return {
            "employee": {
                "name": result["employee"]["name"]
            },
            "payment": {
                "gross": result["payment"]["gross"],
                "net": result["payment"]["net"]
            },
            "raw_output": result["raw_output"]
        }
    
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@app.post("/api/validate-payslip-by-id")
async def validate_payslip_by_id(data: dict, db: Session = Depends(get_db)):
    """
    Validate extracted payslip data against a specific employee ID.
    Returns whether the extracted data matches the expected values in the database.
    """
    try:
        # Extract data from request
        employee_id = data.get("employeeId")
        extracted_data = data.get("extractedData")
        
        if not employee_id or not extracted_data:
            raise HTTPException(status_code=400, detail="Missing employee ID or extracted data")
        
        # Look up the employee in the database
        employee = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
        
        if not employee:
            return {
                "employeeFound": False,
                "message": f"No employee found with ID {employee_id}"
            }
        
        # Get the extracted values
        extracted_name = extracted_data.get("employee", {}).get("name", "")
        
        # Clean the amounts (remove currency symbols and convert to float)
        extracted_gross = extracted_data.get("payment", {}).get("gross", "0")
        extracted_net = extracted_data.get("payment", {}).get("net", "0")
        
        # Clean up amounts - remove currency symbol and convert German format to float
        def clean_amount(amount_str):
            if isinstance(amount_str, (int, float)):
                return float(amount_str)
            
            # Remove currency symbol and whitespace
            cleaned = re.sub(r'[€\s]', '', amount_str)
            # Replace German decimal comma with dot
            cleaned = cleaned.replace(',', '.')
            # Try to convert to float
            try:
                return float(cleaned)
            except ValueError:
                return 0.0
        
        extracted_gross_float = clean_amount(extracted_gross)
        extracted_net_float = clean_amount(extracted_net)
        
        # Validate the extracted data against the database record
        name_matches = employee.name.lower() == extracted_name.lower()
        
        # Allow for a small difference in amounts due to formatting/rounding
        def values_match(val1, val2, tolerance=0.01):
            return abs(val1 - val2) <= tolerance
        
        gross_matches = values_match(employee.expected_gross, extracted_gross_float)
        net_matches = values_match(employee.expected_net, extracted_net_float)
        
        # Format the response
        validation_result = {
            "employeeFound": True,
            "validation": {
                "name": {
                    "matches": name_matches,
                    "expected": employee.name
                },
                "gross": {
                    "matches": gross_matches,
                    "expected": '{:.2f}'.format(employee.expected_gross)
                },
                "net": {
                    "matches": net_matches,
                    "expected": '{:.2f}'.format(employee.expected_net)
                }
            },
            "message": "Validation completed"
        }
        
        return validation_result
    
    except Exception as e:
        logger.error(f"Error validating payslip: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error validating payslip: {str(e)}")

@app.post("/api/process-property")
async def process_property(file: UploadFile = File(...)):
    """
    Process property listing files using the sliding window approach.
    Extracts living space and purchase price information.
    """
    try:
        # Get the file content
        content = await file.read()
        
        # Get file extension to determine processing method
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        # Process file
        processor = get_qwen_processor()
        
        if file_ext in ['.pdf']:
            # Extract data from the PDF
            images = processor.convert_pdf_to_images(content)
            if not images:
                raise HTTPException(status_code=404, detail="No pages found in PDF")
            
            # Use the first page
            image = images[0]
        elif file_ext in ['.jpg', '.jpeg', '.png']:
            # Process as image
            from PIL import Image
            import io
            image = Image.open(io.BytesIO(content))
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format. Please upload a PDF or image file.")
        
        # Process property listing with a custom prompt for property information
        windows = processor.split_image_for_sliding_window(image)
        extracted_info = {
            "living_space": "nicht gefunden",
            "purchase_price": "nicht gefunden",
            "raw_output": ""
        }
        
        # Process each window looking for property information
        for i, window in enumerate(windows):
            position = "top" if i == 0 else "bottom"
            
            # Customize the prompt based on position
            if position == "top":
                prompt = """Du siehst ein deutsches Immobilienangebot (oberer Teil).
                
                SUCHE PRÄZISE NACH:
                Wohnfläche (meist mit Einheit "m²" angegeben).
                
                SCHAUE HIER: In einer Tabelle oder Liste mit Immobiliendetails. Suche nach einer Zeile mit "Wohnfläche".
                
                FORMAT: Die Wohnfläche wird meist als Zahl mit "m²" oder "qm" angegeben, manchmal mit "ca." davor.
                
                Gib deinen Fund als JSON zurück:
                {
                "property_top": {
                    "living_space": "gefundene Wohnfläche mit Einheit oder 'nicht gefunden'",
                    "purchase_price": "nicht gefunden"
                }
                }"""
            else:
                prompt = """Du siehst ein deutsches Immobilienangebot (unterer Teil).
                
                SUCHE PRÄZISE NACH:
                Kaufpreis (meist mit "€" oder "EUR" angegeben).
                
                SCHAUE HIER: In einer Tabelle oder Liste mit Immobiliendetails. Suche nach einer Zeile mit "Kaufpreis" oder "Preis".
                
                FORMAT: Der Kaufpreis wird meist als Zahl mit Tausenderpunkten und Komma für Dezimalstellen angegeben, gefolgt vom Euro-Symbol.
                
                Gib deinen Fund als JSON zurück:
                {
                "property_bottom": {
                    "living_space": "nicht gefunden",
                    "purchase_price": "gefundener Kaufpreis mit Währungssymbol oder 'nicht gefunden'"
                }
                }"""
            
            # Process window using progressive resolution approach
            try:
                # Override the default prompt
                window_data = processor._process_window_with_custom_prompt(window, position, prompt)
                extracted_info["raw_output"] += f"\n--- {position.upper()} WINDOW EXTRACTION ---\n"
                extracted_info["raw_output"] += json.dumps(window_data, indent=2)
                
                # Extract property data
                window_key = f"property_{position}"
                if window_key in window_data:
                    property_data = window_data[window_key]
                    
                    if "living_space" in property_data and property_data["living_space"] != "nicht gefunden":
                        # Clean up and standardize living space format
                        living_space = property_data["living_space"]
                        # Extract just the value and unit if there's extra text
                        living_space_match = re.search(r'ca\.\s*(\d+(?:,\d+)?)\s*m(?:²|2)', living_space, re.IGNORECASE)
                        if not living_space_match:
                            living_space_match = re.search(r'(\d+(?:,\d+)?)\s*m(?:²|2)', living_space, re.IGNORECASE)
                        
                        if living_space_match:
                            extracted_info["living_space"] = f"ca. {living_space_match.group(1)} m²"
                        else:
                            extracted_info["living_space"] = living_space
                    
                    if "purchase_price" in property_data and property_data["purchase_price"] != "nicht gefunden":
                        # Clean up and standardize purchase price format
                        purchase_price = property_data["purchase_price"]
                        # Extract just the value and currency if there's extra text
                        price_match = re.search(r'(\d+(?:\.\d+)*(?:,\d+)?)\s*(?:€|EUR)', purchase_price, re.IGNORECASE)
                        
                        if price_match:
                            price_value = price_match.group(1)
                            # Ensure correct German number format with thousands separator
                            if '.' in price_value and ',' in price_value:
                                # Already has both thousand and decimal separators
                                extracted_info["purchase_price"] = f"{price_value} €"
                            elif '.' in price_value:
                                # Convert from international to German format if needed
                                parts = price_value.split('.')
                                if len(parts[-1]) == 2:  # Looks like international format
                                    price_value = price_value.replace('.', 'X').replace(',', '.').replace('X', ',')
                                extracted_info["purchase_price"] = f"{price_value} €"
                            else:
                                # Just add the Euro symbol if missing
                                extracted_info["purchase_price"] = f"{price_value} €"
                        else:
                            extracted_info["purchase_price"] = purchase_price
            except Exception as e:
                logger.error(f"Error processing {position} window: {str(e)}")
        
        # Check schema validation
        schema = load_schema()
        if schema and "property" in schema:
            # Just check required fields are present
            required_fields = schema["property"].get("required", [])
            for field in required_fields:
                if extracted_info.get(field) == "nicht gefunden":
                    logger.warning(f"Required field '{field}' not found in property listing")
        
        return extracted_info
    
    except Exception as e:
        logger.error(f"Error processing property listing: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing property listing: {str(e)}")

@app.on_event("shutdown")
def shutdown_event():
    """Release resources on server shutdown"""
    try:
        processor = get_qwen_processor()
        processor.unload_model()
        logger.info("Unloaded model resources on shutdown")
    except Exception as e:
        logger.error(f"Error unloading model: {str(e)}") 