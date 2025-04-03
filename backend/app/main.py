import os
import re
import time
import logging
from datetime import datetime
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Form, Request
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Optional
import json
import subprocess
import requests
from fastapi.responses import FileResponse, JSONResponse
import io
import yaml

from . import models, schemas, database
from .database import SessionLocal, engine
from .qwen_processor import QwenVLProcessor
from .docker_client import QwenDockerClient as DockerClient

# Configure logging with absolute path
# Use an absolute path that doesn't depend on working directory
# For Windows, this ensures logs are written to a known location
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Use a single persistent log file
log_file = os.path.join(log_dir, "payslip_processor.log")

# Configure logging with a formatter that includes a timestamp
class CustomFormatter(logging.Formatter):
    def format(self, record):
        formatted_message = super().format(record)
        # On first message of a new run, add separator
        if getattr(self, 'first_message', True):
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            separator = f"\n\n{'=' * 80}\n{now} - NEW APPLICATION RUN\n{'=' * 80}\n\n"
            self.first_message = False
            return separator + formatted_message
        return formatted_message

# Configure root logger to ensure all logs go to our file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Console handler
    ]
)

# Create file handler with our custom formatter
file_handler = logging.FileHandler(log_file, encoding='utf-8', mode='a')
formatter = CustomFormatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
formatter.first_message = True
file_handler.setFormatter(formatter)

# Add the file handler to the root logger
logging.getLogger().addHandler(file_handler)

