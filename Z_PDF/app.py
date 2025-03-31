import os
import io
import time
import torch
import gc
from pathlib import Path
from flask import Flask, request, render_template, jsonify
from qwen_payslip_processor import QwenPayslipProcessor
from qwen_payslip_processor.utils import cleanup_memory
import logging
from transformers import AutoProcessor, AutoModelForImageTextToText

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

logger = logging.getLogger(__name__)

@app.route('/')
def index():
    return render_template('index.html')

# Function to force memory cleanup between prompts
def force_memory_cleanup():
    # Force garbage collection
    gc.collect()
    # Clear CUDA cache if available
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    # Sleep briefly to ensure cleanup completes
    time.sleep(0.5)

@app.route('/process', methods=['POST'])
def process_pdf():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'})
    
    # Save the uploaded file
    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(pdf_path)
    
    # Read the PDF file
    with open(pdf_path, 'rb') as f:
        pdf_bytes = f.read()
    
    # Start timing for processing
    start_time = time.time()
    
    # Create configuration for processing specific parts of pages
    config = {
        "global": {
            "mode": "quadrant"  # Default mode is quadrant for all pages
        },
        "pages": {
            "1": {
                "mode": "quadrant",
                "selected_windows": ["top_left", "bottom_right"]  # Process only top-left and bottom-right of page 1
            },
            "2": {
                "mode": "quadrant",
                "selected_windows": ["bottom_left"]  # Process only bottom-left of page 2
            }
        },
        # PDF settings with specified DPI
        "pdf": {
            "dpi": 350  # Set DPI to 350 as requested
        },
        # Image settings with specified resolution
        "image": {
            "resolution_steps": [1000],  # Use single resolution of 1100px as requested
            "enhance_contrast": True,
            "sharpen_factor": 2.5,
            "contrast_factor": 1.8,
            "brightness_factor": 1.1
        },
        # Add extraction settings to ensure they're available
        "extraction": {
            "confidence_threshold": 0.7,
            "fuzzy_matching": True
        },
        # Text generation settings
        "text_generation": {
            "max_new_tokens": 768,
            "use_beam_search": False,
            "num_beams": 1,
            "temperature": 0.1,
            "top_p": 0.95
        },
        # Window settings
        "window": {
            "overlap": 0.1,
            "min_size": 100
        }
    }
    
    # Custom prompts with much more specific instructions
    custom_prompts = {
        # Top-left of page 1 - ONLY extract employee name, nothing else
        "top_left": """
        Du siehst die obere Hälfte einer deutschen Gehaltsabrechnung.

        FINDE NUR: Den Namen des Angestellten, der nach "Herrn/Frau" steht.
        
        WICHTIG: 
        - Finde NUR den Namen, KEINE anderen Informationen
        - Wenn kein Name gefunden wird, gib "unknown" zurück
        - Extrahiere KEINE Firmen, Adressen oder andere Details
        
        Gib GENAU dieses JSON-Format zurück:
        {
        "found_in_top_left": {
            "employee_name": "Name des Angestellten oder 'unknown'",
            "gross_amount": "0",
            "net_amount": "0"
        }
        }
        """,
        
        # Bottom-right of page 1 - ONLY extract gross and net amounts, nothing else
        "bottom_right": """
        Du siehst die untere Hälfte einer deutschen Gehaltsabrechnung.

        FINDE NUR DIESE ZWEI WERTE:
        1. Bruttogehalt unter dem Label "Gesamt-Brutto"
        2. Nettogehalt unter dem Label "Auszahlungsbetrag"
        
        WICHTIG: 
        - Extrahiere NUR diese zwei Werte, KEINE anderen Informationen
        - Für beide Werte: Nur den Geldbetrag in exakt dem Format wie angezeigt
        - Wenn ein Wert nicht gefunden wird, gib "0" zurück
        
        Gib GENAU dieses JSON-Format zurück:
        {
        "found_in_bottom_right": {
            "employee_name": "unknown",
            "gross_amount": "Betrag bei Gesamt-Brutto oder '0'",
            "net_amount": "Betrag bei Auszahlungsbetrag oder '0'"
        }
        }
        """,
        
        # Bottom-left of page 2 - ONLY extract supervisor name, position and contact
        "bottom_left": """
        Du siehst den unteren linken Bereich auf Seite 2 des Dokuments.

        FINDE NUR: 
        Den Namen des Vorgesetzten/Supervisors
        
        WICHTIG:
        - Extrahiere NUR den Namen des Vorgesetzten, KEINE anderen Informationen
        - IGNORIERE Positionen, Kontaktdaten und alle anderen Details
        - IGNORIERE alle Informationen über Mitarbeiter, Gehälter oder andere Personen
        - Suche nach Abschnitten mit "Supervisor:", "Vorgesetzter:", "Manager:" o.ä.
        - Wenn kein Name gefunden wird, gib "nicht gefunden" zurück
        
        Gib GENAU dieses JSON-Format zurück:
        {
        "found_in_bottom_left": {
            "supervisor_name": "Name des Vorgesetzten oder 'nicht gefunden'"
        }
        }
        """
    }
    
    # Get the absolute path to the model files
    package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    model_dir = os.path.join(package_dir, "pypi_package", "qwen_payslip_processor", "model_files")
    model_path = os.path.join(model_dir, "model")
    processor_path = os.path.join(model_dir, "processor")
    
    # Make sure the environment knows where to find local models
    os.environ["TRANSFORMERS_OFFLINE"] = "1"  # Force offline mode
    
    # Create a modified config to use local model files
    modified_config = config.copy()
    
    # Adding model location settings to the config
    if "model_paths" not in modified_config:
        modified_config["model_paths"] = {}
    
    modified_config["model_paths"]["model_dir"] = model_dir
    modified_config["model_paths"]["model_path"] = model_path
    modified_config["model_paths"]["processor_path"] = processor_path
    modified_config["model_paths"]["use_local_files"] = True
    
    # Create a class extension to override model loading
    class LocalQwenProcessor(QwenPayslipProcessor):
        def _load_model(self):
            try:
                logger.info("Loading local Qwen model...")
                # Override model paths to use local files
                local_model_path = self.config["model_paths"]["model_path"]
                local_processor_path = self.config["model_paths"]["processor_path"] 
                
                # Load processor and model with the local paths
                self.processor = AutoProcessor.from_pretrained(local_processor_path, local_files_only=True)
                self.model = AutoModelForImageTextToText.from_pretrained(
                    local_model_path,
                    torch_dtype=torch.float16 if self.device.type == "cuda" else torch.float32,
                    device_map="auto" if self.device.type == "cuda" else None,
                    local_files_only=True
                )
                
                # Move to CPU if needed
                if self.device.type != "cuda":
                    self.model = self.model.to(self.device)
                    
                logger.info("Local model loaded successfully")
            except Exception as e:
                logger.error(f"Error loading local model: {e}")
                raise
    
    # Initialize processor with the custom class and modified config
    processor = LocalQwenProcessor(
        config=modified_config, 
        custom_prompts=custom_prompts,
        memory_isolation="none"  # Keep memory isolation off as requested
    )
    
    # Force initial memory cleanup 
    force_memory_cleanup()
    
    # Process pages one by one
    all_results = []
    total_pages = 0
    processed_pages = 0
    
    try:
        # Process first page
        first_page_result = processor.process_pdf(pdf_bytes, pages=[1])
        if "results" in first_page_result and len(first_page_result["results"]) > 0:
            # Remove any top-level fields that are not from the raw model output
            for result in first_page_result["results"]:
                # Keep only page metadata and found_in fields
                keys_to_keep = ["page_index", "page_number"] + [k for k in result.keys() if k.startswith("found_in_")]
                # Create a clean result with only the fields we want
                clean_result = {k: result[k] for k in keys_to_keep}
                # Add the clean result to all_results
                all_results.append(clean_result)
        if "total_pages" in first_page_result:
            total_pages = first_page_result["total_pages"]
        processed_pages += 1
        
        # Force memory cleanup between pages for extra safety
        force_memory_cleanup()
        
        # Process second page
        second_page_result = processor.process_pdf(pdf_bytes, pages=[2])
        if "results" in second_page_result and len(second_page_result["results"]) > 0:
            # Remove any top-level fields that are not from the raw model output
            for result in second_page_result["results"]:
                # Keep only page metadata and found_in fields
                keys_to_keep = ["page_index", "page_number"] + [k for k in result.keys() if k.startswith("found_in_")]
                # Create a clean result with only the fields we want
                clean_result = {k: result[k] for k in keys_to_keep}
                # Add the clean result to all_results
                all_results.append(clean_result)
        if "total_pages" in second_page_result and total_pages == 0:
            total_pages = second_page_result["total_pages"]
        processed_pages += 1
    except Exception as e:
        return jsonify({
            'error': f"Error processing PDF: {str(e)}",
            'processing_time': time.time() - start_time
        })
    
    # Calculate total processing time
    processing_time = time.time() - start_time
    
    # Create combined result with ONLY the raw model outputs and package metadata
    result = {
        "results": all_results,
        "processing_time": processing_time,
        "processed_pages": processed_pages,
        "total_pages": total_pages
    }
    
    # Add isolation mode information to the result
    # Get this from the processor object, or from the first page result if available
    isolation_mode = {"requested": processor.memory_isolation, "actual": processor.memory_isolation}
    
    # If we have isolation statistics from the results, use them
    if "isolation_mode" in first_page_result:
        isolation_mode = first_page_result["isolation_mode"]
    
    # Add isolation mode to the result
    result["isolation_mode"] = isolation_mode
    
    # Return results and filename with ONLY raw model output and package metadata
    return jsonify({
        'status': 'success',
        'filename': file.filename,
        'processing_time': processing_time,
        'result': result  # Return only raw model outputs and package metadata
    })

if __name__ == '__main__':
    app.run(debug=True)