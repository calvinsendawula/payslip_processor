from fastapi import FastAPI, File, UploadFile, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Dict, List
import json
import os
from tempfile import NamedTemporaryFile
import requests
from PIL import Image
from pdf2image import convert_from_bytes
import logging
import re

from . import models, schemas, database
from .database import engine, get_db

# At the top of the file, configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # This is your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def load_schema():
    try:
        # Update the path to be relative to the backend directory
        schema_path = os.path.join(os.path.dirname(__file__), '..', 'schema.json')
        with open(schema_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading schema: {str(e)}")
        return None

async def process_image_with_ollama(image_path: str, schema_type: str) -> dict:
    """Process a single image with Ollama's LLaVA model"""
    try:
        # Load the schema
        schema = load_schema()
        if not schema or schema_type not in schema:
            logger.error(f"Schema not found for type: {schema_type}")
            return None

        # Convert image to base64
        with open(image_path, "rb") as image_file:
            import base64
            image_data = base64.b64encode(image_file.read()).decode()

        # Update the prompt section
        prompt = f"""
        Analysiere diese deutsche Gehaltsabrechnung und extrahiere die folgenden Informationen.

        WICHTIG: Gib NUR ein JSON-Objekt zurück, das EXAKT diesem Format entspricht:
        {{
            "employee": {{
                "name": "Name des Mitarbeiters",
                "id": "12345"
            }},
            "payment": {{
                "gross": 1234.56,
                "net": 987.65,
                "deductions": 246.91
            }}
        }}

        Regeln:
        - Gib NUR das JSON zurück, KEINE Erklärungen oder Analysen
        - Zahlen müssen als reine Zahlen ohne Anführungszeichen erscheinen
        - Entferne alle Währungssymbole (€) von Zahlenwerten
        - Verwende Punkt statt Komma für Dezimalstellen
        - Die ID muss als String in Anführungszeichen stehen
        - Der Name muss als String in Anführungszeichen stehen
        - Keine zusätzlichen Felder wie "type" hinzufügen
        """

        logger.info("Calling Llama 3.2 Vision API...")
        response = requests.post('http://localhost:11434/api/generate',
            json={
                'model': 'llama3.2-vision',
                'prompt': prompt,
                'images': [image_data],
                'stream': False,
                'temperature': 0.1
            })
        
        if not response.ok:
            logger.error(f"Ollama API error: {response.status_code} - {response.text}")
            return None

        result = response.json()
        logger.info(f"Ollama response: {result['response']}")
        
        # Extract JSON from response - improved regex pattern
        json_match = re.search(r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}', result['response'], re.DOTALL)
        if not json_match:
            logger.error("No JSON found in response")
            return None
            
        json_str = json_match.group()
        logger.info(f"Extracted JSON: {json_str}")
        
        try:
            # Try to fix common JSON issues before parsing
            # 1. Fix numeric IDs without quotes
            json_str = re.sub(r'"id"\s*:\s*(\d+)', r'"id": "\1"', json_str)
            logger.info(f"Fixed JSON: {json_str}")
            
            extracted_data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            # Try to clean the JSON string
            json_str = re.sub(r',\s*}', '}', json_str)  # Remove trailing commas
            json_str = re.sub(r',\s*]', ']', json_str)  # Remove trailing commas in arrays
            
            # Try a more aggressive approach to fix the JSON
            try:
                # Use a regular expression to manually extract the values
                employee_name = re.search(r'"name"\s*:\s*"([^"]+)"', json_str)
                employee_id = re.search(r'"id"\s*:\s*(?:"([^"]+)"|(\d+))', json_str)
                payment_gross = re.search(r'"gross"\s*:\s*(\d+(?:\.\d+)?)', json_str)
                payment_net = re.search(r'"net"\s*:\s*(\d+(?:\.\d+)?)', json_str)
                payment_deductions = re.search(r'"deductions"\s*:\s*(\d+(?:\.\d+)?)', json_str)
                
                extracted_data = {
                    "employee": {
                        "name": employee_name.group(1) if employee_name else "unknown",
                        "id": employee_id.group(1) or employee_id.group(2) if employee_id else "unknown"
                    },
                    "payment": {
                        "gross": float(payment_gross.group(1)) if payment_gross else 0,
                        "net": float(payment_net.group(1)) if payment_net else 0,
                        "deductions": float(payment_deductions.group(1)) if payment_deductions else 0
                    }
                }
            except Exception as e2:
                logger.error(f"Failed to manually extract JSON: {e2}")
                return None
        
        # Ensure the extracted data matches the expected schema
        validated_data = {
            "employee": {
                "name": "unknown",
                "id": "unknown"
            },
            "payment": {
                "gross": 0,
                "net": 0,
                "deductions": 0
            }
        }

        try:
            # Remove the "type" field if it exists
            if "type" in extracted_data:
                del extracted_data["type"]

            # Validate employee data
            if "employee" in extracted_data:
                emp_data = extracted_data["employee"]
                validated_data["employee"]["name"] = emp_data.get("name", "unknown")
                # Clean up ID - remove extra quotes if present
                id_value = emp_data.get("id", "unknown")
                if isinstance(id_value, str):
                    id_value = id_value.replace('"', '')
                validated_data["employee"]["id"] = id_value

            # Validate payment data
            if "payment" in extracted_data:
                pay_data = extracted_data["payment"]
                try:
                    validated_data["payment"]["gross"] = float(pay_data.get("gross", 0))
                    validated_data["payment"]["net"] = float(pay_data.get("net", 0))
                    validated_data["payment"]["deductions"] = float(pay_data.get("deductions", 0))
                except (ValueError, TypeError) as e:
                    logger.error(f"Error converting payment values: {e}")

            # Verify we have at least some valid data
            if (validated_data["employee"]["name"] == "unknown" and 
                validated_data["employee"]["id"] == "unknown" and
                validated_data["payment"]["gross"] == 0 and
                validated_data["payment"]["net"] == 0):
                logger.error("No valid data found in extracted content")
                return None

            return validated_data

        except Exception as e:
            logger.error(f"Error validating extracted data: {e}")
            return None

    except Exception as e:
        logger.error(f"Error processing image with Ollama: {e}")
        return None

async def preprocess_image(image_path: str) -> str:
    """Preprocess the image for better OCR results"""
    try:
        # Check if the file is a PDF
        if image_path.lower().endswith('.pdf'):
            logger.info("Processing as PDF file...")
            # Convert PDF to image
            images = convert_from_bytes(open(image_path, 'rb').read())
            if not images:
                raise ValueError("Failed to convert PDF to images")
                
            # Save the first page as an image
            output_path = f"{os.path.splitext(image_path)[0]}_processed.jpg"
            images[0].save(output_path, 'JPEG')
            return output_path
        else:
            logger.info("Processing as image file...")
            # Process image file
            img = Image.open(image_path)
            output_path = f"{os.path.splitext(image_path)[0]}_processed.jpg"
            img.save(output_path, 'JPEG')
            return output_path
    except Exception as e:
        logger.error(f"Image preprocessing failed: {str(e)}")
        # If preprocessing fails, return the original path
        return image_path

async def extract_employee_info(image_path: str) -> dict:
    """Extract just employee information"""
    try:
        # Convert image to base64
        with open(image_path, "rb") as image_file:
            import base64
            image_data = base64.b64encode(image_file.read()).decode()

        prompt = """
        Look at the Employee Information section at the top of this payslip.
        
        Your ONLY task is to find and copy:
        1. The exact full name that appears after "Name:"
        2. The exact ID number that appears after "Employee ID:"
        
        Return ONLY a JSON object in this format:
        {
            "name": "the exact name you found",
            "id": "the exact ID you found"
        }
        """

        logger.info("Calling Ollama API for employee info...")
        response = requests.post('http://localhost:11434/api/generate',
            json={
                'model': 'llama3.2-vision',
                'prompt': prompt,
                'images': [image_data],
                'stream': False,
                'temperature': 0.1
            })
        
        if not response.ok:
            logger.error(f"Ollama API error: {response.status_code} - {response.text}")
            return None

        result = response.json()
        logger.info(f"Employee info response: {result['response']}")
        
        json_match = re.search(r'\{.*\}', result['response'], re.DOTALL)
        if not json_match:
            logger.error("No JSON found in employee info response")
            return None
            
        employee_data = json.loads(json_match.group())
        if not isinstance(employee_data.get("name"), str) or not isinstance(employee_data.get("id"), str):
            logger.error(f"Invalid employee data format: {employee_data}")
            return None
            
        return employee_data

    except Exception as e:
        logger.error(f"Error extracting employee info: {e}")
        return None

async def extract_payment_info(image_path: str) -> dict:
    """Extract just payment information"""
    try:
        # Convert image to base64
        with open(image_path, "rb") as image_file:
            import base64
            image_data = base64.b64encode(image_file.read()).decode()

        prompt = """
        Look ONLY at the Summary section at the bottom of this payslip.
        
        Find these three specific numbers:
        1. The exact amount after "Gross Pay: $"
        2. The exact amount after "Total Deductions: $"
        3. The exact amount after "Net Pay: $"
        
        Return ONLY a JSON object in this format:
        {
            "gross": number_without_dollar_sign,
            "net": number_without_dollar_sign,
            "deductions": number_without_dollar_sign
        }

        Example format (but use the real numbers you find):
        {
            "gross": 4000.00,
            "net": 2500.00,
            "deductions": 1500.00
        }
        """

        logger.info("Calling Ollama API for payment info...")
        response = requests.post('http://localhost:11434/api/generate',
            json={
                'model': 'llama3.2-vision',
                'prompt': prompt,
                'images': [image_data],
                'stream': False,
                'temperature': 0.1
            })
        
        if not response.ok:
            logger.error(f"Ollama API error: {response.status_code} - {response.text}")
            return None

        result = response.json()
        logger.info(f"Payment info response: {result['response']}")
        
        json_match = re.search(r'\{.*\}', result['response'], re.DOTALL)
        if not json_match:
            logger.error("No JSON found in payment info response")
            return None
            
        payment_data = json.loads(json_match.group())
        
        # Convert strings to floats if needed
        for key in ["gross", "net", "deductions"]:
            if isinstance(payment_data.get(key), str):
                payment_data[key] = float(payment_data[key].replace(',', ''))
            
        return payment_data

    except Exception as e:
        logger.error(f"Error extracting payment info: {e}")
        return None

def validate_payment_data(data: dict) -> bool:
    """Validate payment data for consistency"""
    try:
        gross = float(data["gross"])
        net = float(data["net"])
        deductions = float(data["deductions"])
        
        # Basic range checks
        if any(amount <= 0 for amount in [gross, net, deductions]):
            logger.error("Found negative or zero amount")
            return False
            
        # Mathematical consistency
        if abs((gross - deductions) - net) > 0.01:
            logger.error("Payment amounts don't add up")
            return False
            
        # Reasonable range checks
        if gross > 50000 or net > 50000 or deductions > 50000:
            logger.error("Amounts outside reasonable range")
            return False
            
        return True
    except Exception as e:
        logger.error(f"Payment validation failed: {e}")
        return False

async def validate_employee_info(employee_data: dict, db: Session) -> dict:
    """Validate extracted employee information against database records"""
    try:
        # First try to find employee by ID
        employee = None
        if employee_data.get('id') and employee_data['id'] != "unknown":
            # Clean up the ID - remove "SV-Schlüssel:" prefix if present
            id_value = employee_data['id']
            if "SV-Schlüssel:" in id_value:
                id_value = id_value.replace("SV-Schlüssel:", "").strip()
            
            # Extract just the first part if the ID contains spaces
            id_parts = id_value.split()
            employee_id = id_parts[0] if id_parts else id_value
            
            employee = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
        
        # If not found by ID, try to find by exact name
        if not employee and employee_data.get('name') and employee_data['name'] != "unknown":
            # Clean up the name - remove "Frau" or "Herr" prefix if present
            name = employee_data['name']
            if name.startswith("Frau "):
                name = name[5:].strip()
            elif name.startswith("Herr "):
                name = name[5:].strip()
                
            employee = db.query(models.Employee).filter(models.Employee.name == name).first()
            
            # If still not found, try more flexible name matching (case insensitive, partial match)
            if not employee:
                # Try with case insensitive match
                employee = db.query(models.Employee).filter(
                    models.Employee.name.ilike(f"%{name}%")
                ).first()
                
                # Also try with reversed name (in case of "Last, First" vs "First Last" format)
                if not employee and ',' in name:
                    parts = name.split(',')
                    reversed_name = f"{parts[1].strip()} {parts[0].strip()}"
                    employee = db.query(models.Employee).filter(
                        models.Employee.name.ilike(f"%{reversed_name}%")
                    ).first()
                
                # Try with reversed name format (in case of "First Last" vs "Last, First")
                if not employee and ' ' in name:
                    parts = name.split(' ', 1)
                    reversed_name = f"{parts[1].strip()}, {parts[0].strip()}"
                    employee = db.query(models.Employee).filter(
                        models.Employee.name.ilike(f"%{reversed_name}%")
                    ).first()
            
        if not employee:
            logger.warning(f"No matching employee found for {employee_data}")
            return {
                "name": {
                    "extracted": employee_data.get('name', 'unknown'),
                    "stored": "unknown",
                    "matches": False
                },
                "id": {
                    "extracted": employee_data.get('id', 'unknown'),
                    "stored": "unknown",
                    "matches": False
                }
            }
        
        # Validate employee information
        return {
            "name": {
                "extracted": employee_data.get('name', ''),
                "stored": employee.name,
                "matches": True  # Set to true if we found a match in the database
            },
            "id": {
                "extracted": employee_data.get('id', ''),
                "stored": employee.id,
                "matches": True  # Set to true if we found a match in the database
            }
        }
    except Exception as e:
        logger.error(f"Error validating employee info: {e}")
        return {
            "name": {"extracted": "error", "stored": "error", "matches": False},
            "id": {"extracted": "error", "stored": "error", "matches": False}
        }

@app.post("/api/process-payslip")
async def process_payslip(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Process a payslip file and compare with expected values"""
    pages = []
    try:
        logger.info(f"Processing payslip: {file.filename} ({file.content_type})")
        
        # Read file content
        content = await file.read()
        
        # Process PDF or image
        if file.content_type == "application/pdf":
            logger.info("Processing as PDF file...")
            try:
                # Convert PDF to images
                pdf_images = convert_from_bytes(content)
                for i, image in enumerate(pdf_images):
                    temp_path = f"temp_page_{i+1}.jpg"
                    image.save(temp_path, "JPEG")
                    pages.append(temp_path)
            except Exception as e:
                logger.error(f"PDF conversion error: {str(e)}")
                raise HTTPException(status_code=400, detail="Failed to process PDF file")
        else:
            logger.info("Processing as image file...")
            temp_path = f"temp_{file.filename}"
            with open(temp_path, "wb") as f:
                f.write(content)
            pages = [temp_path]

        # Process each page
        all_comparisons = []
        for page_idx, page_path in enumerate(pages):
            try:
                logging.info(f"Attempting to extract data from page {page_idx + 1}")
                preprocessed_path = await preprocess_image(page_path)
                
                # Extract data using schema
                extracted_data = await process_image_with_ollama(preprocessed_path, "payslip")
                
                if not extracted_data:
                    logger.warning(f"No data extracted from page {page_idx + 1}")
                    continue
                
                # Validate employee information
                employee_validation = await validate_employee_info(extracted_data["employee"], db)
                
                # If we found a matching employee, validate payment information
                if employee_validation["name"]["matches"] or employee_validation["id"]["matches"]:
                    employee = None
                    
                    # Get the employee record - improved logic to handle different ID formats
                    if employee_validation["id"]["matches"]:
                        # Clean up the ID for lookup
                        extracted_id = extracted_data["employee"]["id"]
                        if isinstance(extracted_id, str):
                            if extracted_id.startswith("SV-"):
                                extracted_id = extracted_id[3:]
                        
                            # Try to find by exact ID
                            employee = db.query(models.Employee).filter(
                                models.Employee.id == extracted_id
                            ).first()
                        
                            # If not found, try with case-insensitive search
                            if not employee:
                                employee = db.query(models.Employee).filter(
                                    models.Employee.id.ilike(f"%{extracted_id}%")
                                ).first()
                    
                    # If still not found, try by name
                    if not employee and employee_validation["name"]["matches"]:
                        extracted_name = extracted_data["employee"]["name"]
                        
                        # Clean up the name
                        if extracted_name.startswith("Frau "):
                            extracted_name = extracted_name[5:].strip()
                        elif extracted_name.startswith("Herr "):
                            extracted_name = extracted_name[5:].strip()
                        
                        # Try to find by exact name
                        employee = db.query(models.Employee).filter(
                            models.Employee.name == extracted_name
                        ).first()
                        
                        # If not found, try with case-insensitive search
                        if not employee:
                            employee = db.query(models.Employee).filter(
                                models.Employee.name.ilike(f"%{extracted_name}%")
                            ).first()
                    
                    # Log the employee we found
                    if employee:
                        logger.info(f"Found matching employee: {employee.id} - {employee.name}")
                    else:
                        logger.warning("Employee found during validation but not when retrieving record")
                    
                    # Validate payment information
                    payment_validation = {
                        "gross": {
                            "extracted": extracted_data["payment"]["gross"],
                            "stored": employee.expected_gross,
                            "matches": False
                        },
                        "net": {
                            "extracted": extracted_data["payment"]["net"],
                            "stored": employee.expected_net,
                            "matches": False
                        },
                        "deductions": {
                            "extracted": extracted_data["payment"]["deductions"],
                            "stored": employee.expected_deductions,
                            "matches": False
                        }
                    }
                    
                    # Check if values match (with some tolerance for floating point)
                    try:
                        if extracted_data["payment"]["gross"] != "unknown":
                            payment_validation["gross"]["matches"] = abs(
                                float(extracted_data["payment"]["gross"]) - employee.expected_gross
                            ) < 0.01
                            
                        if extracted_data["payment"]["net"] != "unknown":
                            payment_validation["net"]["matches"] = abs(
                                float(extracted_data["payment"]["net"]) - employee.expected_net
                            ) < 0.01
                            
                        if extracted_data["payment"]["deductions"] != "unknown":
                            payment_validation["deductions"]["matches"] = abs(
                                float(extracted_data["payment"]["deductions"]) - employee.expected_deductions
                            ) < 0.01
                    except (ValueError, TypeError) as e:
                        logger.error(f"Error comparing payment values: {e}")
                    
                    # Add to results
                    comparison = {
                        "page": page_idx + 1,
                        "employee": employee_validation,
                        "payment": payment_validation
                    }
                    all_comparisons.append(comparison)
                else:
                    logger.warning("No matching employee found in database")
            except Exception as e:
                logger.error(f"Error processing page {page_idx + 1}: {str(e)}")
            finally:
                # Cleanup temporary file
                if os.path.exists(page_path):
                    try:
                        os.unlink(page_path)
                    except Exception as e:
                        logger.error(f"Failed to cleanup temp file {page_path}: {str(e)}")
                if os.path.exists(preprocessed_path):
                    try:
                        os.unlink(preprocessed_path)
                    except Exception as e:
                        logger.error(f"Failed to cleanup temp file {preprocessed_path}: {str(e)}")

        if not all_comparisons:
            raise HTTPException(status_code=404, detail="Keine gültigen Gehaltsabrechnungsdaten gefunden")

        return {"pages": all_comparisons, "total_pages": len(pages)}

    except Exception as e:
        logger.error(f"Unexpected error in process_payslip: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup temporary files
        for page_path in pages:
            if os.path.exists(page_path):
                try:
                    os.unlink(page_path)
                except Exception as e:
                    logger.error(f"Failed to cleanup temp file {page_path}: {str(e)}")

@app.post("/api/process-property")
async def process_property(
    file: UploadFile = File(...)
):
    try:
        logger.info(f"Processing property listing: {file.filename} ({file.content_type})")
        
        # Read file content
        content = await file.read()
        temp_path = f"temp_{file.filename}"
        
        try:
            # Save the file temporarily
            with open(temp_path, "wb") as f:
                f.write(content)
            
            # Preprocess the image
            preprocessed_path = await preprocess_image(temp_path)
            
            # Extract property information using Ollama
            property_data = await extract_property_info(preprocessed_path)
            
            if not property_data:
                raise HTTPException(status_code=404, detail="No property data found")
                
            return property_data
            
        finally:
            # Clean up temporary files
            for path in [temp_path, preprocessed_path]:
                if os.path.exists(path):
                    try:
                        os.unlink(path)
                    except Exception as e:
                        logger.error(f"Failed to cleanup temp file {path}: {str(e)}")
                        
    except Exception as e:
        logger.error(f"Unexpected error in process_property: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def extract_property_info(image_path: str) -> dict:
    """Extract property information from an image"""
    try:
        # Convert image to base64
        with open(image_path, "rb") as image_file:
            import base64
            image_data = base64.b64encode(image_file.read()).decode()

        # Prepare the prompt
        prompt = """
        Analysiere dieses Immobilienangebot. Du musst folgende spezifische Informationen finden und extrahieren:

        1. Die Wohnfläche (in Quadratmetern, m²)
        2. Den Kaufpreis (in Euro, €)

        Gib die extrahierten Werte in dieser JSON-Struktur zurück:
        {
            "living_space": "<exakter Text für die Wohnfläche, inklusive Einheit>",
            "purchase_price": "<exakter Text für den Kaufpreis, inklusive Währungssymbol>"
        }

        Regeln:
        - Extrahiere die Werte EXAKT wie sie erscheinen
        - Gib nur die JSON-Struktur zurück
        - Wenn du einen Wert nicht klar lesen kannst, gib "unklar" zurück
        - Erfinde oder rate keine Werte
        """

        logger.info("Calling Llama 3.2 Vision API for property info...")
        response = requests.post('http://localhost:11434/api/generate',
            json={
                'model': 'llama3.2-vision',
                'prompt': prompt,
                'images': [image_data],
                'stream': False,
                'temperature': 0.1
            })
        
        if not response.ok:
            logger.error(f"Ollama API error: {response.status_code} - {response.text}")
            return None

        result = response.json()
        logger.info(f"Property info response: {result['response']}")
        
        json_match = re.search(r'\{.*\}', result['response'], re.DOTALL)
        if not json_match:
            logger.error("No JSON found in property info response")
            return None
            
        property_data = json.loads(json_match.group())
        return property_data

    except Exception as e:
        logger.error(f"Error extracting property info: {e}")
        return None

# Update the path to the settings file
def load_ai_settings():
    try:
        # Change from 'aisettings' to 'aisettings.json'
        with open('aisettings.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading AI settings: {str(e)}")
        return {
            "model": "llama3.2-vision",
            "temperature": 0.1,
            "max_tokens": 1000,
            "prompts": {
                "payslip": {"text": "Default payslip prompt"},
                "property": {"text": "Default property prompt"}
            }
        } 