# Get logger for this module
logger = logging.getLogger(__name__)
logger.info("Logger initialized")

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Docker client
docker_client = DockerClient(
    container_name="qwen-payslip-processor",
    port=27842,
    host="localhost"
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

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def read_root():
    return {"message": "Payslip Processor API is running"}

@app.get("/health")
def health_check():
    """Simple health check endpoint for the frontend to verify backend connection"""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.get("/container-status")
def container_status():
    """Get the current status of the Docker container"""
    try:
        logger.info("Checking Docker container status")
        docker_status = docker_client._check_container_status()
        logger.info(f"Container status check result: {docker_status.get('status', 'unknown')}")
        
        # Ensure status is one of the values the frontend expects: running, initializing, stopped, not_found, error
        if docker_status["status"] not in ["running", "initializing", "stopped", "not_found", "error"]:
            # If we get an unexpected status, map it to a value the frontend understands
            logger.warning(f"Unexpected status '{docker_status['status']}', mapping to appropriate value")
            if docker_status["status"] == "ok":
                docker_status["status"] = "running"
        
        # Add GPU information to the response
        docker_status["gpu_available"] = docker_client.gpu_info['available']
        docker_status["gpu_name"] = docker_client.gpu_info['name']
        
        # Check if container should be using GPU but isn't
        if docker_status["status"] == "running" and docker_client.gpu_info['available']:
            try:
                logger.info(f"Container is running and GPU is available, checking if container is using GPU")
                response = requests.get(f"{docker_client.base_url}/status", timeout=3)
                if response.status_code == 200:
                    status_data = response.json()
                    # Check for CUDA/GPU usage in status response
                    docker_status["using_gpu"] = (
                        'device' in status_data and 'cuda' in str(status_data['device']).lower()
                    ) or (
                        'gpu' in status_data and status_data['gpu']
                    )
                    if not docker_status["using_gpu"]:
                        logger.warning("GPU is available but container is not using it")
                        docker_status["warning"] = "GPU is available but container is not using it"
                else:
                    logger.warning(f"Container status endpoint returned non-200 status: {response.status_code}")
                    docker_status["warning"] = f"Container status endpoint returned unexpected status: {response.status_code}"
            except Exception as e:
                logger.error(f"Error checking container GPU status: {e}")
                # If we can't determine GPU status but logs show CUDA, assume it's using GPU
                docker_status["using_gpu"] = False
                docker_status["warning"] = f"Couldn't determine GPU status: {str(e)}"
        
        logger.info(f"Returning container status: {docker_status}")
        return docker_status
    except Exception as e:
        logger.error(f"Error checking container status: {str(e)}")
        error_response = {"status": "error", "message": str(e)}
        logger.error(f"Returning error response: {error_response}")
        return error_response

@app.post("/restart-container-with-gpu")
def restart_container_with_gpu():
    """Restart the container with GPU support if GPU is available"""
    try:
        if not docker_client.gpu_info['available']:
            return {"status": "error", "message": "No GPU detected on this system"}
            
        success = docker_client.restart_container_with_gpu()
        
        if success:
            return {"status": "success", "message": "Container restarted with GPU support"}
        else:
            return {"status": "error", "message": "Failed to restart container with GPU support"}
    except Exception as e:
        logger.error(f"Error restarting container: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/extract-payslip")
async def extract_payslip(
    file: UploadFile = File(...),
    window_mode: Optional[str] = Form("vertical"),  # Default to vertical mode instead of quadrant
    memory_isolation: Optional[str] = Form(None),  # Allow setting memory isolation
    force_cpu: Optional[bool] = Form(False)  # Allow forcing CPU but default to false
):
    """
    Extract data from a payslip PDF - Default mode for backward compatibility
    """
    try:
        # Read uploaded file
        file_content = await file.read()
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        # Process file based on file type
        processor = QwenVLProcessor(document_type="payslip")
        
        # Set processing configuration from parameters
        if "processing" not in processor.config:
            processor.config["processing"] = {}
            
        # Set window mode from parameter
        processor.config["processing"]["window_mode"] = window_mode
        
        # Set mode-appropriate window selections
        valid_windows = {
            "vertical": ["top", "bottom"],
            "horizontal": ["left", "right"],  # Horizontal splits document into left/right parts
            "quadrant": ["top_left", "top_right", "bottom_left", "bottom_right"],
            "whole": ["whole"]
        }
        
        # Select appropriate windows based on window_mode
        if window_mode in valid_windows:
            processor.config["processing"]["selected_windows"] = valid_windows[window_mode]
            
        # Set memory isolation if provided
        if memory_isolation is not None:
            processor.config["processing"]["memory_isolation"] = memory_isolation
            
        # Set force_cpu if provided
        processor.config["processing"]["force_cpu"] = force_cpu
        
        # Ensure global settings don't override our explicit window mode choices
        if "global" in processor.config:
            # Replace global settings to prevent conflicts with our explicit selection
            processor.config["global"] = {
                "mode": window_mode,
                "selected_windows": valid_windows[window_mode]
            }
            # Keep any existing prompt instructions if present
            if "prompt_instructions" in processor.config.get("global", {}):
                processor.config["global"]["prompt_instructions"] = processor.config["global"].get("prompt_instructions")
            
            logger.info(f"Replaced global settings to ensure {window_mode} mode is used for payslip processing")
        
        logger.info(f"Processing payslip with window mode '{window_mode}'")
        
        start_time = time.time()
        
        if file_ext in ['.pdf']:
            extracted_data = processor.process_pdf_file(
                pdf_bytes=file_content,
                file_name=file.filename
            )
        elif file_ext in ['.jpg', '.jpeg', '.png']:
            extracted_data = processor.process_image_file(
                image_bytes=file_content
            )
        else:
            return JSONResponse(
                status_code=400,
                content={"error": f"Unsupported file format: {file_ext}. Please upload a PDF, JPG, or PNG file."}
            )
            
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Add processing metadata to response
        result = {
            "extracted_data": extracted_data,
            "processing": {
                "processing_time_seconds": processing_time,
                "window_mode": window_mode,
                "selected_windows": processor.config["processing"]["selected_windows"]
            },
            "file": {
                "filename": file.filename,
                "file_type": file_ext.lstrip('.')
            }
        }
        
        # Force explicit memory cleanup again to ensure GPU memory is released
        try:
            processor._explicit_memory_cleanup()
        except Exception as e:
            logger.warning(f"Additional memory cleanup failed: {str(e)}")
        
        return result
    except Exception as e:
        logger.error(f"Error processing payslip: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Error processing file: {str(e)}"}
        )

