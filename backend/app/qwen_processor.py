"""
Qwen Vision-Language Model Processor for Document Extraction
This module adapts the Qwen2.5-VL-7B sliding window OCR implementation
to work with our FastAPI backend structure via Docker container.
"""

import os
import json
import re
import yaml
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Union, Any

from .docker_client import QwenDockerClient

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QwenVLProcessor:
    """Processes documents using Qwen2.5-VL-7B vision-language model with Docker container API"""
    
    def __init__(self, config_path=None, document_type="payslip"):
        """Initialize the QwenVLProcessor with configuration
        
        Args:
            config_path (str, optional): Path to the config file. If None, uses default path.
            document_type (str, optional): Type of document to process ('payslip' or 'property').
                Determines which config file to load.
        """
        self.document_type = document_type
        
        # Set default config path based on document type if not provided
        if not config_path:
            # Use os.path for better cross-platform compatibility
            if document_type == "property":
                config_path = os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config_property.yml'))
            else:  # default to payslip
                config_path = os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config_payslip.yml'))
        
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Initialize Docker client
        docker_config = self.config.get("docker", {})
        self.docker_client = QwenDockerClient(
            host=docker_config.get("host", "localhost"),
            port=docker_config.get("port", 27842),
            timeout=docker_config.get("timeout", 30)
        )
        logger.info(f"Using Docker container for Qwen model processing with document type: {document_type}")
    
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
        # Default configuration varies by document type
        if self.document_type == "property":
            return {
                "docker": {
                    "host": "localhost",
                    "port": 27842,
                    "timeout": 30
                },
                "processing": {
                    "mode": "docker",
                    "window_mode": "whole",
                    "selected_windows": [],
                    "force_cpu": False
                },
                "pdf": {
                    "dpi": 600
                },
                "image": {
                    "resolution_steps": [1500, 1200, 1000, 800]
                }
            }
        else:  # default to payslip
            return {
                "docker": {
                    "host": "localhost",
                    "port": 27842,
                    "timeout": 30
                },
                "processing": {
                    "mode": "docker",
                    "window_mode": "quadrant",
                    "selected_windows": ["top_left", "bottom_right"],
                    "force_cpu": False
                },
                "pdf": {
                    "dpi": 600
                },
                "image": {
                    "resolution_steps": [1500, 1200, 1000, 800]
                }
            }
    
    def is_container_running(self):
        """Check if the Docker container is running"""
        return self.docker_client.is_container_running()
    
    def _get_custom_prompts_for_windows(self):
        """Get custom prompts for the selected windows based on configuration"""
        window_mode = self.config.get("processing", {}).get("window_mode", "quadrant")
        selected_windows = self.config.get("processing", {}).get("selected_windows", [])
        prompts = self.config.get("prompts", {})
        
        # Get the specific prompts for this window mode
        mode_prompts = prompts.get(window_mode, {})
        
        # If no mode-specific prompts are found, but we have prompts for default modes, log a warning
        if not mode_prompts and prompts:
            # Find first available prompt type
            available_modes = list(prompts.keys())
            if available_modes:
                logger.warning(f"No prompts found for window_mode '{window_mode}', but found prompts for modes: {available_modes}")
                logger.warning(f"Please ensure 'window_mode' in config matches the prompt types. Using default mode.")
                
                # Use first available mode as fallback
                window_mode = available_modes[0]
                mode_prompts = prompts.get(window_mode, {})
                
                # Update window mode in config to match prompts
                if "processing" in self.config:
                    self.config["processing"]["window_mode"] = window_mode
                    logger.warning(f"Updated window_mode to '{window_mode}' to match available prompts")

        # If no windows are selected, use all available windows for that mode
        if not selected_windows:
            if window_mode == "vertical":
                selected_windows = ["top", "bottom"]
            elif window_mode == "horizontal":
                selected_windows = ["left", "right"]
            elif window_mode == "quadrant":
                selected_windows = ["top_left", "top_right", "bottom_left", "bottom_right"]
            elif window_mode == "whole":
                selected_windows = ["whole"]
            
            # Update selected windows in config
            if "processing" in self.config:
                self.config["processing"]["selected_windows"] = selected_windows
                logger.info(f"No windows selected, using all available for mode '{window_mode}': {selected_windows}")
        
        # Validate that selected windows are valid for the window mode
        valid_windows = {
            "vertical": ["top", "bottom"],
            "horizontal": ["left", "right"],
            "quadrant": ["top_left", "top_right", "bottom_left", "bottom_right"],
            "whole": ["whole"]
        }
        
        valid_for_mode = valid_windows.get(window_mode, [])
        invalid_selections = [w for w in selected_windows if w not in valid_for_mode]
        
        if invalid_selections:
            logger.warning(f"Invalid window selections {invalid_selections} for mode '{window_mode}'. Valid options are: {valid_for_mode}")
            # Filter to only valid selections
            selected_windows = [w for w in selected_windows if w in valid_for_mode]
            
            # If no valid selections remain, use all valid windows
            if not selected_windows:
                selected_windows = valid_for_mode
                logger.warning(f"No valid selections for mode '{window_mode}', using all: {selected_windows}")
            
            # Update selected windows in config
            if "processing" in self.config:
                self.config["processing"]["selected_windows"] = selected_windows
        
        # Create a dictionary of custom prompts for selected windows
        custom_prompts = {}
        for window in selected_windows:
            if window in mode_prompts:
                custom_prompts[window] = mode_prompts[window]
            else:
                logger.warning(f"No prompt found for window '{window}' in mode '{window_mode}'")
        
        return custom_prompts
    
    def _convert_german_number_format(self, value):
        """Convert German number format (comma as decimal separator) to float"""
        if not value or not isinstance(value, str):
            return 0.0
        
        # Remove any non-numeric chars except comma and period
        clean_value = re.sub(r'[^\d,.]', '', value)
        
        # Replace comma with period for decimal
        clean_value = clean_value.replace(',', '.')
        
        # If multiple periods, keep only the last one
        parts = clean_value.split('.')
        if len(parts) > 2:
            clean_value = ''.join(parts[:-1]) + '.' + parts[-1]
        
        try:
            return float(clean_value)
        except ValueError:
            return 0.0
    
    def _extract_from_response(self, response_data):
        """Extract standardized fields from the container response based on document type"""
        try:
            if self.document_type == "property":
                return self._extract_property_data(response_data)
            else:
                return self._extract_payslip_data(response_data)
        except Exception as e:
            logger.error(f"Error extracting data from response: {e}")
            if self.document_type == "property":
                return {
                    "living_space": "nicht gefunden",
                    "purchase_price": "nicht gefunden",
                    "raw_output": response_data
                }
            else:
                return {
                    "employee": {
                        "name": "unknown"
                    },
                    "payment": {
                        "gross": "0",
                        "net": "0"
                    },
                    "raw_output": response_data
                }
    
    def _extract_payslip_data(self, response_data):
        """Extract payslip data from the model response"""
        # Initialize with default values
        extracted = {
            "employee": {
                "name": "unknown"
            },
            "payment": {
                "gross": "0",
                "net": "0"
            },
            "raw_output": response_data
        }
        
        # Process the results based on the window mode
        results = response_data.get("results", [])
        
        # Extract data from different window sections
        employee_name = None
        gross_amount = None
        net_amount = None
        
        # Check all result objects
        for result in results:
            # Process each result key (could be found_in_top_left, found_in_whole, etc.)
            for key, data in result.items():
                # Only process dictionary values that match our expected pattern
                if isinstance(data, dict):
                    # Check for employee name
                    if "employee_name" in data and (employee_name is None or employee_name == "unknown"):
                        if data["employee_name"] and data["employee_name"].lower() != "unknown":
                            employee_name = data["employee_name"]
                    
                    # Check for gross amount
                    if "gross_amount" in data and (gross_amount is None or gross_amount == "0"):
                        if data["gross_amount"] and data["gross_amount"] != "0":
                            gross_amount = data["gross_amount"]
                    
                    # Check for net amount
                    if "net_amount" in data and (net_amount is None or net_amount == "0"):
                        if data["net_amount"] and data["net_amount"] != "0":
                            net_amount = data["net_amount"]
            
            # For backwards compatibility, also check for direct keys at result level
            if "employee_name" in result and (employee_name is None or employee_name == "unknown"):
                if result["employee_name"] and result["employee_name"].lower() != "unknown":
                    employee_name = result["employee_name"]
                
            # Check for gross amount
            if "gross_amount" in result and (gross_amount is None or gross_amount == "0"):
                if result["gross_amount"] and result["gross_amount"] != "0":
                    gross_amount = result["gross_amount"]
            
            # Check for net amount
            if "net_amount" in result and (net_amount is None or net_amount == "0"):
                if result["net_amount"] and result["net_amount"] != "0":
                    net_amount = result["net_amount"]
        
        # Update the extracted data if values were found
        if employee_name:
            extracted["employee"]["name"] = employee_name
        
        if gross_amount:
            extracted["payment"]["gross"] = gross_amount
        
        if net_amount:
            extracted["payment"]["net"] = net_amount
            
        return extracted
    
    def _extract_property_data(self, response_data):
        """Extract property listing data from the model response"""
        # Initialize with default values
        extracted = {
            "living_space": "nicht gefunden",
            "purchase_price": "nicht gefunden",
            "raw_output": response_data
        }
        
        # Process the results
        results = response_data.get("results", [])
        
        # Check all result objects
        for result in results:
            # First check for found_in_whole format (standard response from whole mode)
            if "found_in_whole" in result:
                property_data = result["found_in_whole"]
                
                if "living_space" in property_data and property_data["living_space"] != "nicht gefunden":
                    extracted["living_space"] = property_data["living_space"]
                
                if "purchase_price" in property_data and property_data["purchase_price"] != "nicht gefunden":
                    extracted["purchase_price"] = property_data["purchase_price"]
                    
            # For backwards compatibility, also check legacy property_* formats
            property_keys = ["property_whole", "property_top", "property_bottom"]
            
            for key in property_keys:
                if key in result:
                    property_data = result[key]
                    
                    if "living_space" in property_data and property_data["living_space"] != "nicht gefunden":
                        extracted["living_space"] = property_data["living_space"]
                    
                    if "purchase_price" in property_data and property_data["purchase_price"] != "nicht gefunden":
                        extracted["purchase_price"] = property_data["purchase_price"]
        
        return extracted
    
    def _process_window_with_custom_prompt(self, window, position, prompt):
        """Process a window with a custom prompt - used for property listings"""
        try:
            # Use Docker client to process the window
            return self.docker_client.process_window_with_prompt(window, prompt)
        except Exception as e:
            logger.error(f"Error processing window with custom prompt: {e}")
            return {}
    
    def convert_pdf_to_images(self, pdf_bytes):
        """Convert PDF to images using the Docker container"""
        return self.docker_client.convert_pdf_to_images(pdf_bytes)
    
    def split_image_for_sliding_window(self, image):
        """Split image for sliding window processing"""
        return self.docker_client.split_image_for_sliding_window(image, 
                                                              self.config.get("processing", {}).get("window_mode", "quadrant"))
    
    def process_pdf_file(self, pdf_bytes, file_name=None):
        """Process a PDF file to extract data using the Docker container"""
        logger.info(f"Processing PDF with Docker container for document type: {self.document_type}")
        
        try:
            # Extract all configuration parameters from the config file
            processing_config = self.config.get("processing", {})
            pdf_config = self.config.get("pdf", {})
            image_config = self.config.get("image", {})
            window_config = self.config.get("window", {})
            text_generation_config = self.config.get("text_generation", {})
            extraction_config = self.config.get("extraction", {})
            global_config = self.config.get("global", {})
            
            # Get any custom prompts from configuration
            custom_prompts = self._get_custom_prompts_for_windows()
            logger.info(f"Using custom prompts for windows: {', '.join(custom_prompts.keys())}")
            
            # Create kwargs dict for all optional parameters
            container_params = {
                # Basic parameters
                "pdf_bytes": pdf_bytes,
                "file_name": file_name,
                "window_mode": processing_config.get("window_mode"),
                "selected_windows": processing_config.get("selected_windows"),
                "custom_prompts": custom_prompts,
                "force_cpu": processing_config.get("force_cpu"),
                "gpu_memory_fraction": processing_config.get("gpu_memory_fraction"),
                "memory_isolation": processing_config.get("memory_isolation"),
                
                # PDF parameters
                "pdf_dpi": pdf_config.get("dpi"),
                
                # Image processing parameters
                "image_resolution_steps": self._validate_resolution_steps(image_config.get("resolution_steps")),
                "image_enhance_contrast": image_config.get("enhance_contrast"),
                "image_sharpen_factor": image_config.get("sharpen_factor"),
                "image_contrast_factor": image_config.get("contrast_factor"),
                "image_brightness_factor": image_config.get("brightness_factor"),
                "image_ocr_language": image_config.get("ocr_language"),
                "image_ocr_threshold": image_config.get("ocr_threshold"),
                
                # Window settings
                "window_overlap": window_config.get("overlap"),
                "window_min_size": window_config.get("min_size"),
                
                # Text generation settings
                "text_generation_max_new_tokens": text_generation_config.get("max_new_tokens"),
                "text_generation_use_beam_search": text_generation_config.get("use_beam_search"),
                "text_generation_num_beams": text_generation_config.get("num_beams"),
                "text_generation_temperature": text_generation_config.get("temperature"),
                "text_generation_top_p": text_generation_config.get("top_p"),
                
                # Extraction settings
                "extraction_confidence_threshold": extraction_config.get("confidence_threshold"),
                "extraction_fuzzy_matching": extraction_config.get("fuzzy_matching"),
                
                # Global settings
                "global_mode": global_config.get("mode"),
                "global_prompt": global_config.get("prompt"),
                "global_selected_windows": global_config.get("selected_windows")
            }
            
            # Filter out None values to avoid sending unnecessary parameters
            container_params = {k: v for k, v in container_params.items() if v is not None}
            
            # Process with Docker container
            response = self.docker_client.process_pdf(**container_params)
            
            # Extract standardized fields
            return self._extract_from_response(response)
            
        except Exception as e:
            logger.error(f"Error processing PDF: {e}")
            raise
    
    # Alias for backward compatibility
    process_pdf = process_pdf_file
    
    def process_pdf_with_pages(self, pdf_bytes, file_name=None, pages=None, selected_windows=None, override_global_settings=None):
        """
        Process specific pages of a PDF with page-specific configurations
        
        Args:
            pdf_bytes: PDF file content as bytes
            file_name: Name of the file (optional)
            pages: List of page numbers to process (1-indexed)
            selected_windows: List or string of specific windows to use (overrides config)
            override_global_settings: When "true", forces the selected_windows to override global settings
            
        Returns:
            Dict containing extracted data
        """
        logger.info(f"Processing PDF with page-specific configurations. Pages: {pages}")
        
        try:
            # Extract all configuration parameters from the config file
            processing_config = self.config.get("processing", {})
            pdf_config = self.config.get("pdf", {})
            image_config = self.config.get("image", {})
            window_config = self.config.get("window", {})
            text_generation_config = self.config.get("text_generation", {})
            extraction_config = self.config.get("extraction", {})
            global_config = self.config.get("global", {})
            page_configs = self.config.get("pages", {})
            
            # Get custom prompts from configuration
            custom_prompts = self._get_custom_prompts_for_windows()
            
            # Create kwargs dict for all optional parameters
            container_params = {
                # Core parameters
                "pdf_bytes": pdf_bytes,
                "file_name": file_name,
                "pages": pages,
                "page_configs": page_configs,
                
                # Window and processing parameters
                "window_mode": global_config.get("mode") or processing_config.get("window_mode"),
                # Use explicitly provided selected_windows parameter if available
                "selected_windows": selected_windows or global_config.get("selected_windows") or processing_config.get("selected_windows"),
                "custom_prompts": custom_prompts,
                "force_cpu": global_config.get("force_cpu") or processing_config.get("force_cpu"),
                "gpu_memory_fraction": global_config.get("gpu_memory_fraction") or processing_config.get("gpu_memory_fraction"),
                "memory_isolation": processing_config.get("memory_isolation"),
                
                # Add override_global_settings parameter if provided
                "override_global_settings": override_global_settings,
                
                # PDF parameters
                "pdf_dpi": pdf_config.get("dpi"),
                
                # Image processing parameters
                "image_resolution_steps": self._validate_resolution_steps(image_config.get("resolution_steps")),
                "image_enhance_contrast": image_config.get("enhance_contrast"),
                "image_sharpen_factor": image_config.get("sharpen_factor"),
                "image_contrast_factor": image_config.get("contrast_factor"),
                "image_brightness_factor": image_config.get("brightness_factor"),
                "image_ocr_language": image_config.get("ocr_language"),
                "image_ocr_threshold": image_config.get("ocr_threshold"),
                
                # Window settings
                "window_overlap": window_config.get("overlap"),
                "window_min_size": window_config.get("min_size"),
                
                # Text generation settings
                "text_generation_max_new_tokens": text_generation_config.get("max_new_tokens"),
                "text_generation_use_beam_search": text_generation_config.get("use_beam_search"),
                "text_generation_num_beams": text_generation_config.get("num_beams"),
                "text_generation_temperature": text_generation_config.get("temperature"),
                "text_generation_top_p": text_generation_config.get("top_p"),
                
                # Extraction settings
                "extraction_confidence_threshold": extraction_config.get("confidence_threshold"),
                "extraction_fuzzy_matching": extraction_config.get("fuzzy_matching"),
                
                # Global settings
                "global_mode": global_config.get("mode"),
                "global_prompt": global_config.get("prompt"),
                "global_selected_windows": global_config.get("selected_windows")
            }
            
            # Filter out None values to avoid sending unnecessary parameters
            container_params = {k: v for k, v in container_params.items() if v is not None}
            
            # Process with Docker container with page specifications
            response = self.docker_client.process_pdf(**container_params)
            
            # Extract standardized fields
            result = self._extract_from_response(response)
            
            # Add page processing info to result
            result["page_processing"] = {
                "pages_requested": pages,
                "pages_processed": response.get("processed_pages", 0),
                "total_pages": response.get("total_pages", 0)
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing PDF with pages: {e}")
            raise
    
    def process_image_file(self, image_bytes):
        """Process an image file to extract data using the Docker container"""
        logger.info(f"Processing image with Docker container for document type: {self.document_type}")
        
        try:
            # Extract all configuration parameters from the config file
            processing_config = self.config.get("processing", {})
            image_config = self.config.get("image", {})
            window_config = self.config.get("window", {})
            text_generation_config = self.config.get("text_generation", {})
            extraction_config = self.config.get("extraction", {})
            global_config = self.config.get("global", {})
            
            # Get any custom prompts from configuration
            custom_prompts = self._get_custom_prompts_for_windows()
            logger.info(f"Using custom prompts for windows: {', '.join(custom_prompts.keys())}")
            
            # Create kwargs dict for all optional parameters
            container_params = {
                # Core parameters
                "image_bytes": image_bytes,
                "window_mode": processing_config.get("window_mode"),
                "selected_windows": processing_config.get("selected_windows"),
                "custom_prompts": custom_prompts,
                "force_cpu": processing_config.get("force_cpu"),
                "gpu_memory_fraction": processing_config.get("gpu_memory_fraction"),
                "memory_isolation": processing_config.get("memory_isolation"),
                
                # Image processing parameters
                "image_resolution_steps": self._validate_resolution_steps(image_config.get("resolution_steps")),
                "image_enhance_contrast": image_config.get("enhance_contrast"),
                "image_sharpen_factor": image_config.get("sharpen_factor"),
                "image_contrast_factor": image_config.get("contrast_factor"),
                "image_brightness_factor": image_config.get("brightness_factor"),
                "image_ocr_language": image_config.get("ocr_language"),
                "image_ocr_threshold": image_config.get("ocr_threshold"),
                
                # Window settings
                "window_overlap": window_config.get("overlap"),
                "window_min_size": window_config.get("min_size"),
                
                # Text generation settings
                "text_generation_max_new_tokens": text_generation_config.get("max_new_tokens"),
                "text_generation_use_beam_search": text_generation_config.get("use_beam_search"),
                "text_generation_num_beams": text_generation_config.get("num_beams"),
                "text_generation_temperature": text_generation_config.get("temperature"),
                "text_generation_top_p": text_generation_config.get("top_p"),
                
                # Extraction settings
                "extraction_confidence_threshold": extraction_config.get("confidence_threshold"),
                "extraction_fuzzy_matching": extraction_config.get("fuzzy_matching"),
                
                # Global settings
                "global_mode": global_config.get("mode"),
                "global_prompt": global_config.get("prompt"),
                "global_selected_windows": global_config.get("selected_windows")
            }
            
            # Filter out None values to avoid sending unnecessary parameters
            container_params = {k: v for k, v in container_params.items() if v is not None}
            
            # Process with Docker container
            response = self.docker_client.process_image(**container_params)
            
            # Extract standardized fields
            return self._extract_from_response(response)
            
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            raise

    def _validate_resolution_steps(self, resolution_steps):
        """Validate resolution steps and ensure they are in the correct format
        
        Args:
            resolution_steps: Resolution steps from configuration
            
        Returns:
            List[int]: Valid resolution steps
        """
        # If None, return None
        if resolution_steps is None:
            return None
            
        # If already a list, ensure all values are integers
        if isinstance(resolution_steps, list):
            try:
                # Convert all values to integers
                return [int(step) for step in resolution_steps]
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid resolution_steps values: {resolution_steps}. Using default [600, 400]. Error: {e}")
                return [600, 400]
        
        # If a string, try to parse as comma-separated values
        if isinstance(resolution_steps, str):
            try:
                if ',' in resolution_steps:
                    return [int(s.strip()) for s in resolution_steps.split(',')]
                else:
                    return [int(resolution_steps)]
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid resolution_steps string: {resolution_steps}. Using default [600, 400]. Error: {e}")
                return [600, 400]
                
        # If a single value, convert to a list
        try:
            return [int(resolution_steps)]
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid resolution_steps format: {resolution_steps}. Using default [600, 400]. Error: {e}")
            return [600, 400]

def get_qwen_processor(config_path=None, document_type="payslip"):
    """Factory function to get a QwenVLProcessor instance
    
    Args:
        config_path (str, optional): Path to config file. If None, uses default based on document_type.
        document_type (str, optional): Type of document to process ('payslip' or 'property').
    
    Returns:
        QwenVLProcessor: Configured processor instance
    """
    return QwenVLProcessor(config_path, document_type) 