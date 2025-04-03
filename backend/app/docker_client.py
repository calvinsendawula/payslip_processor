import requests
import logging
import socket
import base64
import io
from PIL import Image
import time
import json
import subprocess
import platform
from typing import Dict, List, Optional, Union, Tuple, Any

logger = logging.getLogger(__name__)

class QwenDockerClient:
    """Client for interacting with the Qwen Payslip Processor Docker container"""
    
    def __init__(self, host: str = "localhost", port: int = 27842, timeout: int = 1800, container_name: str = "qwen-payslip-processor", cpu_timeout_multiplier: float = 2.0):
        """Initialize the Docker client
        
        Args:
            host: Hostname or IP where the Docker container is running
            port: Port number exposed by the Docker container
            timeout: HTTP request timeout in seconds (default 1800 seconds = 30 minutes)
            container_name: Name of the Docker container
            cpu_timeout_multiplier: Factor to multiply timeout by when running on CPU
        """
        self.host = host
        self.port = port
        self.base_timeout = timeout  # Store base timeout value
        self.timeout = timeout       # Current timeout value
        self.container_name = container_name
        self.base_url = f"http://{host}:{port}"
        self.cpu_timeout_multiplier = cpu_timeout_multiplier
        
        # Check GPU availability
        self.gpu_info = self._check_gpu_availability()
        
        logger.info(f"Initialized Docker client for {self.base_url} with base timeout {timeout}s")
        if self.gpu_info['available']:
            logger.info(f"GPU detected: {self.gpu_info['name']} - Container may use GPU acceleration")
        else:
            logger.info("No GPU detected or not accessible - Container will use CPU")
            # For CPU, processing might take much longer
            self.timeout = min(self.timeout * self.cpu_timeout_multiplier, 3600)  # Use multiplier from config
            logger.info(f"Increased timeout to {self.timeout}s for CPU-only processing (multiplier: {self.cpu_timeout_multiplier}x)")
        
        # Verify container accessibility at startup
        if not self.is_container_running():
            logger.warning(f"⚠️ Docker container not running at {self.base_url}")
            logger.warning(f"Please ensure the Docker container is running with:")
            
            gpu_flag = "--gpus all " if self.gpu_info['available'] else ""
            logger.warning(f"docker run -d -p {self.port}:{self.port} {gpu_flag}--name {self.container_name} --memory=12g --memory-swap=24g --shm-size=1g calvin189/qwen-payslip-processor:latest")
            
            # Provide WSL config suggestion for Windows users
            if platform.system() == "Windows":
                logger.warning(f"If you encounter memory errors, check your .wslconfig:")
                logger.warning(f"Create %USERPROFILE%\\.wslconfig with settings:")
                logger.warning(f"[wsl2]\nmemory=16GB\nprocessors=8\nswap=32GB\ngpuSupport=true")
        else:
            # Check if container has GPU access
            self._check_container_gpu_status()
    
    def _check_gpu_availability(self) -> Dict[str, Any]:
        """Check if a compatible GPU is available for Docker
        
        Returns:
            Dict with GPU availability information
        """
        gpu_info = {
            'available': False,
            'type': None,
            'name': None,
            'driver': None,
            'error': None
        }
        
        try:
            # Check for NVIDIA GPU
            if platform.system() == "Windows" or platform.system() == "Linux":
                try:
                    # Check if nvidia-smi is available and working
                    result = subprocess.run(
                        ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"], 
                        capture_output=True, 
                        text=True, 
                        timeout=5
                    )
                    
                    if result.returncode == 0 and result.stdout.strip():
                        parts = result.stdout.strip().split(', ')
                        if len(parts) >= 2:
                            gpu_info['available'] = True
                            gpu_info['type'] = 'nvidia'
                            gpu_info['name'] = parts[0]
                            gpu_info['driver'] = parts[1]
                    
                    # Also check if Docker can access the GPU
                    if gpu_info['available']:
                        docker_test = subprocess.run(
                            ["docker", "run", "--rm", "--gpus", "all", "nvidia/cuda:11.0-base", "nvidia-smi"],
                            capture_output=True,
                            timeout=10
                        )
                        if docker_test.returncode != 0:
                            gpu_info['error'] = "NVIDIA GPU detected but Docker cannot access it. Check nvidia-docker setup."
                            # Still available but with warning
                
                except (subprocess.SubprocessError, FileNotFoundError) as e:
                    # nvidia-smi not found or failed
                    gpu_info['error'] = f"Error checking NVIDIA GPU: {str(e)}"
            
            # For macOS, check for Apple Silicon
            elif platform.system() == "Darwin":
                try:
                    result = subprocess.run(
                        ["sysctl", "-n", "machdep.cpu.brand_string"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    if "Apple" in result.stdout:
                        gpu_info['available'] = True
                        gpu_info['type'] = 'apple'
                        gpu_info['name'] = 'Apple Silicon'
                        # Docker Desktop for Mac will use Metal automatically
                
                except (subprocess.SubprocessError, FileNotFoundError) as e:
                    gpu_info['error'] = f"Error checking Apple Silicon: {str(e)}"
            
        except Exception as e:
            gpu_info['error'] = f"Unexpected error checking GPU: {str(e)}"
        
        return gpu_info
    
    def _check_container_gpu_status(self):
        """Check if the container is actually using GPU and log appropriate warnings"""
        try:
            response = requests.get(f"{self.base_url}/status", timeout=5)
            if response.status_code == 200:
                status_data = response.json()
                
                # Check if GPU is expected and being used
                if self.gpu_info['available']:
                    if 'gpu' in status_data and status_data['gpu']:
                        logger.info(f"Container is using GPU acceleration: {status_data.get('gpu_info', 'Unknown GPU')}")
                    else:
                        logger.warning("WARNING: GPU is available on the system but container is running on CPU!")
                        logger.warning("Consider restarting the container with GPU support using the restart_container_with_gpu method")
                else:
                    logger.info("Container is running on CPU (no GPU available on this system)")
        except Exception as e:
            logger.error(f"Error checking container GPU status: {e}")
    
    def verify_gpu_container(self) -> bool:
        """Verify that the container is actually using GPU
        
        Returns:
            bool: True if container is using GPU
        """
        try:
            # Give container more time to initialize for this check
            for _ in range(12):  # Try for up to 60 seconds
                try:
                    response = requests.get(f"{self.base_url}/status", timeout=5)
                    if response.status_code == 200:
                        status_data = response.json()
                        if 'gpu' in status_data and status_data['gpu']:
                            logger.info(f"Verified container is using GPU: {status_data.get('gpu_info', 'Unknown GPU')}")
                            return True
                        elif 'status' in status_data and status_data['status'] == 'ok':
                            # Container is responding but not using GPU
                            logger.warning("Container is responding but not using GPU")
                            return False
                except:
                    pass
                
                logger.info("Waiting for container to initialize...")
                time.sleep(5)
                
            logger.warning("Container didn't report GPU usage within timeout period")
            return False
        except Exception as e:
            logger.error(f"Error verifying GPU container: {e}")
            return False
    
    def _check_container_status(self):
        """Check if Docker container is running
        
        Returns:
            dict: Status information including container running state
        """
        try:
            # Try to access the container status endpoint
            response = requests.get(f"{self.base_url}/status", timeout=5)
            if response.status_code == 200:
                status_data = response.json()
                if status_data.get("status") == "ok":
                    # Container is running and API is responsive
                    logger.info(f"Docker container is running: {status_data}")
                    
                    gpu_status = {
                        "status": "running",  # Always return "running" when container is up
                        "ready": status_data.get("ready", False),
                        "model": status_data.get("model", "unknown"),
                        "version": status_data.get("version", "unknown"),
                        "device": status_data.get("device", "unknown"),
                    }
                    
                    # Check if container was started with GPU support
                    container_id = self._find_container_id()
                    if container_id:
                        try:
                            # Inspect container configuration
                            inspect_result = subprocess.run(
                                ["docker", "inspect", container_id],
                                capture_output=True,
                                text=True,
                                timeout=5
                            )
                            
                            if inspect_result.returncode == 0:
                                container_info = json.loads(inspect_result.stdout)
                                if container_info:
                                    # Check for GPU configuration in container
                                    host_config = container_info[0].get('HostConfig', {})
                                    runtime = host_config.get('Runtime', '')
                                    devices = host_config.get('Devices', [])
                                    
                                    # Container is using GPU if:
                                    # 1. Runtime is nvidia
                                    # 2. Has nvidia devices
                                    # 3. Has GPU in device requests
                                    gpu_status["gpu"] = (
                                        runtime == 'nvidia' or
                                        any('nvidia' in str(dev).lower() for dev in devices) or
                                        any('gpu' in str(req).lower() for req in host_config.get('DeviceRequests', []))
                                    )
                                    
                                    if gpu_status["gpu"]:
                                        logger.info("Container is configured with GPU support")
                                    else:
                                        logger.warning("Container is running without GPU configuration")
                        except Exception as e:
                            logger.error(f"Error inspecting container: {e}")
                            # Fall back to GPU availability if we can't inspect
                            gpu_status["gpu"] = self.gpu_info['available']
                    
                    logger.info(f"Container GPU status: {gpu_status}")
                    return gpu_status
        except Exception as e:
            logger.error(f"Error checking container status: {e}")
            # API request failed, but container might still be running
            pass
        
        # If we can't connect to the API, check if the container exists 
        # and is running using Docker commands
        container_id = self._find_container_id()
        if container_id:
            # Container exists, check if it's running
            result = subprocess.run(
                ["docker", "ps", "-q", "--filter", f"id={container_id}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.stdout.strip():
                # Container exists and is running, but API isn't responding yet
                logger.info(f"Container {container_id[:12]} is running but API not responding yet (still initializing)")
                
                # Check container GPU configuration
                try:
                    inspect_result = subprocess.run(
                        ["docker", "inspect", container_id],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    if inspect_result.returncode == 0:
                        container_info = json.loads(inspect_result.stdout)
                        if container_info:
                            host_config = container_info[0].get('HostConfig', {})
                            runtime = host_config.get('Runtime', '')
                            devices = host_config.get('Devices', [])
                            
                            using_gpu = (
                                runtime == 'nvidia' or
                                any('nvidia' in str(dev).lower() for dev in devices) or
                                any('gpu' in str(req).lower() for req in host_config.get('DeviceRequests', []))
                            )
                            
                            return {
                                "status": "initializing",
                                "ready": False,
                                "message": "Container is starting up, please wait",
                                "gpu": using_gpu
                            }
                except Exception as e:
                    logger.error(f"Error inspecting container: {e}")
                
                # Fall back to GPU availability if inspection fails
                return {
                    "status": "initializing",
                    "ready": False,
                    "message": "Container is starting up, please wait",
                    "gpu": self.gpu_info['available']
                }
            else:
                # Container exists but isn't running
                logger.warning(f"Container {container_id[:12]} exists but is not running")
                return {
                    "status": "stopped",
                    "ready": False,
                    "message": "Container is stopped"
                }
        
        # No container found
        logger.warning("No suitable container found")
        return {
            "status": "not_found",
            "ready": False,
            "message": "No container found"
        }

    def _find_container_id(self):
        """Find a suitable container by name or port
        
        Tries to find a container either by the expected name or by the port it should be using
        
        Returns:
            str: Container ID or None if no suitable container found
        """
        try:
            # First try by name
            result = subprocess.run(
                ["docker", "ps", "-a", "-q", "--filter", f"name={self.container_name}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            container_id = result.stdout.strip()
            if container_id:
                return container_id
            
            # If not found by name, try by port
            result = subprocess.run(
                ["docker", "ps", "-a", "-q", "--filter", f"publish={self.port}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            container_id = result.stdout.strip()
            if container_id:
                # Found by port - capture the actual name for future reference
                name_result = subprocess.run(
                    ["docker", "inspect", "--format='{{.Name}}'", container_id],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                actual_name = name_result.stdout.strip().replace("'", "").replace("/", "")
                logger.info(f"Found container by port {self.port}: {container_id[:12]} (name: {actual_name})")
                
                # Update the container name for future reference
                self.container_name = actual_name
                
                return container_id
        except Exception as e:
            logger.error(f"Error finding container: {e}")
        
        return None

    def is_container_running(self):
        """Check if the container is running
        
        Returns:
            bool: True if container is running
        """
        status_info = self._check_container_status()
        return status_info["status"] in ["running", "initializing"]
    
    def restart_container_with_gpu(self) -> bool:
        """Try to restart the container with GPU support
        
        Returns:
            bool: True if container was restarted with GPU
        """
        if not self.gpu_info['available']:
            logger.warning("No GPU detected on this system")
            return False
            
        try:
            # Find existing container using either name or port
            container_id = self._find_container_id()
            
            if container_id:
                # Stop the existing container
                logger.info(f"Stopping container {container_id[:12]}")
                subprocess.run(
                    ["docker", "stop", container_id],
                    capture_output=True,
                    timeout=30
                )
                
                # Remove the existing container
                subprocess.run(
                    ["docker", "rm", container_id],
                    capture_output=True,
                    timeout=30
                )
            else:
                logger.warning("No existing container found to restart")
            
            # Start a new container with GPU support
            result = subprocess.run(
                ["docker", "run", "-d", "-p", f"{self.port}:{self.port}", 
                 "--gpus", "all", 
                 "--name", self.container_name,
                 "--memory=12g", "--memory-swap=24g", "--shm-size=1g",
                 "calvin189/qwen-payslip-processor:latest"],
                capture_output=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info("Container restarted with GPU support")
                time.sleep(5)  # Give container time to initialize
                return self.verify_gpu_container()
            else:
                error_msg = result.stderr.decode('utf-8')
                # If the error is due to container name conflict, try with a unique name
                if "Conflict" in error_msg and "container name" in error_msg:
                    logger.warning("Container name conflict, trying with a unique name")
                    # Generate a unique name with timestamp
                    unique_name = f"{self.container_name}-{int(time.time())}"
                    result = subprocess.run(
                        ["docker", "run", "-d", "-p", f"{self.port}:{self.port}", 
                         "--gpus", "all", 
                         "--name", unique_name,
                         "--memory=12g", "--memory-swap=24g", "--shm-size=1g",
                         "calvin189/qwen-payslip-processor:latest"],
                        capture_output=True,
                        timeout=30
                    )
                    
                    if result.returncode == 0:
                        logger.info(f"Container restarted with GPU support using unique name: {unique_name}")
                        # Update the container name in this instance
                        self.container_name = unique_name
                        time.sleep(5)  # Give container time to initialize
                        return self.verify_gpu_container()
                
                logger.error(f"Failed to restart container: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"Error restarting container: {e}")
            return False
    
    def process_pdf(self, 
                    pdf_bytes: bytes, 
                    pages: Optional[Union[int, List[int]]] = None,
                    window_mode: Optional[str] = None,
                    selected_windows: Optional[Union[str, List[str]]] = None,
                    custom_prompts: Optional[Dict[str, str]] = None,
                    page_configs: Optional[Dict[str, Dict]] = None,
                    memory_isolation: Optional[str] = None,
                    file_name: Optional[str] = None,
                    force_cpu: bool = False,
                    gpu_memory_fraction: Optional[float] = None,
                    # Parameters for individual window processing
                    original_window_mode: Optional[str] = None,
                    extract_window: Optional[str] = None,
                    # Add all new parameters from the container API
                    pdf_dpi: Optional[int] = None,
                    image_resolution_steps: Optional[List[int]] = None,
                    image_enhance_contrast: Optional[bool] = None,
                    image_sharpen_factor: Optional[float] = None,
                    image_contrast_factor: Optional[float] = None,
                    image_brightness_factor: Optional[float] = None,
                    image_ocr_language: Optional[str] = None,
                    image_ocr_threshold: Optional[int] = None,
                    window_overlap: Optional[float] = None,
                    window_min_size: Optional[int] = None,
                    text_generation_max_new_tokens: Optional[int] = None,
                    text_generation_use_beam_search: Optional[bool] = None,
                    text_generation_num_beams: Optional[int] = None,
                    text_generation_temperature: Optional[float] = None,
                    text_generation_top_p: Optional[float] = None,
                    extraction_confidence_threshold: Optional[float] = None,
                    extraction_fuzzy_matching: Optional[bool] = None,
                    global_mode: Optional[str] = None,
                    global_prompt: Optional[str] = None,
                    global_selected_windows: Optional[Union[str, List[str]]] = None,
                    override_global_settings: Optional[bool] = None,
                    full_config: Optional[Dict] = None) -> Dict:
        """Process a PDF file using the Docker container
        
        Args:
            pdf_bytes: Raw PDF file bytes
            pages: Specific page numbers to process (1-indexed)
            window_mode: Window mode to use (whole, vertical, horizontal, quadrant)
            selected_windows: Windows to process based on window_mode
            custom_prompts: Dictionary of custom prompts for specific windows
            page_configs: Dictionary of page-specific configurations
            memory_isolation: Memory isolation mode ("none", "medium", "strict", "auto")
            file_name: Original filename (optional)
            force_cpu: Force CPU processing even if GPU is available
            gpu_memory_fraction: Fraction of GPU memory to use (0.0-1.0)
            original_window_mode: Original window mode when processing individual windows
            extract_window: Specific window to extract when processing individual windows
            pdf_dpi: DPI for PDF rendering
            image_resolution_steps: List of image resolutions to try
            image_enhance_contrast: Enable contrast enhancement
            image_sharpen_factor: Sharpening intensity
            image_contrast_factor: Contrast enhancement factor
            image_brightness_factor: Brightness adjustment factor
            image_ocr_language: OCR language
            image_ocr_threshold: OCR confidence threshold
            window_overlap: Overlap between windows
            window_min_size: Minimum window size
            text_generation_max_new_tokens: Max tokens to generate
            text_generation_use_beam_search: Use beam search
            text_generation_num_beams: Number of beams
            text_generation_temperature: Generation temperature
            text_generation_top_p: Top-p sampling
            extraction_confidence_threshold: Minimum confidence threshold
            extraction_fuzzy_matching: Use fuzzy matching
            global_mode: Default mode for all pages
            global_prompt: Default prompt for all pages
            global_selected_windows: Default windows for all pages
            override_global_settings: Override global settings
            full_config: Complete configuration object
            
        Returns:
            Dict: Processed results from the container
            
        Raises:
            ConnectionError: If the Docker container is not running
            RuntimeError: If the container returns an error response
        """
        if not self.is_container_running():
            error_msg = f"Docker container not running at {self.base_url}. Cannot process PDF."
            logger.error(error_msg)
            raise ConnectionError(error_msg)
        
        # Prepare files and data
        files = {'file': (file_name or 'document.pdf', pdf_bytes, 'application/pdf')}
        data = {}
        
        # Calculate dynamic timeout based on pages and window count
        # Start with base timeout
        dynamic_timeout = self.base_timeout
        
        # Determine page count for timeout calculation
        page_count = 1  # Default to 1 if unknown
        if pages is not None:
            if isinstance(pages, int):
                page_count = 1
                data['pages'] = str(pages)
            elif isinstance(pages, list):
                page_count = len(pages)
                data['pages'] = ','.join(map(str, pages))
        
        # Calculate windows per page for timeout calculation
        window_count = 1  # Default
        if window_mode == "quadrant":
            window_count = 4  # 4 windows per page
        elif window_mode in ["vertical", "horizontal"]:
            window_count = 2  # 2 windows per page
            
        # Multiply timeout by total windows to process
        dynamic_timeout = dynamic_timeout * page_count * window_count
        
        # Cap at reasonable maximum (4 hours)
        dynamic_timeout = min(dynamic_timeout, 14400)
        
        # If running on CPU, add additional time
        if force_cpu or not self.gpu_info['available']:
            dynamic_timeout = min(dynamic_timeout * self.cpu_timeout_multiplier, 14400)  # Use multiplier from config, cap at 4 hours
            logger.info(f"Applied CPU timeout multiplier ({self.cpu_timeout_multiplier}x) for CPU-only processing")
        
        logger.info(f"Using dynamic timeout of {dynamic_timeout} seconds for {page_count} pages in {window_mode} mode")
        
        # Add page information if provided
        if pages is not None:
            if isinstance(pages, int):
                data['pages'] = str(pages)
            elif isinstance(pages, list):
                data['pages'] = ','.join(map(str, pages))
        
        # Add window mode if provided
        if window_mode is not None:
            data['window_mode'] = window_mode
        else:
            # Default to vertical mode if None is provided
            data['window_mode'] = "vertical"
            logger.warning("window_mode was None, defaulted to 'vertical'")
            
        # Add selected windows if provided
        if selected_windows is not None:
            if isinstance(selected_windows, list):
                data['selected_windows'] = ','.join(selected_windows)
            else:
                data['selected_windows'] = selected_windows
            
            # Force override_global_settings to true when selected_windows is explicitly provided
            # This ensures user-specified window selections take precedence over global settings
            data['override_global_settings'] = 'true'
            logger.info(f"Selected windows explicitly provided: {selected_windows}. Forcing override_global_settings=true")
        else:
            # Default to both windows for vertical mode
            if data['window_mode'] == "vertical":
                data['selected_windows'] = "top,bottom"
                logger.warning("selected_windows was None for vertical mode, defaulted to 'top,bottom'")
                # Also force override_global_settings to true
                data['override_global_settings'] = 'true'
        
        # Add memory isolation if provided
        if memory_isolation is not None:
            data['memory_isolation'] = memory_isolation
                
        # Add force CPU setting if provided
        if force_cpu:
            data['force_cpu'] = 'true'
        
        # Add GPU memory fraction if provided
        if gpu_memory_fraction is not None:
            data['gpu_memory_fraction'] = str(gpu_memory_fraction)
            
        # Add custom prompts if provided
        if custom_prompts and isinstance(custom_prompts, dict):
            for window, prompt in custom_prompts.items():
                data[f'prompt_{window}'] = prompt
        
        # Add page configs if provided
        if page_configs and isinstance(page_configs, dict):
            data['page_configs'] = json.dumps(page_configs)
            
        # Add individual window processing parameters if provided
        if original_window_mode is not None:
            data['original_window_mode'] = original_window_mode
            
        if extract_window is not None:
            data['extract_window'] = extract_window
            
        # Add PDF parameters
        if pdf_dpi is not None:
            data['pdf_dpi'] = str(pdf_dpi)
            
        # Add image processing parameters
        if image_resolution_steps is not None:
            # Make sure image_resolution_steps is a list of integers
            if not isinstance(image_resolution_steps, list):
                try:
                    # Try to convert to a list if it's not already
                    if isinstance(image_resolution_steps, str) and ',' in image_resolution_steps:
                        image_resolution_steps = [int(s.strip()) for s in image_resolution_steps.split(',')]
                    else:
                        # Convert single value to list
                        image_resolution_steps = [int(image_resolution_steps)]
                    logger.info(f"Converted resolution_steps to list: {image_resolution_steps}")
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid resolution_steps format: {image_resolution_steps}. Using default [600, 400]. Error: {e}")
                    image_resolution_steps = [600, 400]
            else:
                # Ensure all values in the list are integers
                try:
                    image_resolution_steps = [int(step) for step in image_resolution_steps]
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid values in resolution_steps list: {image_resolution_steps}. Using default [600, 400]. Error: {e}")
                    image_resolution_steps = [600, 400]
            
            # FIXED: Instead of passing as a comma-separated string, create a full config with proper integers
            if 'full_config' not in data:
                data['full_config'] = json.dumps({
                    "image": {
                        "resolution_steps": image_resolution_steps  # This will be properly serialized as JSON integers
                    }
                })
            else:
                # Parse existing full_config, update it, and re-serialize
                try:
                    config = json.loads(data['full_config'])
                    if 'image' not in config:
                        config['image'] = {}
                    config['image']['resolution_steps'] = image_resolution_steps
                    data['full_config'] = json.dumps(config)
                except json.JSONDecodeError:
                    # If the full_config isn't valid JSON, create a new one
                    data['full_config'] = json.dumps({
                        "image": {
                            "resolution_steps": image_resolution_steps
                        }
                    })
            
            logger.info(f"Using image_resolution_steps in full_config: {image_resolution_steps}")
            
        if image_enhance_contrast is not None:
            data['image_enhance_contrast'] = str(image_enhance_contrast).lower()
            
        if image_sharpen_factor is not None:
            data['image_sharpen_factor'] = str(image_sharpen_factor)
            
        if image_contrast_factor is not None:
            data['image_contrast_factor'] = str(image_contrast_factor)
            
        if image_brightness_factor is not None:
            data['image_brightness_factor'] = str(image_brightness_factor)
            
        if image_ocr_language is not None:
            data['image_ocr_language'] = image_ocr_language
            
        if image_ocr_threshold is not None:
            data['image_ocr_threshold'] = str(image_ocr_threshold)
            
        # Add window settings
        if window_overlap is not None:
            data['window_overlap'] = str(window_overlap)
            
        if window_min_size is not None:
            data['window_min_size'] = str(window_min_size)
            
        # Add text generation settings
        if text_generation_max_new_tokens is not None:
            data['text_generation_max_new_tokens'] = str(text_generation_max_new_tokens)
            
        if text_generation_use_beam_search is not None:
            data['text_generation_use_beam_search'] = str(text_generation_use_beam_search).lower()
            
        if text_generation_num_beams is not None:
            data['text_generation_num_beams'] = str(text_generation_num_beams)
            
        if text_generation_temperature is not None:
            data['text_generation_temperature'] = str(text_generation_temperature)
            
        if text_generation_top_p is not None:
            data['text_generation_top_p'] = str(text_generation_top_p)
            
        # Add extraction settings
        if extraction_confidence_threshold is not None:
            data['extraction_confidence_threshold'] = str(extraction_confidence_threshold)
            
        if extraction_fuzzy_matching is not None:
            data['extraction_fuzzy_matching'] = str(extraction_fuzzy_matching).lower()
            
        # Add global settings
        if global_mode is not None:
            data['global_mode'] = global_mode
            
        if global_prompt is not None:
            data['global_prompt'] = global_prompt
            
        # Add global_selected_windows if provided
        if global_selected_windows is not None:
            data['global_selected_windows'] = global_selected_windows
        
        # Add override_global_settings if provided (but don't overwrite if already set above)
        if override_global_settings is not None and 'override_global_settings' not in data:
            # ensure it's a string
            data['override_global_settings'] = str(override_global_settings).lower()
        
        # Add full config if provided
        if full_config is not None:
            # FIXED: Parse resolution_steps to ensure they are integers before sending
            if "image" in full_config and "resolution_steps" in full_config["image"]:
                # Ensure resolution_steps are integers
                if isinstance(full_config["image"]["resolution_steps"], list):
                    full_config["image"]["resolution_steps"] = [
                        int(step) for step in full_config["image"]["resolution_steps"]
                    ]
                elif full_config["image"]["resolution_steps"] is not None:
                    # Handle single value
                    full_config["image"]["resolution_steps"] = [
                        int(full_config["image"]["resolution_steps"])
                    ]
            
            # Convert to JSON with proper types
            data['full_config'] = json.dumps(full_config)
            logger.info(f"Sending full_config with resolution_steps as integers")
        
        # CRITICAL: Final validation before API call to ensure window_mode is never None
        if "window_mode" not in data or data["window_mode"] is None:
            data["window_mode"] = "vertical"  
            logger.warning("CRITICAL FIX: window_mode missing or None just before API call. Forced to 'vertical'")
        
        # CRITICAL: Final validation for selected_windows - needed for vertical mode
        if "window_mode" in data and data["window_mode"] == "vertical" and "selected_windows" not in data:
            data["selected_windows"] = "top,bottom"
            logger.warning("CRITICAL FIX: selected_windows missing for vertical mode. Forced to 'top,bottom'")
            
        # CRITICAL: Force override_global_settings
        data["override_global_settings"] = "true"
        
        try:
            # Make request to container
            logger.info(f"Sending PDF to container with params: {data}")
            logger.info(f"Critical parameters: window_mode={data.get('window_mode', 'MISSING!')}, selected_windows={data.get('selected_windows', 'MISSING!')}")
            
            start_time = time.time()
            response = requests.post(
                f"{self.base_url}/process/pdf",
                files=files,
                data=data,
                timeout=dynamic_timeout  # Use dynamic timeout
            )
            processing_time = time.time() - start_time
            logger.info(f"Container processed PDF in {processing_time:.2f} seconds")
            
            # Check response
            if response.status_code != 200:
                error_msg = f"Container returned error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            result = response.json()
            
            # Log processing stats
            if 'processing_time' in result:
                logger.info(f"PDF processing completed in {result['processing_time']:.2f} seconds")
            if 'processed_pages' in result and 'total_pages' in result:
                logger.info(f"Processed {result['processed_pages']} of {result['total_pages']} pages")
            
            return result
            
        except requests.RequestException as e:
            error_msg = f"Error communicating with Docker container: {e}"
            logger.error(error_msg)
            raise ConnectionError(error_msg)
    
    def process_image(self, 
                    image_bytes: bytes,
                    window_mode: Optional[str] = None,
                    selected_windows: Optional[Union[str, List[str]]] = None,
                    custom_prompts: Optional[Dict[str, str]] = None,
                    force_cpu: bool = False,
                    gpu_memory_fraction: Optional[float] = None,
                    # Parameters for individual window processing
                    original_window_mode: Optional[str] = None,
                    extract_window: Optional[str] = None,
                    # Add all new parameters from the container API
                    memory_isolation: Optional[str] = None,
                    image_resolution_steps: Optional[List[int]] = None,
                    image_enhance_contrast: Optional[bool] = None,
                    image_sharpen_factor: Optional[float] = None,
                    image_contrast_factor: Optional[float] = None,
                    image_brightness_factor: Optional[float] = None,
                    image_ocr_language: Optional[str] = None,
                    image_ocr_threshold: Optional[int] = None,
                    window_overlap: Optional[float] = None,
                    window_min_size: Optional[int] = None,
                    text_generation_max_new_tokens: Optional[int] = None,
                    text_generation_use_beam_search: Optional[bool] = None,
                    text_generation_num_beams: Optional[int] = None,
                    text_generation_temperature: Optional[float] = None,
                    text_generation_top_p: Optional[float] = None,
                    extraction_confidence_threshold: Optional[float] = None,
                    extraction_fuzzy_matching: Optional[bool] = None,
                    global_mode: Optional[str] = None,
                    global_prompt: Optional[str] = None,
                    global_selected_windows: Optional[Union[str, List[str]]] = None,
                    override_global_settings: Optional[bool] = None,
                    full_config: Optional[Dict] = None) -> Dict:
        """Process an image file using the Docker container
        
        Args:
            image_bytes: Raw image file bytes
            window_mode: Window mode to use (whole, vertical, horizontal, quadrant)
            selected_windows: Windows to process based on window_mode
            custom_prompts: Dictionary of custom prompts for specific windows
            force_cpu: Force CPU processing even if GPU is available
            gpu_memory_fraction: Fraction of GPU memory to use (0.0-1.0)
            memory_isolation: Memory isolation mode ("none", "medium", "strict", "auto")
            image_resolution_steps: List of image resolutions to try
            image_enhance_contrast: Enable contrast enhancement
            image_sharpen_factor: Sharpening intensity
            image_contrast_factor: Contrast enhancement factor
            image_brightness_factor: Brightness adjustment factor
            image_ocr_language: OCR language
            image_ocr_threshold: OCR confidence threshold
            window_overlap: Overlap between windows
            window_min_size: Minimum window size
            text_generation_max_new_tokens: Max tokens to generate
            text_generation_use_beam_search: Use beam search
            text_generation_num_beams: Number of beams
            text_generation_temperature: Generation temperature
            text_generation_top_p: Top-p sampling
            extraction_confidence_threshold: Minimum confidence threshold
            extraction_fuzzy_matching: Use fuzzy matching
            global_mode: Default mode for all pages
            global_prompt: Default prompt for all pages
            global_selected_windows: Default windows for all pages
            override_global_settings: Override global settings
            full_config: Complete configuration object
            
        Returns:
            Dict: Processed results from the container
            
        Raises:
            ConnectionError: If the Docker container is not running
            RuntimeError: If the container returns an error response
        """
        if not self.is_container_running():
            error_msg = f"Docker container not running at {self.base_url}. Cannot process image."
            logger.error(error_msg)
            raise ConnectionError(error_msg)
        
        # Prepare files and data
        files = {'file': ('document.jpg', image_bytes, 'image/jpeg')}
        data = {}
        
        # Calculate dynamic timeout based on window count
        # Start with base timeout
        dynamic_timeout = self.base_timeout
        
        # Calculate window count for timeout calculation
        window_count = 1  # Default
        if window_mode == "quadrant":
            window_count = 4  # 4 windows per image
        elif window_mode in ["vertical", "horizontal"]:
            window_count = 2  # 2 windows per image
            
        # Multiply timeout by total windows to process
        dynamic_timeout = dynamic_timeout * window_count
        
        # If running on CPU, add additional time
        if force_cpu or not self.gpu_info['available']:
            dynamic_timeout = min(dynamic_timeout * self.cpu_timeout_multiplier, 14400)  # Use multiplier from config, cap at 4 hours
            logger.info(f"Applied CPU timeout multiplier ({self.cpu_timeout_multiplier}x) for CPU-only processing")
        
        logger.info(f"Using dynamic timeout of {dynamic_timeout} seconds for image in {window_mode} mode")
        
        # Add window mode if provided
        if window_mode is not None:
            data['window_mode'] = window_mode
        else:
            # Default to vertical mode if None is provided
            data['window_mode'] = "vertical"
            logger.warning("window_mode was None, defaulted to 'vertical'")
            
        # Add selected windows if provided
        if selected_windows is not None:
            if isinstance(selected_windows, list):
                data['selected_windows'] = ','.join(selected_windows)
            else:
                data['selected_windows'] = selected_windows
            
            # Force override_global_settings to true when selected_windows is explicitly provided
            # This ensures user-specified window selections take precedence over global settings
            data['override_global_settings'] = 'true'
            logger.info(f"Selected windows explicitly provided: {selected_windows}. Forcing override_global_settings=true")
        else:
            # Default to both windows for vertical mode
            if data['window_mode'] == "vertical":
                data['selected_windows'] = "top,bottom"
                logger.warning("selected_windows was None for vertical mode, defaulted to 'top,bottom'")
                # Also force override_global_settings to true
                data['override_global_settings'] = 'true'
        
        # Add memory isolation if provided
        if memory_isolation is not None:
            data['memory_isolation'] = memory_isolation
                
        # Add force CPU setting if provided
        if force_cpu:
            data['force_cpu'] = 'true'
        
        # Add GPU memory fraction if provided
        if gpu_memory_fraction is not None:
            data['gpu_memory_fraction'] = str(gpu_memory_fraction)
        
        # Add individual window processing parameters if provided
        if original_window_mode is not None:
            data['original_window_mode'] = original_window_mode
            
        if extract_window is not None:
            data['extract_window'] = extract_window
        
        # Add custom prompts if provided
        if custom_prompts and isinstance(custom_prompts, dict):
            for window, prompt in custom_prompts.items():
                data[f'prompt_{window}'] = prompt
            
        # Add image processing parameters
        if image_resolution_steps is not None:
            # Make sure image_resolution_steps is a list of integers
            if not isinstance(image_resolution_steps, list):
                try:
                    # Try to convert to a list if it's not already
                    if isinstance(image_resolution_steps, str) and ',' in image_resolution_steps:
                        image_resolution_steps = [int(s.strip()) for s in image_resolution_steps.split(',')]
                    else:
                        # Convert single value to list
                        image_resolution_steps = [int(image_resolution_steps)]
                    logger.info(f"Converted resolution_steps to list: {image_resolution_steps}")
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid resolution_steps format: {image_resolution_steps}. Using default [600, 400]. Error: {e}")
                    image_resolution_steps = [600, 400]
            else:
                # Ensure all values in the list are integers
                try:
                    image_resolution_steps = [int(step) for step in image_resolution_steps]
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid values in resolution_steps list: {image_resolution_steps}. Using default [600, 400]. Error: {e}")
                    image_resolution_steps = [600, 400]
            
            # FIXED: Instead of passing as a comma-separated string, create a full config with proper integers
            if 'full_config' not in data:
                data['full_config'] = json.dumps({
                    "image": {
                        "resolution_steps": image_resolution_steps  # This will be properly serialized as JSON integers
                    }
                })
            else:
                # Parse existing full_config, update it, and re-serialize
                try:
                    config = json.loads(data['full_config'])
                    if 'image' not in config:
                        config['image'] = {}
                    config['image']['resolution_steps'] = image_resolution_steps
                    data['full_config'] = json.dumps(config)
                except json.JSONDecodeError:
                    # If the full_config isn't valid JSON, create a new one
                    data['full_config'] = json.dumps({
                        "image": {
                            "resolution_steps": image_resolution_steps
                        }
                    })
            
            logger.info(f"Using image_resolution_steps in full_config: {image_resolution_steps}")
            
        if image_enhance_contrast is not None:
            data['image_enhance_contrast'] = str(image_enhance_contrast).lower()
            
        if image_sharpen_factor is not None:
            data['image_sharpen_factor'] = str(image_sharpen_factor)
            
        if image_contrast_factor is not None:
            data['image_contrast_factor'] = str(image_contrast_factor)
            
        if image_brightness_factor is not None:
            data['image_brightness_factor'] = str(image_brightness_factor)
            
        if image_ocr_language is not None:
            data['image_ocr_language'] = image_ocr_language
            
        if image_ocr_threshold is not None:
            data['image_ocr_threshold'] = str(image_ocr_threshold)
            
        # Add window settings
        if window_overlap is not None:
            data['window_overlap'] = str(window_overlap)
            
        if window_min_size is not None:
            data['window_min_size'] = str(window_min_size)
            
        # Add text generation settings
        if text_generation_max_new_tokens is not None:
            data['text_generation_max_new_tokens'] = str(text_generation_max_new_tokens)
            
        if text_generation_use_beam_search is not None:
            data['text_generation_use_beam_search'] = str(text_generation_use_beam_search).lower()
            
        if text_generation_num_beams is not None:
            data['text_generation_num_beams'] = str(text_generation_num_beams)
            
        if text_generation_temperature is not None:
            data['text_generation_temperature'] = str(text_generation_temperature)
            
        if text_generation_top_p is not None:
            data['text_generation_top_p'] = str(text_generation_top_p)
            
        # Add extraction settings
        if extraction_confidence_threshold is not None:
            data['extraction_confidence_threshold'] = str(extraction_confidence_threshold)
            
        if extraction_fuzzy_matching is not None:
            data['extraction_fuzzy_matching'] = str(extraction_fuzzy_matching).lower()
            
        # Add global settings
        if global_mode is not None:
            data['global_mode'] = global_mode
            
        if global_prompt is not None:
            data['global_prompt'] = global_prompt
            
        if global_selected_windows is not None:
            if isinstance(global_selected_windows, list):
                data['global_selected_windows'] = ','.join(global_selected_windows)
            else:
                data['global_selected_windows'] = global_selected_windows
                
        # Add override_global_settings if provided
        if override_global_settings is not None:
            data['override_global_settings'] = str(override_global_settings).lower()
            
        # Add full config if provided
        if full_config is not None:
            # FIXED: Parse resolution_steps to ensure they are integers before sending
            if "image" in full_config and "resolution_steps" in full_config["image"]:
                # Ensure resolution_steps are integers
                if isinstance(full_config["image"]["resolution_steps"], list):
                    full_config["image"]["resolution_steps"] = [
                        int(step) for step in full_config["image"]["resolution_steps"]
                    ]
                elif full_config["image"]["resolution_steps"] is not None:
                    # Handle single value
                    full_config["image"]["resolution_steps"] = [
                        int(full_config["image"]["resolution_steps"])
                    ]
            
            # Convert to JSON with proper types
            data['full_config'] = json.dumps(full_config)
            logger.info(f"Sending full_config with resolution_steps as integers")
            
        # CRITICAL: Final validation before API call to ensure window_mode is never None
        if "window_mode" not in data or data["window_mode"] is None:
            data["window_mode"] = "vertical"  
            logger.warning("CRITICAL FIX: window_mode missing or None just before API call. Forced to 'vertical'")
        
        # CRITICAL: Final validation for selected_windows - needed for vertical mode
        if "window_mode" in data and data["window_mode"] == "vertical" and "selected_windows" not in data:
            data["selected_windows"] = "top,bottom"
            logger.warning("CRITICAL FIX: selected_windows missing for vertical mode. Forced to 'top,bottom'")
            
        # CRITICAL: Force override_global_settings
        data["override_global_settings"] = "true"
        
        try:
            # Make request to container
            logger.info(f"Sending image to container with params: {data}")
            logger.info(f"Critical parameters: window_mode={data.get('window_mode', 'MISSING!')}, selected_windows={data.get('selected_windows', 'MISSING!')}")
            
            start_time = time.time()
            response = requests.post(
                f"{self.base_url}/process/image",
                files=files,
                data=data,
                timeout=dynamic_timeout  # Use dynamic timeout
            )
            processing_time = time.time() - start_time
            logger.info(f"Container processed image in {processing_time:.2f} seconds")
            
            # Check response
            if response.status_code != 200:
                error_msg = f"Container returned error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            return response.json()
            
        except requests.RequestException as e:
            error_msg = f"Error communicating with Docker container: {e}"
            logger.error(error_msg)
            raise ConnectionError(error_msg)
    
    def process_window_with_prompt(self, image, prompt):
        """Process a single image window with a custom prompt
        
        Args:
            image: PIL Image object
            prompt: Custom prompt to use for this window
            
        Returns:
            Dict: Processed results from the container
        """
        if not self.is_container_running():
            error_msg = f"Docker container not running at {self.base_url}. Cannot process window."
            logger.error(error_msg)
            raise ConnectionError(error_msg)
        
        # Convert PIL Image to bytes
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='JPEG')
        img_byte_arr = img_byte_arr.getvalue()
        
        # Prepare files and data
        files = {'file': ('window.jpg', img_byte_arr)}
        data = {
            'window_mode': 'whole',  # Always use whole for single window
            'prompt_whole': prompt
        }
        
        try:
            # Make request to container
            logger.info(f"Sending window to container with custom prompt")
            start_time = time.time()
            response = requests.post(
                f"{self.base_url}/process/image",
                files=files,
                data=data,
                timeout=self.timeout
            )
            processing_time = time.time() - start_time
            logger.info(f"Container processed window in {processing_time:.2f} seconds")
            
            # Check response
            if response.status_code != 200:
                error_msg = f"Container returned error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            result = response.json()
            
            # Extract the property data from the "whole" window result
            property_data = {}
            for result_item in result.get("results", []):
                if "property_whole" in result_item:
                    property_data = result_item["property_whole"]
                    break
            
            return property_data
            
        except requests.RequestException as e:
            error_msg = f"Error communicating with Docker container: {e}"
            logger.error(error_msg)
            raise ConnectionError(error_msg)
    
    def convert_pdf_to_images(self, pdf_bytes):
        """Convert a PDF to images using the Docker container
        
        Args:
            pdf_bytes: Raw PDF file bytes
            
        Returns:
            List[PIL.Image]: List of PIL Image objects, one per page
        """
        if not self.is_container_running():
            error_msg = f"Docker container not running at {self.base_url}. Cannot convert PDF."
            logger.error(error_msg)
            raise ConnectionError(error_msg)
        
        # Prepare files
        files = {'file': ('document.pdf', pdf_bytes)}
        data = {'return_images': 'true'}
        
        try:
            logger.info("Sending PDF to container for conversion to images")
            response = requests.post(
                f"{self.base_url}/convert/pdf-to-images",
                files=files,
                data=data,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                error_msg = f"Container returned error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            result = response.json()
            
            # Convert base64 images to PIL Image objects
            images = []
            for base64_img in result.get("images", []):
                try:
                    img_data = base64.b64decode(base64_img)
                    img = Image.open(io.BytesIO(img_data))
                    images.append(img)
                except Exception as e:
                    logger.error(f"Error converting base64 to image: {e}")
            
            logger.info(f"Converted PDF to {len(images)} images")
            return images
            
        except requests.RequestException as e:
            error_msg = f"Error communicating with Docker container: {e}"
            logger.error(error_msg)
            raise ConnectionError(error_msg)
    
    def split_image_for_sliding_window(self, image, window_mode="vertical"):
        """Split an image for sliding window processing
        
        Args:
            image: PIL Image object
            window_mode: Mode to split the image (whole, vertical, horizontal, quadrant)
            
        Returns:
            List[PIL.Image]: List of image windows
        """
        windows = []
        
        if window_mode == "whole":
            # Return the whole image
            windows.append(image)
        elif window_mode == "vertical":
            # Split into top and bottom
            width, height = image.size
            top_half = image.crop((0, 0, width, height // 2))
            bottom_half = image.crop((0, height // 2, width, height))
            windows.extend([top_half, bottom_half])
        elif window_mode == "horizontal":
            # Split into left and right
            width, height = image.size
            left_half = image.crop((0, 0, width // 2, height))
            right_half = image.crop((width // 2, 0, width, height))
            windows.extend([left_half, right_half])
        elif window_mode == "quadrant":
            # Split into 4 quadrants
            width, height = image.size
            top_left = image.crop((0, 0, width // 2, height // 2))
            top_right = image.crop((width // 2, 0, width, height // 2))
            bottom_left = image.crop((0, height // 2, width // 2, height))
            bottom_right = image.crop((width // 2, height // 2, width, height))
            windows.extend([top_left, top_right, bottom_left, bottom_right])
        
        return windows
    
    def force_memory_cleanup(self):
        """
        Send a request to the container to force memory cleanup
        This is useful to clear CUDA memory between processing operations
        
        Returns:
            bool: True if cleanup was successful, False otherwise
        """
        if not self.is_container_running():
            logger.warning("Container not running, cannot perform memory cleanup")
            return False
            
        try:
            logger.info("Requesting memory cleanup from Docker container")
            
            # Call container memory cleanup endpoint
            response = requests.post(
                f"{self.base_url}/cleanup/memory",
                timeout=30
            )
            
            # Check response
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Memory cleanup successful: {result.get('message', 'No details provided')}")
                
                # Log memory freed if available
                if "memory_freed_mb" in result:
                    logger.info(f"Memory freed: {result['memory_freed_mb']:.2f} MB")
                    
                return True
            else:
                logger.warning(f"Memory cleanup failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error during container memory cleanup: {e}")
            return False 