@app.post("/api/extract-payslip-single")
async def extract_payslip_single(
    file: UploadFile = File(...),
    employee_name_page: Optional[int] = Form(None),
    employee_name_quadrant: Optional[str] = Form(None),
    gross_page: Optional[int] = Form(None),
    gross_quadrant: Optional[str] = Form(None),
    net_page: Optional[int] = Form(None),
    net_quadrant: Optional[str] = Form(None),
    window_mode: Optional[str] = Form("quadrant"),  # Default window mode
    memory_isolation: Optional[str] = Form(None),  # Allow setting memory isolation
    force_cpu: Optional[bool] = Form(False)  # Allow forcing CPU but default to false
):
    """
    Extract data from a single payslip PDF with optional page and quadrant specifications
    """
    try:
        # Read uploaded file
        file_content = await file.read()
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        if file_ext not in ['.pdf']:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_ext}")
        
        # Initialize processor with default config
        processor = QwenVLProcessor(document_type="payslip")
        
        # Check if page/quadrant information was provided
        has_page_info = any([
            employee_name_page is not None,
            gross_page is not None,
            net_page is not None
        ])
        
        has_quadrant_info = any([
            employee_name_quadrant is not None,
            gross_quadrant is not None,
            net_quadrant is not None
        ])
        
        # Update processing config with user-specified parameters
        if "processing" not in processor.config:
            processor.config["processing"] = {}
            
        # Set window mode from parameter or default to quadrant
        processor.config["processing"]["window_mode"] = window_mode
        
        # Set memory isolation if provided
        if memory_isolation is not None:
            processor.config["processing"]["memory_isolation"] = memory_isolation
            
        # Set force_cpu if provided
        processor.config["processing"]["force_cpu"] = force_cpu
        
        if has_page_info or has_quadrant_info:
            # Use guided extraction with specific page/section
            logger.info("Processing payslip with guided extraction")
            
            # Process each field
            results = {}
            guided_processing_info = {
                "used": True,
                "fields": {}
            }
            
            # Process specific fields in different pages/quadrants
            # Employee name
            if employee_name_page is not None:
                logger.info(f"Extracting employee name from page {employee_name_page}, quadrant {employee_name_quadrant}")
                guided_processing_info["fields"]["employee_name"] = {
                    "page": employee_name_page,
                    "quadrant": employee_name_quadrant
                }
                
                # Set up page-specific configuration
                page_configs = {}
                
                # Determine the correct window mode and selections based on quadrant
                extraction_window_mode = window_mode
                extraction_selected_windows = [employee_name_quadrant] if employee_name_quadrant else None
                
                # Ensure the window mode matches the quadrant
                if employee_name_quadrant:
                    if employee_name_quadrant in ["top", "bottom"]:
                        extraction_window_mode = "vertical"
                    elif employee_name_quadrant in ["top_left", "top_right", "bottom_left", "bottom_right"]:
                        extraction_window_mode = "quadrant"
                    else:
                        extraction_window_mode = "whole"
                else:
                    extraction_window_mode = "whole"
                    extraction_selected_windows = None
                
                page_configs[str(employee_name_page)] = {
                    "mode": extraction_window_mode,
                    "selected_windows": extraction_selected_windows
                }
                
                # Add to processor config
                processor.config["pages"] = page_configs
                
                # Process the specific page with explicit override of global settings
                partial_result = processor.process_pdf_with_pages(
                    pdf_bytes=file_content,
                    file_name=file.filename,
                    pages=[employee_name_page],
                    selected_windows=extraction_selected_windows,
                    override_global_settings="true" if extraction_selected_windows else None
                )
                
                # Extract employee name and add to results
                if "employee" in partial_result and "name" in partial_result["employee"]:
                    if "employee" not in results:
                        results["employee"] = {}
                    results["employee"]["name"] = partial_result["employee"]["name"]
            
            # Gross amount
            if gross_page is not None:
                logger.info(f"Extracting gross amount from page {gross_page}, quadrant {gross_quadrant}")
                guided_processing_info["fields"]["gross_amount"] = {
                    "page": gross_page,
                    "quadrant": gross_quadrant
                }
                
                # Set up page-specific configuration
                page_configs = {}
                
                # Determine the correct window mode and selections based on quadrant
                extraction_window_mode = window_mode
                extraction_selected_windows = [gross_quadrant] if gross_quadrant else None
                
                # Ensure the window mode matches the quadrant
                if gross_quadrant:
                    if gross_quadrant in ["top", "bottom"]:
                        extraction_window_mode = "vertical"
                    elif gross_quadrant in ["top_left", "top_right", "bottom_left", "bottom_right"]:
                        extraction_window_mode = "quadrant"
                    else:
                        extraction_window_mode = "whole"
                else:
                    extraction_window_mode = "whole"
                    extraction_selected_windows = None
                
                page_configs[str(gross_page)] = {
                    "mode": extraction_window_mode,
                    "selected_windows": extraction_selected_windows
                }
                
                # Add to processor config
                processor.config["pages"] = page_configs
                
                # Process the specific page with explicit override of global settings
                partial_result = processor.process_pdf_with_pages(
                    pdf_bytes=file_content,
                    file_name=file.filename,
                    pages=[gross_page],
                    selected_windows=extraction_selected_windows,
                    override_global_settings="true" if extraction_selected_windows else None
                )
                
                # Extract gross amount and add to results
                if "payment" in partial_result and "gross" in partial_result["payment"]:
                    if "payment" not in results:
                        results["payment"] = {}
                    results["payment"]["gross"] = partial_result["payment"]["gross"]
            
            # Net amount
            if net_page is not None:
                logger.info(f"Extracting net amount from page {net_page}, quadrant {net_quadrant}")
                guided_processing_info["fields"]["net_amount"] = {
                    "page": net_page,
                    "quadrant": net_quadrant
                }
                
                # Set up page-specific configuration
                page_configs = {}
                
                # Determine the correct window mode and selections based on quadrant
                extraction_window_mode = window_mode
                extraction_selected_windows = [net_quadrant] if net_quadrant else None
                
                # Ensure the window mode matches the quadrant
                if net_quadrant:
                    if net_quadrant in ["top", "bottom"]:
                        extraction_window_mode = "vertical"
                    elif net_quadrant in ["top_left", "top_right", "bottom_left", "bottom_right"]:
                        extraction_window_mode = "quadrant"
                    else:
                        extraction_window_mode = "whole"
                else:
                    extraction_window_mode = "whole"
                    extraction_selected_windows = None
                
                page_configs[str(net_page)] = {
                    "mode": extraction_window_mode,
                    "selected_windows": extraction_selected_windows
                }
                
                # Add to processor config
                processor.config["pages"] = page_configs
                
                # Process the specific page with explicit override of global settings
                partial_result = processor.process_pdf_with_pages(
                    pdf_bytes=file_content,
                    file_name=file.filename,
                    pages=[net_page],
                    selected_windows=extraction_selected_windows,
                    override_global_settings="true" if extraction_selected_windows else None
                )
                
                # Extract net amount and add to results
                if "payment" in partial_result and "net" in partial_result["payment"]:
                    if "payment" not in results:
                        results["payment"] = {}
                    results["payment"]["net"] = partial_result["payment"]["net"]
            
            # Ensure minimum result structure
            if "employee" not in results:
                results["employee"] = {"name": "unknown"}
            if "payment" not in results:
                results["payment"] = {"gross": "0", "net": "0"}
            
            # Add processing info to results
            results["guided_processing"] = guided_processing_info
            
            return results
        else:
            # No specific page/quadrant info provided, use default window mode
            logger.info(f"Processing payslip with default window mode: {window_mode}")
            
            # Set mode-appropriate window selections
            valid_windows = {
                "vertical": ["top", "bottom"],
                "horizontal": ["left", "right"],  # Horizontal splits document into left/right parts
                "quadrant": ["top_left", "top_right", "bottom_left", "bottom_right"],
                "whole": ["whole"]
            }
            
            # Select appropriate windows based on window_mode
            selected_windows = None
            if window_mode in valid_windows:
                selected_windows = valid_windows[window_mode]
                processor.config["processing"]["selected_windows"] = selected_windows
            
            # Set override_global_settings to true to ensure our window mode is respected
            processor.config["processing"]["override_global_settings"] = True
            
            # If using quadrant mode, ensure global settings don't override
            if window_mode == "quadrant":
                # Override global settings
                if "global" in processor.config:
                    # Instead of just updating global mode, replace it completely to avoid conflicts
                    processor.config["global"] = {
                        "mode": "quadrant",
                        "selected_windows": valid_windows["quadrant"]
                    }
                    # Keep any existing prompt instructions if present
                    if "prompt_instructions" in processor.config.get("global", {}):
                        processor.config["global"]["prompt_instructions"] = processor.config["global"].get("prompt_instructions")
                    
                    logger.info("Completely replaced global settings to ensure quadrant mode is used")
            
            # Set override_global_settings parameter explicitly when calling process_pdf_file
            extracted_data = processor.process_pdf_file(
                pdf_bytes=file_content,
                file_name=file.filename
            )
            
            # Add metadata indicating no guided processing was used
            extracted_data["guided_processing"] = {
                "used": False,
                "window_mode": window_mode
            }
            
            return extracted_data
            
    except Exception as e:
        logger.error(f"Error processing payslip: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/extract-payslip-batch")
