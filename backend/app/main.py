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
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def process_image_with_ollama(image_path: str, schema: dict) -> dict:
    """Process a single image with Ollama's LLaVA model"""
    try:
        # Convert image to base64
        with open(image_path, "rb") as image_file:
            import base64
            image_data = base64.b64encode(image_file.read()).decode()

        # Prepare the prompt
        prompt = """
        Analyze this payslip image. You must find and extract specific text fields.

        Step 1: In the Employee Information section at the top:
        - Locate the text that appears immediately after "Name:"
        - Locate the text that appears immediately after "Employee ID:"

        Step 2: In the Summary section at the bottom of the payslip:
        - Find the exact number after "Gross Pay:" (ignore the $ symbol)
        - Find the exact number after "Total Deductions:" (ignore the $ symbol)
        - Find the exact number after "Net Pay:" (ignore the $ symbol)

        Return the extracted values in this JSON structure:
        {
            "employee": {
                "name": "<exact text found after Name:>",
                "id": "<exact text found after Employee ID:>"
            },
            "payment": {
                "gross": <number from Gross Pay>,
                "net": <number from Net Pay>,
                "deductions": <number from Total Deductions>
            }
        }

        Rules:
        - Extract values EXACTLY as they appear
        - For amounts: remove $ and , symbols and return as numbers
        - Return only the JSON structure
        - If you cannot read a value clearly, return "unclear"
        - Do not invent or guess any values
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
            raise HTTPException(status_code=500, detail="Failed to process image with Ollama")

        result = response.json()
        logger.info(f"Ollama raw response: {result['response']}")
        
        # Extract JSON from the response text
        json_match = re.search(r'\{.*\}', result['response'], re.DOTALL)
        if not json_match:
            logger.error("No JSON found in Ollama response")
            raise ValueError("No JSON found in response")
            
        extracted_json = json.loads(json_match.group())
        
        # Validate extracted data
        if (
            not isinstance(extracted_json.get("employee", {}).get("id"), str) or
            not isinstance(extracted_json.get("payment", {}).get("gross"), (int, float)) or
            not isinstance(extracted_json.get("payment", {}).get("net"), (int, float)) or
            not isinstance(extracted_json.get("payment", {}).get("deductions"), (int, float))
        ):
            logger.error(f"Invalid data types in extracted JSON: {extracted_json}")
            raise ValueError("Extracted data has invalid format")
            
        logger.info(f"Parsed JSON: {extracted_json}")
        return extracted_json

    except requests.exceptions.ConnectionError:
        logger.error("Failed to connect to Ollama API - is it running?")
        raise HTTPException(status_code=500, detail="Failed to connect to Ollama service")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from response: {e}")
        raise HTTPException(status_code=500, detail="Invalid response format from Ollama")
    except Exception as e:
        logger.error(f"Unexpected error in process_image_with_ollama: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def preprocess_image(image_path: str) -> str:
    """Enhance image for better text extraction"""
    try:
        with Image.open(image_path) as img:
            # Convert to grayscale
            img = img.convert('L')
            
            # Increase contrast
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(2.0)  # Increase contrast
            
            # Resize if too large (maintain aspect ratio)
            max_size = 1024
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                img = img.resize((int(img.size[0] * ratio), int(img.size[1] * ratio)))
            
            # Save preprocessed image
            preprocessed_path = f"{image_path}_processed.jpg"
            img.save(preprocessed_path, quality=95)
            return preprocessed_path
    except Exception as e:
        logger.error(f"Image preprocessing failed: {e}")
        return image_path  # Return original if preprocessing fails

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

@app.post("/api/process-payslip")
async def process_payslip(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Processing file: {file.filename} ({file.content_type})")
        
        # Read file content
        content = await file.read()
        pages = []

        # Handle PDF or image
        if file.content_type == "application/pdf":
            logger.info("Converting PDF to images...")
            try:
                pdf_images = convert_from_bytes(content)
                for i, image in enumerate(pdf_images):
                    temp_path = f"temp_page_{i}.jpg"
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
                logging.info("Attempting to extract data from page %s", page_idx + 1)
                preprocessed_path = await preprocess_image(page_path)
                
                # Extract information in steps
                employee_data = await extract_employee_info(preprocessed_path)
                if not employee_data:
                    continue
                    
                # Only proceed to payment extraction if we found valid employee
                employee = db.query(models.Employee).filter(
                    models.Employee.id == employee_data["id"]
                ).first()
                
                if not employee:
                    continue
                    
                payment_data = await extract_payment_info(preprocessed_path)
                
                # Validate the extracted data
                if not validate_payment_data(payment_data):
                    continue
                
                # Combine the results
                extracted_data = {
                    "employee": employee_data,
                    "payment": payment_data
                }
                
                # Compare extracted data with database records
                comparison = {
                    "page": page_idx + 1,
                    "employee": {
                        "name": {
                            "extracted": extracted_data["employee"]["name"],
                            "stored": employee.name,
                            "matches": extracted_data["employee"]["name"] == employee.name
                        },
                        "id": {
                            "extracted": extracted_data["employee"]["id"],
                            "stored": employee.id,
                            "matches": extracted_data["employee"]["id"] == employee.id
                        }
                    },
                    "payment": {
                        "gross": {
                            "extracted": extracted_data["payment"]["gross"],
                            "stored": employee.expected_gross,
                            "matches": abs(float(extracted_data["payment"]["gross"]) - employee.expected_gross) < 0.01
                        },
                        "net": {
                            "extracted": extracted_data["payment"]["net"],
                            "stored": employee.expected_net,
                            "matches": abs(float(extracted_data["payment"]["net"]) - employee.expected_net) < 0.01
                        },
                        "deductions": {
                            "extracted": extracted_data["payment"]["deductions"],
                            "stored": employee.expected_deductions,
                            "matches": abs(float(extracted_data["payment"]["deductions"]) - employee.expected_deductions) < 0.01
                        }
                    }
                }
                all_comparisons.append(comparison)

            finally:
                # Cleanup temporary file
                if os.path.exists(page_path):
                    os.unlink(page_path)

        if not all_comparisons:
            raise HTTPException(status_code=404, detail="No valid payslip data found")

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