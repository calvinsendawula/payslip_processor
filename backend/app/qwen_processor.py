"""
Qwen Vision-Language Model Processor for Payslip Extraction
This module adapts the Qwen2.5-VL-7B sliding window OCR implementation
to work with our FastAPI backend structure.
"""

import torch
from transformers import AutoProcessor, AutoModelForImageTextToText
from pdf2image import convert_from_bytes
from PIL import Image
import os
import json
import re
import gc
import yaml
import logging
import matplotlib.pyplot as plt
import time
import io
import base64
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QwenVLProcessor:
    """Processes payslips using Qwen2.5-VL-7B vision-language model with sliding window approach"""
    
    def __init__(self, config_path=None):
        """Initialize the QwenVLProcessor with configuration"""
        # Set default config path relative to this file if not provided
        if not config_path:
            # Use os.path for better cross-platform compatibility
            config_path = os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yml'))
        
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Set device
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Using device: {self.device}")
        
        # Configure PyTorch for better memory management
        if torch.cuda.is_available():
            # Enable memory optimizations
            torch.cuda.empty_cache()
            # Set PyTorch to release memory more aggressively
            os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
        
        # Load model and processor (initialize them as None until needed)
        self.model = None
        self.processor = None
    
    def _load_config(self, config_path):
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                logger.info(f"Loaded configuration from {config_path}")
                return config
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            # Use default configuration
            logger.info("Using default configuration")
            return self._get_default_config()
    
    def _get_default_config(self):
        """Return default configuration if YAML file cannot be loaded"""
        return {
            "model": {
                "id": "Qwen/Qwen2.5-VL-7B-Instruct",
                "memory_limit_gb": 0,
                "use_float32": False,
                "use_cpu_offload": False
            },
            "pdf": {
                "dpi": 600
            },
            "image": {
                "initial_resolution": 1500,
                "resolution_steps": [1500, 1200, 1000, 800, 600],
                "enhance_contrast": True,
                "use_advanced_preprocessing": True,
                "sharpen_factor": 2.5,
                "contrast_factor": 1.8,
                "brightness_factor": 1.1
            },
            "sliding_window": {
                "enabled": True,
                "window_count": 2,
                "window_overlap": 0.1
            },
            "text_generation": {
                "max_new_tokens": 768,
                "use_beam_search": False,
                "num_beams": 1,
                "auto_process_results": True
            }
        }
    
    def _load_model(self):
        """Load the Qwen2.5-VL-7B model and processor"""
        if self.model is not None and self.processor is not None:
            return  # Model already loaded
        
        logger.info("Loading Qwen2.5-VL-7B-Instruct model...")
        
        try:
            # Initial memory cleanup
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                gc.collect()
            
            # Load model and processor
            model_id = self.config["model"]["id"]
            
            # Use local project model cache directory
            cache_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'model_cache'))
            
            # Set environment variable for consistency
            os.environ["TRANSFORMERS_CACHE"] = cache_dir
            
            # Check for our ready marker file
            model_ready = os.path.exists(os.path.join(cache_dir, "QWEN_MODEL_READY"))
            
            if model_ready:
                logger.info(f"Model files found and ready in: {cache_dir}")
                local_files_only = True
            else:
                logger.warning(f"Model files not found in {cache_dir}. Please run setup_model.py first.")
                logger.warning("Attempting to load from the Hugging Face hub (this will be slow)...")
                local_files_only = False
            
            # Try loading from our saved explicit locations first
            try:
                explicit_model_path = os.path.join(cache_dir, "model")
                explicit_processor_path = os.path.join(cache_dir, "processor")
                
                if os.path.exists(explicit_processor_path) and os.path.exists(explicit_model_path):
                    logger.info(f"Loading processor from: {explicit_processor_path}")
                    self.processor = AutoProcessor.from_pretrained(explicit_processor_path)
                    
                    logger.info(f"Loading model from: {explicit_model_path}")
                    self.model = AutoModelForImageTextToText.from_pretrained(
                        explicit_model_path,
                        torch_dtype=torch.float16 if not self.config["model"]["use_float32"] else torch.float32,
                        device_map="auto"
                    )
                    
                    logger.info("Model loaded successfully from local saved files!")
                    return
            except Exception as e:
                logger.warning(f"Failed to load from explicit saved paths: {e}")
                logger.warning("Falling back to cache directory...")
            
            # Load processor
            try:
                self.processor = AutoProcessor.from_pretrained(
                    model_id,
                    cache_dir=cache_dir,
                    local_files_only=local_files_only
                )
            except Exception as e:
                if local_files_only:
                    logger.warning(f"Failed to load processor with local_files_only=True: {e}")
                    logger.info("Retrying without local_files_only restriction")
                    self.processor = AutoProcessor.from_pretrained(
                        model_id,
                        cache_dir=cache_dir,
                        local_files_only=False
                    )
                else:
                    raise
            
            # Load model with memory optimization settings
            try:
                self.model = AutoModelForImageTextToText.from_pretrained(
                    model_id,
                    torch_dtype=torch.float16 if not self.config["model"]["use_float32"] else torch.float32,
                    device_map="auto",
                    cache_dir=cache_dir,
                    local_files_only=local_files_only
                )
            except Exception as e:
                if local_files_only:
                    logger.warning(f"Failed to load model with local_files_only=True: {e}")
                    logger.info("Retrying without local_files_only restriction")
                    self.model = AutoModelForImageTextToText.from_pretrained(
                        model_id,
                        torch_dtype=torch.float16 if not self.config["model"]["use_float32"] else torch.float32,
                        device_map="auto",
                        cache_dir=cache_dir,
                        local_files_only=False
                    )
                else:
                    raise
            
            logger.info("Model loaded successfully!")
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            raise
    
    def convert_pdf_to_images(self, pdf_bytes):
        """Convert PDF bytes to images with configured DPI for quality vs memory"""
        dpi = self.config["pdf"]["dpi"]
        logger.info(f"Converting PDF to images with {dpi} DPI...")
        
        try:
            images = convert_from_bytes(pdf_bytes, dpi=dpi)
            logger.info(f"Converted {len(images)} pages from PDF")
            return images
        except Exception as e:
            logger.error(f"Error converting PDF to images: {e}")
            raise
    
    def optimize_image_for_vl_model(self, image, target_long_side):
        """Optimize image for vision-language model while preserving aspect ratio and readability"""
        # Calculate the scaling factor
        long_side = max(image.width, image.height)
        scale_factor = target_long_side / long_side
        
        # Resize while maintaining aspect ratio
        new_width = int(image.width * scale_factor)
        new_height = int(image.height * scale_factor)
        
        # Ensure dimensions are even
        if new_width % 2 == 1:
            new_width += 1
        if new_height % 2 == 1:
            new_height += 1
        
        # Apply image enhancement if enabled
        if self.config["image"]["use_advanced_preprocessing"]:
            try:
                # Apply contrast enhancement
                from PIL import ImageEnhance
                enhancer = ImageEnhance.Contrast(image)
                image = enhancer.enhance(self.config["image"]["contrast_factor"])
                
                # Apply brightness adjustment
                enhancer = ImageEnhance.Brightness(image)
                image = enhancer.enhance(self.config["image"]["brightness_factor"])
                
                # Apply sharpening
                enhancer = ImageEnhance.Sharpness(image)
                image = enhancer.enhance(self.config["image"]["sharpen_factor"])
            except ImportError:
                pass
        
        # Resize image with high-quality interpolation - handle both old and new Pillow versions
        try:
            # For newer Pillow versions
            resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        except AttributeError:
            # For older Pillow versions
            resized_image = image.resize((new_width, new_height), Image.LANCZOS)
        
        logger.info(f"Resized image from {image.width}x{image.height} to {new_width}x{new_height}")
        return resized_image
    
    def split_image_for_sliding_window(self, image):
        """Split the image into multiple windows for processing"""
        width, height = image.size
        
        # Get window configuration
        num_windows = self.config["sliding_window"]["window_count"]
        overlap = self.config["sliding_window"]["window_overlap"]
        
        # We're splitting vertically (top/bottom)
        window_height = int(height / (num_windows - ((num_windows-1) * overlap)))
        overlap_pixels = int(window_height * overlap)
        
        windows = []
        
        for i in range(num_windows):
            # Calculate window coordinates
            top = i * (window_height - overlap_pixels) if i > 0 else 0
            bottom = top + window_height
            
            # Ensure bottom doesn't exceed image height
            if bottom > height:
                bottom = height
            
            # Crop and append window
            window = image.crop((0, top, width, bottom))
            windows.append(window)
            
            logger.info(f"Created window {i+1}: Dimensions {window.size[0]}x{window.size[1]}, Region y={top}-{bottom}")
        
        return windows
    
    def extract_data_from_window_progressive(self, window, window_position):
        """Extract data from a window using progressive resolution reduction to handle memory constraints"""
        # Make sure model is loaded
        self._load_model()
        
        # Clear CUDA cache before processing
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            gc.collect()
        
        # Print memory status
        if torch.cuda.is_available():
            logger.info(f"GPU memory before processing window {window_position}: {torch.cuda.memory_allocated() / 1e9:.2f} GB allocated")
        
        # Create prompts specific to each window section and what to look for
        if window_position == "top":
            prompt_text = """Du siehst die obere Hälfte einer deutschen Gehaltsabrechnung.

            SUCHE PRÄZISE NACH: Dem Namen des Angestellten, der direkt nach der Überschrift "Herrn/Frau" steht.
            SCHAUE IN DIESEM BEREICH: Im oberen linken Viertel des Dokuments, meist unter dem Label "Herrn/Frau".
            POSITION: Der Name steht 3-4 Zeilen unter der Personalnummer.

            WICHTIG: Wenn du keinen Namen findest, gib "unknown" zurück.
            Ich brauche KEINEN Namen einer Firma oder einer Krankenversicherung, nur den Namen des Angestellten.

            Gib deinen Fund als JSON zurück:
            {
            "found_in_top": {
                "employee_name": "Name des Angestellten oder 'unknown'",
                "gross_amount": "0",
                "net_amount": "0"
            }
            }"""
        else:  # bottom
            prompt_text = """Du siehst die untere Hälfte einer deutschen Gehaltsabrechnung.

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
            "found_in_bottom": {
                "employee_name": "unknown",
                "gross_amount": "Bruttogehalt oder '0'",
                "net_amount": "Nettogehalt oder '0'"
            }
            }"""
        
        return self._process_window_with_progressive_resolution(window, window_position, prompt_text)
    
    def _process_window_with_custom_prompt(self, window, window_position, prompt_text):
        """Process a window with a custom prompt, using progressive resolution reduction"""
        return self._process_window_with_progressive_resolution(window, window_position, prompt_text)
    
    def _process_window_with_progressive_resolution(self, window, window_position, prompt_text):
        """Core implementation of progressive resolution window processing with a given prompt"""
        # Make sure model is loaded
        self._load_model()
        
        # Clear CUDA cache before processing
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            gc.collect()
        
        # Print memory status
        if torch.cuda.is_available():
            logger.info(f"GPU memory before processing window {window_position}: {torch.cuda.memory_allocated() / 1e9:.2f} GB allocated")
        
        # Get resolution steps from config
        resolution_steps = self.config["image"]["resolution_steps"]
        
        # Try each resolution in sequence until one works
        for resolution in resolution_steps:
            try:
                logger.info(f"Trying {window_position} window with resolution {resolution}...")
                
                # Resize the window to the current resolution step
                processed_window = self.optimize_image_for_vl_model(window, resolution)
                
                # Prepare conversation with window-specific prompting
                conversation = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image"},
                            {"type": "text", "text": prompt_text}
                        ]
                    }
                ]
                
                # Preprocess the inputs
                text_prompt = self.processor.apply_chat_template(conversation, add_generation_prompt=True)
                inputs = self.processor(text=[text_prompt], images=[processed_window], padding=True, return_tensors="pt")
                inputs = inputs.to(self.device)
                
                # Generate output
                with torch.inference_mode():
                    output_ids = self.model.generate(
                        **inputs,
                        max_new_tokens=self.config["text_generation"]["max_new_tokens"],
                        do_sample=False,
                        use_cache=True,
                        num_beams=self.config["text_generation"]["num_beams"]
                    )
                
                # Process the output
                generated_ids = [output_ids[0][inputs.input_ids.shape[1]:]]
                response_text = self.processor.batch_decode(generated_ids, skip_special_tokens=True, clean_up_tokenization_spaces=True)[0]
                
                # Extract JSON from the response
                json_pattern = r'({.*})'
                match = re.search(json_pattern, response_text, re.DOTALL)
                
                if match:
                    json_text = match.group(1)
                    try:
                        window_data = json.loads(json_text)
                        # Add full response for debugging
                        window_data["raw_text"] = response_text
                        logger.info(f"Successfully processed {window_position} window at resolution {resolution}")
                        return window_data
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse JSON from {window_position} window at resolution {resolution}")
                
                # JSON extraction failed, continue to next resolution step
                logger.warning(f"JSON extraction failed at resolution {resolution}, trying next resolution...")
                
                # Clean up memory before next attempt
                torch.cuda.empty_cache()
                gc.collect()
            
            except torch.cuda.OutOfMemoryError as e:
                logger.error(f"OOM error at resolution {resolution}: {e}")
                # Clean up memory before next attempt
                torch.cuda.empty_cache()
                gc.collect()
                continue
            
            except Exception as e:
                logger.error(f"Error at resolution {resolution}: {e}")
                # Clean up memory before next attempt
                torch.cuda.empty_cache()
                gc.collect()
                continue
        
        # If we've tried all resolutions and none worked, return failure
        logger.error(f"All resolution attempts failed for {window_position} window")
        return {"raw_text": f"Failed to process {window_position} window at all resolutions", "extraction_failed": True}
    
    def _convert_german_number_format(self, value):
        """Convert German number format (1.234,56 €) to database format (1234.56)"""
        if not value or value == "0":
            return "0"
        
        # Remove € symbol and whitespace
        value = value.replace("€", "").strip()
        
        # Remove thousand separators (.) and replace decimal comma with point
        value = value.replace(".", "").replace(",", ".")
        
        try:
            # Convert to float and back to string to ensure valid number
            return "{:.2f}".format(float(value))
        except ValueError:
            logger.warning(f"Failed to convert number format: {value}")
            return "0"
    
    def extract_payslip_data_sliding_window(self, image):
        """Extract payslip data using sliding window approach with progressive resolution"""
        logger.info("Using sliding window approach with 2 windows (top/bottom) and progressive resolution...")
        
        # Split the image into windows
        windows = self.split_image_for_sliding_window(image)
        
        # Process each window
        window_results = []
        window_positions = ["top", "bottom"]
        
        for i, window in enumerate(windows):
            position = window_positions[i]
            logger.info(f"\nProcessing {position} window...")
            
            # Extract data from this window using progressive resolution
            window_data = self.extract_data_from_window_progressive(window, position)
            window_results.append((position, window_data))
        
        # Combine results from all windows
        return self.combine_window_results(window_results)
    
    def combine_window_results(self, window_results):
        """Combine results from multiple windows into a single result"""
        logger.info("Combining results from all windows...")
        
        combined_data = {
            "employee": {"name": "unknown"},
            "payment": {"gross": "0", "net": "0"},
            "raw_output": ""
        }
        
        # Process each window's results
        for position, data in window_results:
            combined_data["raw_output"] += f"\n--- {position.upper()} WINDOW EXTRACTION ---\n"
            combined_data["raw_output"] += json.dumps(data, indent=2)
            
            # Check if window has extraction results
            if "extraction_failed" in data:
                continue
            
            # Extract data based on window position
            window_key = f"found_in_{position}"
            if window_key in data:
                window_data = data[window_key]
                
                # Process employee name (from top window)
                if position == "top" and "employee_name" in window_data:
                    employee_name = window_data["employee_name"]
                    if employee_name and employee_name.lower() != "unknown":
                        combined_data["employee"]["name"] = employee_name
                
                # Process payment info (primarily from bottom window)
                if "gross_amount" in window_data and window_data["gross_amount"] not in ["0", "", "unknown"]:
                    # Convert from German format to database format
                    gross_amount = self._convert_german_number_format(window_data["gross_amount"])
                    combined_data["payment"]["gross"] = gross_amount
                
                if "net_amount" in window_data and window_data["net_amount"] not in ["0", "", "unknown"]:
                    # Convert from German format to database format
                    net_amount = self._convert_german_number_format(window_data["net_amount"])
                    combined_data["payment"]["net"] = net_amount
        
        return combined_data
    
    def process_pdf_file(self, pdf_bytes):
        """Process a PDF file and extract payslip data"""
        try:
            # Convert PDF to images
            images = self.convert_pdf_to_images(pdf_bytes)
            
            # Process first page (assuming payslip is on the first page)
            if not images:
                logger.error("No pages found in PDF")
                return None
            
            # Extract data from the first page
            result = self.extract_payslip_data_sliding_window(images[0])
            
            return result
        
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            raise
    
    def process_image_file(self, image_bytes):
        """Process an image file and extract payslip data"""
        try:
            # Open image from bytes
            image = Image.open(io.BytesIO(image_bytes))
            
            # Extract data from image
            result = self.extract_payslip_data_sliding_window(image)
            
            return result
        
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            raise
    
    def unload_model(self):
        """Unload model to free up memory"""
        if self.model is not None:
            del self.model
            self.model = None
        
        if self.processor is not None:
            del self.processor
            self.processor = None
        
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            gc.collect()
        
        logger.info("Model unloaded and memory cleared")


# Create singleton instance for reuse
qwen_processor = None

def get_qwen_processor(config_path=None):
    """Get or create the QwenVLProcessor singleton instance"""
    global qwen_processor
    if qwen_processor is None:
        qwen_processor = QwenVLProcessor(config_path)
    return qwen_processor 