async def extract_payslip_batch(
    files: List[UploadFile] = File(...),
    window_mode: Optional[str] = Form("horizontal"),  # Default window mode
    memory_isolation: Optional[str] = Form(None),  # Allow setting memory isolation
    force_cpu: Optional[bool] = Form(False)  # Allow forcing CPU but default to false
):
    """
    Extract data from multiple payslip PDFs using batch processing
    """
    try:
        all_results = []
        total_files = len(files)
        logger.info(f"Processing batch of {total_files} payslip files")
        
        # Initialize processor with default config for batch processing
        processor = QwenVLProcessor(document_type="payslip")
        
        # Set processing configuration from parameters
        if "processing" not in processor.config:
            processor.config["processing"] = {}
            
        # Set window mode from parameter
        processor.config["processing"]["window_mode"] = window_mode
        
        # Set mode-appropriate window selections
        valid_windows = {
            "vertical": ["top", "bottom"],
            "horizontal": ["top", "bottom"],  # Horizontal splits document into top/bottom parts
            "quadrant": ["top_left", "top_right", "bottom_left", "bottom_right"],
            "whole": ["whole"]
        }
        
        # Select appropriate windows based on window_mode
        selected_windows = None
        if window_mode in valid_windows:
            selected_windows = valid_windows[window_mode]
            processor.config["processing"]["selected_windows"] = selected_windows
            
        # Set override_global_settings to true to ensure our window mode is respected
        processor.config["processing"]["override_global_settings"] = True
            
        # Set memory isolation if provided
        if memory_isolation is not None:
            processor.config["processing"]["memory_isolation"] = memory_isolation
            
        # Set force_cpu if provided
        processor.config["processing"]["force_cpu"] = force_cpu
        
        # Ensure global settings don't override our explicit window mode choices
        if "global" in processor.config:
            # Replace global settings to prevent conflicts with our explicit selection
            processor.config["global"] = {
                "mode": window_mode,
                "selected_windows": selected_windows
            }
            # Keep any existing prompt instructions if present
            if "prompt_instructions" in processor.config.get("global", {}):
                processor.config["global"]["prompt_instructions"] = processor.config["global"].get("prompt_instructions")
            
            logger.info(f"Replaced global settings to ensure {window_mode} mode is used for batch processing")
        
        logger.info(f"Using window mode '{window_mode}' with windows {processor.config['processing'].get('selected_windows', [])}")
        
        for i, file in enumerate(files):
            try:
                # Read file content
                file_content = await file.read()
                file_ext = os.path.splitext(file.filename)[1].lower()
                
                if file_ext not in ['.pdf']:
                    all_results.append({
                        "filename": file.filename,
                        "error": f"Unsupported file type: {file_ext}",
                        "success": False
                    })
                    continue
                
                logger.info(f"Processing file {i+1}/{total_files}: {file.filename}")
                
                # Process the file
                extracted_data = processor.process_pdf_file(
                    pdf_bytes=file_content,
                    file_name=file.filename
                )
                
                # Add filename to the result
                extracted_data["filename"] = file.filename
                extracted_data["success"] = True
                
                all_results.append(extracted_data)
                
            except Exception as e:
                logger.error(f"Error processing file {file.filename}: {str(e)}")
                all_results.append({
                    "filename": file.filename,
                    "error": str(e),
                    "success": False
                })
        
        # Return batch results
        return {
            "batch_results": all_results,
            "total_files": total_files,
            "successful_files": sum(1 for r in all_results if r.get("success", False)),
            "processing_mode": "batch",
            "window_mode": window_mode
        }
        
    except Exception as e:
        logger.error(f"Error in batch processing: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/validate-payslip-by-id")
