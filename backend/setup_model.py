#!/usr/bin/env python
"""
Setup script for downloading and caching the Qwen2.5-VL-7B model.
Run this script once before starting the application to avoid downloading
the model files every time the application runs.
"""

import os
import sys
import logging
import yaml
import torch
from transformers import AutoProcessor, AutoModelForImageTextToText
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_config():
    """Load configuration from YAML file"""
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'config.yml')
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            logger.info(f"Loaded configuration from {config_path}")
            return config
    except Exception as e:
        logger.error(f"Error loading configuration: {str(e)}")
        # Use default configuration
        logger.info("Using default configuration")
        return {
            "model": {
                "id": "Qwen/Qwen2.5-VL-7B-Instruct",
                "memory_limit_gb": 0,
                "use_float32": False,
                "use_cpu_offload": False
            }
        }

def download_and_cache_model():
    """Download and cache the Qwen model"""
    logger.info("Starting model download and caching process...")
    
    # Load configuration
    config = load_config()
    model_id = config["model"]["id"]
    
    # Check available resources
    if torch.cuda.is_available():
        logger.info(f"CUDA available: {torch.cuda.is_available()}")
        logger.info(f"CUDA device: {torch.cuda.get_device_name(0)}")
        logger.info(f"CUDA memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
    else:
        logger.info("CUDA not available, using CPU")
    
    # Set explicit cache directory - use a local directory in the project for maximum reliability
    cache_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'model_cache'))
    os.makedirs(cache_dir, exist_ok=True)
    
    # Override the environment variable to ensure consistency
    os.environ["TRANSFORMERS_CACHE"] = cache_dir
    logger.info(f"Setting TRANSFORMERS_CACHE to {cache_dir}")
    
    logger.info(f"Using cache directory: {cache_dir}")
    
    # Required model files to check for
    required_files = [
        f"models--{model_id.replace('/', '--')}/snapshots",
        f"models--{model_id.replace('/', '--')}/blobs/model-00001-of-00005.safetensors",
        f"models--{model_id.replace('/', '--')}/blobs/model-00002-of-00005.safetensors",
        f"models--{model_id.replace('/', '--')}/blobs/model-00003-of-00005.safetensors",
        f"models--{model_id.replace('/', '--')}/blobs/model-00004-of-00005.safetensors",
        f"models--{model_id.replace('/', '--')}/blobs/model-00005-of-00005.safetensors"
    ]
    
    # Check if all required files exist
    all_files_exist = True
    for file_path in required_files:
        full_path = os.path.join(cache_dir, file_path)
        if not os.path.exists(full_path):
            logger.warning(f"Missing required file: {full_path}")
            all_files_exist = False
            break
    
    if all_files_exist:
        logger.info("All required model files found in cache.")
        # Create a marker file that qwen_processor.py can check for
        with open(os.path.join(cache_dir, "QWEN_MODEL_READY"), "w") as f:
            f.write("Model is ready for use")
        return True
    
    # If any files are missing, do a full download
    logger.info("Some required model files are missing. Starting full download...")
    
    try:
        # Download and cache the processor
        logger.info(f"Downloading and caching processor for {model_id}...")
        processor = AutoProcessor.from_pretrained(
            model_id, 
            cache_dir=cache_dir,
            local_files_only=False  # Force download
        )
        
        # Save processor explicitly to disk
        logger.info("Saving processor to disk...")
        processor_path = os.path.join(cache_dir, "processor")
        os.makedirs(processor_path, exist_ok=True)
        processor.save_pretrained(processor_path)
        
        # Download and cache the model
        logger.info(f"Downloading and caching model {model_id}...")
        torch_dtype = torch.float16 if not config["model"]["use_float32"] else torch.float32
        model = AutoModelForImageTextToText.from_pretrained(
            model_id,
            torch_dtype=torch_dtype,
            device_map="auto",
            cache_dir=cache_dir,
            local_files_only=False  # Force download
        )
        
        # Save model explicitly to disk
        logger.info("Saving model to disk...")
        model_path = os.path.join(cache_dir, "model")
        os.makedirs(model_path, exist_ok=True)
        model.save_pretrained(model_path)
        
        # Create a marker file that qwen_processor.py can check for
        with open(os.path.join(cache_dir, "QWEN_MODEL_READY"), "w") as f:
            f.write("Model is ready for use")
        
        # Verify all files now exist
        all_files_exist = True
        for file_path in required_files:
            full_path = os.path.join(cache_dir, file_path)
            if not os.path.exists(full_path):
                logger.warning(f"Still missing required file after download: {full_path}")
                all_files_exist = False
                break
        
        if all_files_exist:
            logger.info("All model files successfully downloaded and verified.")
        else:
            logger.warning("Some model files are still missing. Please run this script again.")
        
        logger.info(f"Model cached at: {cache_dir}")
        return all_files_exist
    
    except Exception as e:
        logger.error(f"Error downloading and caching model: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("Model setup script starting...")
    
    success = download_and_cache_model()
    
    if success:
        logger.info("Setup completed successfully!")
        logger.info("You can now start the application without waiting for model downloads.")
        sys.exit(0)
    else:
        logger.error("Setup failed! Please check the logs for details.")
        sys.exit(1) 