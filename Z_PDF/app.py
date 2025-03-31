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
    
    # Custom prompts with context-clearing instructions
    # We can remove the context-clearing prefixes since memory_isolation will handle this
    custom_prompts = {
        # Top-left of page 1 - look for employee name
        "top_left": """
        Du siehst die obere Hälfte einer deutschen Gehaltsabrechnung.

        SUCHE PRÄZISE NACH: Dem Namen des Angestellten, der direkt nach der Überschrift "Herrn/Frau" steht.
        SCHAUE IN DIESEM BEREICH: Im oberen linken Viertel des Dokuments, meist unter dem Label "Herrn/Frau".
        POSITION: Der Name steht 3-4 Zeilen unter der Personalnummer.

        WICHTIG: Wenn du keinen Namen findest, gib "unknown" zurück.
        Ich brauche KEINEN Namen einer Firma oder einer Krankenversicherung, nur den Namen des Angestellten.

        Gib deinen Fund als JSON zurück:
        {
        "found_in_top_left": {
            "employee_name": "Name des Angestellten oder 'unknown'",
            "gross_amount": "0",
            "net_amount": "0"
        }
        }
        """,
        
        # Bottom-right of page 1 - look for financial information
        "bottom_right": """
        Du siehst die untere Hälfte einer deutschen Gehaltsabrechnung.

        SUCHE PRÄZISE NACH BEIDEN WERTEN:
        1. Bruttogehalt ("Gesamt-Brutto"): 
           - WICHTIG: Es gibt zwei "Gesamt-Brutto" Werte im Dokument!
           - Nimm NUR den Wert aus der oberen rechten Ecke
           - Der korrekte Wert steht unter dem Label "Gesamt-Brutto"
           - IGNORIERE den Wert unter "Verdienstbescheinigung" auf der linken Seite
           - Der Wert sollte im Bereich von 1.000 € bis 10.000 € liegen
           - Typischerweise ist dieser Wert kleiner als die Summen unter "Verdienstbescheinigung"

        2. Nettogehalt ("Auszahlungsbetrag"):
           - Suche nach dem Label "Auszahlungsbetrag" ganz unten im Dokument
           - Der Wert steht direkt daneben, meist rechts ausgerichtet
           - Dies ist typischerweise die letzte Zahl im Dokument
           - Der Wert sollte kleiner als das Bruttogehalt sein

        WICHTIG:
        - Gib NUR die Werte zurück, die zu diesen spezifischen Labels gehören
        - Achte auf das korrekte Format: #.###,## (mit Punkt als Tausendertrennzeichen)
        - Gib "0" zurück, wenn du einen Wert nicht sicher identifizieren kannst

        Gib deine Funde als JSON zurück:
        {
        "found_in_bottom_right": {
            "employee_name": "unknown",
            "gross_amount": "Bruttogehalt oder '0'",
            "net_amount": "Nettogehalt oder '0'"
        }
        }
        """,
        
        # Bottom-left of page 2 - look for supervisor information with custom structure
        "bottom_left": """
        Du siehst den unteren linken Bereich auf Seite 2 des Dokuments.

        AUFGABE: Suche nach Informationen über einen Vorgesetzten oder Supervisor.
        WICHTIG: 
        - Achte auf Bezeichnungen wie "Supervisor:", "Vorgesetzter:", "Manager:" oder ähnliche Kennzeichnungen.
        - IGNORIERE KOMPLETT alle Informationen über Mitarbeiter, Gehälter oder andere Personen.
        - Konzentriere dich AUSSCHLIESSLICH auf Vorgesetzte/Manager-Informationen.
        
        Gib den gefundenen Namen und weitere Informationen in diesem JSON-FORMAT zurück:
        {
          "found_in_bottom_left": {
            "supervisor_name": "Name des Vorgesetzten oder 'nicht gefunden'",
            "supervisor_position": "Position des Vorgesetzten oder 'unbekannt'",
            "supervisor_contact": "Kontaktinformationen des Vorgesetzten oder 'unbekannt'"
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
            all_results.extend(first_page_result["results"])
        if "total_pages" in first_page_result:
            total_pages = first_page_result["total_pages"]
        processed_pages += 1
        
        # Force memory cleanup between pages for extra safety
        force_memory_cleanup()
        
        # Process second page
        second_page_result = processor.process_pdf(pdf_bytes, pages=[2])
        if "results" in second_page_result and len(second_page_result["results"]) > 0:
            # Post-process page 2 results to properly format supervisor information
            for page_result in second_page_result["results"]:
                # Check for supervisor information directly from the model's response
                if "found_in_bottom_left" in page_result:
                    supervisor_data = page_result["found_in_bottom_left"]
                    
                    # If supervisor fields are present in the direct model output
                    if "supervisor_name" in supervisor_data:
                        # Add formatted supervisor information for easier access
                        page_result["supervisor_info"] = {
                            "name": supervisor_data.get("supervisor_name", "nicht gefunden"),
                            "position": supervisor_data.get("supervisor_position", "unbekannt"),
                            "contact": supervisor_data.get("supervisor_contact", "unbekannt")
                        }
                
            # Add results to the combined list
            all_results.extend(second_page_result["results"])
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
    
    # Create combined result
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
    
    # Return results and filename
    return jsonify({
        'status': 'success',
        'filename': file.filename,
        'processing_time': processing_time,
        'result': result
    })

if __name__ == '__main__':
    app.run(debug=True)