async def validate_payslip_by_id(data: dict, db: Session = Depends(get_db)):
    """
    Validate extracted payslip data against a specific employee ID.
    """
    try:
        # Extract employee ID from the data
        employee_id = data.get("employee_id")
        payslip_data = data.get("payslip_data")
        
        if not employee_id:
            raise HTTPException(status_code=400, detail="Employee ID is required")
            
        if not payslip_data:
            raise HTTPException(status_code=400, detail="Payslip data is required")
        
        # TODO: Implement validation logic against employee database
        # For now, we'll just return a mock validation result
        validation_result = {
            "is_valid": True,
            "employee_id": employee_id,
            "matched_fields": ["name", "salary", "position"],
            "mismatched_fields": [],
            "validation_time": datetime.now().isoformat()
        }
        
        return validation_result
    except Exception as e:
        logger.error(f"Error validating payslip: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/process-property")
async def process_property(
    file: UploadFile = File(...),
    window_mode: Optional[str] = Form("whole"),  # Default window mode for property listings
    memory_isolation: Optional[str] = Form(None),  # Allow setting memory isolation
    force_cpu: Optional[bool] = Form(False)  # Allow forcing CPU but default to false
):
    """
    Process a property listing document to extract data
    """
    try:
        # Read uploaded file
        file_content = await file.read()
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        # Process file based on file type
        processor = QwenVLProcessor(document_type="property")
        
        # Set processing configuration from parameters
        if "processing" not in processor.config:
            processor.config["processing"] = {}
            
        # Set window mode from parameter
        processor.config["processing"]["window_mode"] = window_mode
        
        # Set mode-appropriate window selections
        valid_windows = {
            "vertical": ["top", "bottom"],
            "horizontal": ["top", "bottom"],  # Horizontal splits document into top/bottom parts
            "quadrant": ["top_left", "top_right", "bottom_left", "bottom_right"],
            "whole": ["whole"]
        }
        
        # Select appropriate windows based on window_mode
        if window_mode in valid_windows:
            processor.config["processing"]["selected_windows"] = valid_windows[window_mode]
            
        # Set memory isolation if provided
        if memory_isolation is not None:
            processor.config["processing"]["memory_isolation"] = memory_isolation
            
        # Set force_cpu if provided
        processor.config["processing"]["force_cpu"] = force_cpu
        
        # Ensure global settings don't override our explicit window mode choices
        if "global" in processor.config:
            # Replace global settings to prevent conflicts with our explicit selection
            processor.config["global"] = {
                "mode": window_mode,
                "selected_windows": valid_windows[window_mode]
            }
            # Keep any existing prompt instructions if present
            if "prompt_instructions" in processor.config.get("global", {}):
                processor.config["global"]["prompt_instructions"] = processor.config["global"].get("prompt_instructions")
            
            logger.info(f"Replaced global settings to ensure {window_mode} mode is used for property processing")
        
        logger.info(f"Processing property document with window mode '{window_mode}'")
        
        if file_ext in ['.pdf']:
            extracted_data = processor.process_pdf_file(
                pdf_bytes=file_content,
                file_name=file.filename
            )
            return extracted_data
        elif file_ext in ['.jpg', '.jpeg', '.png']:
            extracted_data = processor.process_image_file(
                image_bytes=file_content
            )
            return extracted_data
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_ext}")
    except Exception as e:
        logger.error(f"Error processing property document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/config")
def get_config(document_type: str = "payslip"):
    """
    Get the current configuration settings for a document type
    """
    try:
        # Initialize processor with the specified document type to load its config
        processor = QwenVLProcessor(document_type=document_type)
        
        # Return the config data
        return {
            "document_type": document_type,
            "config": processor.config
        }
    except Exception as e:
        logger.error(f"Error getting configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/config/update")
async def update_config(data: dict, document_type: str = "payslip"):
    """
    Update configuration settings for a document type
    
    The request body should contain configuration sections to update, e.g.:
    {
        "processing": {
            "window_mode": "horizontal",
            "selected_windows": ["left", "right"]
        },
        "pdf": {
            "dpi": 400
        }
    }
    """
    try:
        # Initialize processor with the specified document type to load its config
        processor = QwenVLProcessor(document_type=document_type)
        
        # Get the current config
        current_config = processor.config
        
        # Update configuration with provided values
        for section, settings in data.items():
            if section not in current_config:
                current_config[section] = {}
            
            if isinstance(settings, dict):
                for key, value in settings.items():
                    current_config[section][key] = value
        
        # Save the updated configuration
        config_path = os.path.normpath(os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            f'config_{document_type}.yml'
        ))
        
        try:
            with open(config_path, 'w') as f:
                yaml.dump(current_config, f, default_flow_style=False, sort_keys=False)
                
            logger.info(f"Updated configuration saved to {config_path}")
        except Exception as e:
            logger.error(f"Error saving configuration: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error saving configuration: {str(e)}")
        
        # Return the updated config
        return {
            "document_type": document_type,
            "config": current_config,
            "message": "Configuration updated successfully"
        }
    except Exception as e:
        logger.error(f"Error updating configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("shutdown")
def shutdown_event():
    """Release resources on server shutdown"""
    logger.info("Server shutting down")
    # No resources to clean up when using Docker container 

@app.post("/api/extract-payslip-advanced")
async def extract_payslip_advanced(
    file: UploadFile = File(...),
    # Core processing parameters
    window_mode: Optional[str] = Form(None),
    selected_windows: Optional[str] = Form(None),
    memory_isolation: Optional[str] = Form(None),
    force_cpu: Optional[bool] = Form(None),
    gpu_memory_fraction: Optional[float] = Form(None),
    pages: Optional[str] = Form(None),
    
    # PDF parameters
    pdf_dpi: Optional[int] = Form(None),
    
    # Image parameters
    image_resolution_steps: Optional[str] = Form(None),
    image_enhance_contrast: Optional[bool] = Form(None),
    image_sharpen_factor: Optional[float] = Form(None),
    image_contrast_factor: Optional[float] = Form(None),
    image_brightness_factor: Optional[float] = Form(None),
    image_ocr_language: Optional[str] = Form(None),
    image_ocr_threshold: Optional[int] = Form(None),
    
    # Window settings
    window_overlap: Optional[float] = Form(None),
    window_min_size: Optional[int] = Form(None),
    
    # Text generation settings
    text_generation_max_new_tokens: Optional[int] = Form(None),
    text_generation_use_beam_search: Optional[bool] = Form(None),
    text_generation_num_beams: Optional[int] = Form(None),
    text_generation_temperature: Optional[float] = Form(None),
    text_generation_top_p: Optional[float] = Form(None),
    
    # Extraction settings
    extraction_confidence_threshold: Optional[float] = Form(None),
    extraction_fuzzy_matching: Optional[bool] = Form(None),
    
    # Global settings
    global_mode: Optional[str] = Form(None),
    global_prompt: Optional[str] = Form(None),
    global_selected_windows: Optional[str] = Form(None),
    
    # Window-specific prompts
    prompt_top: Optional[str] = Form(None),
    prompt_bottom: Optional[str] = Form(None),
    prompt_left: Optional[str] = Form(None),
    prompt_right: Optional[str] = Form(None),
    prompt_top_left: Optional[str] = Form(None),
    prompt_top_right: Optional[str] = Form(None),
    prompt_bottom_left: Optional[str] = Form(None),
    prompt_bottom_right: Optional[str] = Form(None),
    prompt_whole: Optional[str] = Form(None)
):
    """
    Advanced API endpoint that directly passes all parameters to the Docker container
    
    This endpoint provides complete control over all processing parameters
    supported by the Docker container, allowing fine-grained customization
    without needing to modify the configuration files.
    """
    try:
        # Read uploaded file
        file_content = await file.read()
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        if file_ext not in ['.pdf']:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_ext}")
        
        # Initialize processor with default config
        processor = QwenVLProcessor(document_type="payslip")
        
        # If window_mode is specified but no selected_windows, use appropriate defaults
        if window_mode and not selected_windows:
            # Set proper window selections based on mode
            valid_windows = {
                "vertical": "top,bottom",
                "horizontal": "left,right",  # Horizontal splits document into left/right parts
                "quadrant": "top_left,top_right,bottom_left,bottom_right",
                "whole": "whole"
            }
            
            # Apply default windows for the selected mode
            if window_mode in valid_windows:
                selected_windows = valid_windows[window_mode]
                logger.info(f"Auto-selecting windows for mode '{window_mode}': {selected_windows}")
        
        # Collect custom prompts from form parameters
        custom_prompts = {}
        for window in ['top', 'bottom', 'left', 'right', 'top_left', 'top_right', 
                      'bottom_left', 'bottom_right', 'whole']:
            prompt_value = locals().get(f'prompt_{window}')
            if prompt_value:
                custom_prompts[window] = prompt_value
        
        # Process page numbers if provided
        page_numbers = None
        if pages:
            try:
                if ',' in pages:
                    page_numbers = [int(p.strip()) for p in pages.split(',')]
                else:
                    page_numbers = int(pages)
            except ValueError:
                logger.warning(f"Invalid page numbers format: {pages}. Using all pages.")
        
        # Process selected windows if provided as comma-separated string
        windows_list = None
        if selected_windows:
            windows_list = [w.strip() for w in selected_windows.split(',')]
        
        # Process resolution steps if provided
        resolution_steps = None
        if image_resolution_steps:
            try:
                # Handle different formats: comma-separated string, single value, or already parsed list
                if isinstance(image_resolution_steps, list):
                    resolution_steps = [int(step) for step in image_resolution_steps]
                elif isinstance(image_resolution_steps, str):
                    if ',' in image_resolution_steps:
                        resolution_steps = [int(s.strip()) for s in image_resolution_steps.split(',')]
                    else:
                        # Handle single value case
                        resolution_steps = [int(image_resolution_steps)]
                else:
                    # Handle potential numeric value
                    resolution_steps = [int(image_resolution_steps)]
                
                logger.info(f"Using custom resolution steps: {resolution_steps}")
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid resolution steps format: {image_resolution_steps}. Using defaults. Error: {e}")
                # Provide a reasonable default if parsing fails
                resolution_steps = [600, 400]
        
        # Process global selected windows if provided
        global_windows_list = None
        if global_selected_windows:
            global_windows_list = [w.strip() for w in global_selected_windows.split(',')]
        
        # Create parameters dict for Docker container
        container_params = {
            # Core parameters
            "pdf_bytes": file_content,
            "file_name": file.filename,
            "window_mode": window_mode,
            "selected_windows": windows_list,
            "memory_isolation": memory_isolation,
            "force_cpu": force_cpu,
            "gpu_memory_fraction": gpu_memory_fraction,
            "pages": page_numbers,
            "custom_prompts": custom_prompts if custom_prompts else None,
            
            # PDF parameters
            "pdf_dpi": pdf_dpi,
            
            # Image parameters
            "image_resolution_steps": resolution_steps,
            "image_enhance_contrast": image_enhance_contrast,
            "image_sharpen_factor": image_sharpen_factor,
            "image_contrast_factor": image_contrast_factor,
            "image_brightness_factor": image_brightness_factor,
            "image_ocr_language": image_ocr_language,
            "image_ocr_threshold": image_ocr_threshold,
            
            # Window settings
            "window_overlap": window_overlap,
            "window_min_size": window_min_size,
            
            # Text generation settings
            "text_generation_max_new_tokens": text_generation_max_new_tokens,
            "text_generation_use_beam_search": text_generation_use_beam_search,
            "text_generation_num_beams": text_generation_num_beams,
            "text_generation_temperature": text_generation_temperature,
            "text_generation_top_p": text_generation_top_p,
            
            # Extraction settings
            "extraction_confidence_threshold": extraction_confidence_threshold,
            "extraction_fuzzy_matching": extraction_fuzzy_matching,
            
            # Global settings 
            # Explicitly set global_mode to None to prevent container defaults from overriding
            "global_mode": None if window_mode else global_mode,
            "global_prompt": global_prompt,
            "global_selected_windows": None if windows_list else global_windows_list,
            
            # Force UI parameters to override global settings
            "override_global_settings": True
        }
        
        # Filter out None values
        container_params = {k: v for k, v in container_params.items() if v is not None}
        
        logger.info(f"Processing payslip with {len(container_params)} custom parameters")
        
        # If window_mode is specified, log a special note to explain precedence
        if window_mode:
            logger.info(f"Using explicitly provided window_mode '{window_mode}' with selected_windows {windows_list}. " +
                        "Explicit parameters will override any global settings.")
        
        # Process the document with all specified parameters
        if page_numbers:
            response = processor.docker_client.process_pdf(**container_params)
            result = processor._extract_from_response(response)
            
            # Add page processing info to result
            result["page_processing"] = {
                "pages_requested": page_numbers,
                "pages_processed": response.get("processed_pages", 0),
                "total_pages": response.get("total_pages", 0)
            }
        else:
            # Standard processing without specific pages
            response = processor.docker_client.process_pdf(**container_params)
            result = processor._extract_from_response(response)
        
        # Add additional metadata about the processing
        result["processing_info"] = {
            "advanced_mode": True,
            "parameters_used": {k: v for k, v in container_params.items() 
                               if k not in ["pdf_bytes", "custom_prompts"]}
        }
        
        if custom_prompts:
            result["processing_info"]["custom_prompts_used"] = list(custom_prompts.keys())
            
        return result
            
    except Exception as e:
        logger.error(f"Error in advanced payslip processing: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/cleanup-memory")
async def cleanup_memory():
    """
    Force CUDA memory cleanup on the backend
    This endpoint is available to force memory cleanup between operations
    without needing to restart the container.
    """
    try:
        # Create temporary processor instance just for cleanup
        processor = QwenVLProcessor(document_type="payslip")
        
        # Call explicit cleanup method
        processor._explicit_memory_cleanup()
        
        # Return success response
        return {
            "status": "success",
            "message": "Memory cleanup completed successfully"
        }
    except Exception as e:
        logger.error(f"Error during memory cleanup: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Error during memory cleanup: {str(e)}"
            }
        ) 