# Qwen Payslip Processor

A Docker-based Python application for processing German payslips and property listings using the Qwen2.5-VL-7B vision-language model.

## Quick Start (2 Simple Steps)

The fastest way to get up and running:

```bash
# Step 1: Clone the repository
git clone https://github.com/calvinsendawula/payslip_processor.git
cd payslip_processor

# Step 2: Run the all-in-one starter script
# On Windows:
start_app.bat

# On Linux/macOS:
chmod +x start_app.sh
./start_app.sh
```

That's it! The script automatically:
- Ensures Docker is running
- Downloads and starts the Docker container with GPU support when available
- Sets up Python environment and dependencies
- Launches backend and frontend services
- Opens your browser to the UI at http://localhost:5173

The application will process both payslips and property listings, detecting and using your GPU if available.

## Overview

This application is designed for processing German documents:
- **Payslips**: Extracts employee name, gross amount, and net amount
- **Property Listings**: Extracts living space (m²) and purchase price (€)

The system works in **air-gapped environments** (environments without internet access):

1. **Docker Container**: Contains the entire Qwen2.5-VL model and processing logic
2. **Backend**: FastAPI service that communicates with the Docker container
3. **Frontend**: Flask web interface for uploading and validating documents

## System Requirements

### Minimum Requirements (CPU Mode)
- **CPU**: Quad-core CPU (8 threads recommended)
- **RAM**: 8GB for Docker container + 2GB for application (12GB total recommended)
- **Disk Space**: 15GB for Docker image and container
- **Docker**: Docker Engine/CLI (Docker Desktop not required)
- **Python**: 3.11+ for the backend and frontend
- **Network**: Internet connection (only needed for initial Docker image download)

### Recommended Requirements (GPU Mode)
- **CPU**: 8+ cores
- **RAM**: 16GB system RAM
- **GPU**: 
  - NVIDIA GPU with 8GB+ VRAM and CUDA support
  - OR Apple Silicon M1/M2/M3 (Metal acceleration)
- **Disk Space**: 20GB free space
- **Docker**: Docker Engine with GPU support
- **GPU Drivers**:
  - For NVIDIA: Latest NVIDIA drivers and NVIDIA Container Toolkit installed

## Download and Startup Times

**Important**: The Docker image is large (~14GB) and requires significant download and startup time:

- **Download time**: 
  - On a 200Mbps connection: 15-30 minutes
  - On a 100Mbps connection: 30-60 minutes
  - On slower connections: 1+ hour
  
- **Initial startup time**: 5-10 minutes while the model loads into memory

The container is ready when you see this in the logs (`docker logs qwen-payslip-processor`):
```
Loading checkpoint shards: 100%|██████████| 4/4 [00:07<00:00,  1.93s/it]
INFO:qwen_payslip_processor.processor:Model loaded successfully!
INFO:server:Model loaded and ready to serve requests
INFO:     Uvicorn running on http://0.0.0.0:27842 (Press CTRL+C to quit)
```

Do not interrupt the download or startup process. The backend will automatically detect when the container is ready.

## Docker Environment Setup

For optimal performance, especially with the large model in the Docker container:

### Windows with WSL2

Create a `.wslconfig` file in your Windows user profile directory (`%USERPROFILE%\.wslconfig`) with:

```
[wsl2]
memory=16GB
processors=8
swap=32GB
gpuSupport=true
```

Then restart Docker Desktop completely.

### Docker Desktop Settings

1. Go to Docker Desktop → Settings → Resources
2. Allocate at least 8GB RAM (12GB+ recommended)
3. Increase Swap space to at least 4GB
4. For GPU support, ensure "Use GPU" is enabled (if available)

## Air-Gapped Operation

This application is specifically designed to work in completely isolated environments without internet access:

### Setup for Air-Gapped Environment

1. **Download and package required assets** on a machine with internet access:
   ```bash
   # Download Docker image
   docker pull calvin189/qwen-payslip-processor:latest
   docker save calvin189/qwen-payslip-processor:latest > qwen-payslip-processor.tar
   
   # Clone and package the application
   git clone https://github.com/calvinsendawula/payslip_processor.git
   cd payslip_processor
   
   # Install dependencies in a temporary venv to include in the package
   python -m venv temp_venv
   source temp_venv/bin/activate  # Windows: temp_venv\Scripts\activate
   pip install -r requirements.txt
   pip install -r backend/requirements.txt  
   pip install -r frontend/requirements.txt
   deactivate
   
   # Package everything
   tar -czvf payslip-processor.tar.gz *
   ```

2. **Transfer files** to the air-gapped environment:
   - `qwen-payslip-processor.tar` (Docker image)
   - `payslip-processor.tar.gz` (Application code)

3. **Deploy on air-gapped machine**:
   ```bash
   # Load Docker image
   docker load < qwen-payslip-processor.tar
   
   # Unpack application
   mkdir payslip-processor
   tar -xzvf payslip-processor.tar.gz -C payslip-processor
   cd payslip-processor
   
   # Run the application
   ./start_app.sh  # or start_app.bat on Windows
   ```

### Air-Gapped Features

- **No internet dependencies**: All required files are packaged within the application:
  - Local fonts instead of Google Fonts CDN
  - Local Material icons instead of external CDN
  - Offline documentation and error messages
  
- **No model downloads**: The complete Qwen2.5-VL model (14GB+) is pre-packaged in the Docker image

- **Works with Docker CLI**: Docker Desktop is not required, only the Docker Engine/CLI

- **Self-contained setup scripts**: All virtual environment setup is handled automatically

## Docker-Based Architecture

The application is designed to work exclusively with the Docker container:

- **No Local Model**: The 14GB+ model is entirely contained within the Docker image
- **Port-Based Detection**: The backend automatically detects if the Docker container is running
- **GPU Acceleration**: Automatically detects and uses GPU if available
- **Complete Configuration**: All parameters are configured via the config files
- **Multi-Window Processing**: Documents can be divided into regions for targeted extraction
- **Custom German Prompts**: Specific instructions for the model in German language

## Detailed Setup Instructions

### Recommended: One-Click Automatic Setup

Our one-click script `start_app.bat` (Windows) or `start_app.sh` (Linux/macOS) handles everything automatically:

```bash
# Windows (Command Prompt)
start_app.bat

# Linux/macOS
chmod +x start_app.sh
./start_app.sh
```

These scripts will:
1. Check if the Docker container is running and start it if needed
2. Set up a Python virtual environment (`.venv`) if it doesn't exist
3. Install all required dependencies in the virtual environment
4. Start the backend server
5. Start the frontend web interface
6. Open the application in your browser

**First-time startup process** includes these automatic steps:
1. Checking if Docker is installed and running
2. Verifying if Docker image exists locally, if not:
   - Downloading the Docker image (~14GB, 15-60+ minutes depending on connection)
3. Creating and starting the container:
   - Detecting GPU availability and using it if present
   - Configuring appropriate memory settings
4. Creating a Python virtual environment in the root directory
5. Installing dependencies in the virtual environment
6. Starting backend and frontend with required dependencies
7. Opening the web interface once services are ready

The total time for first setup can be 20-90 minutes depending on your internet speed and hardware. Subsequent startups will be much faster (typically under 1 minute if the container already exists).

### For Troubleshooting: Manual Setup

If you need to start components individually:

#### 1. Start the Docker Container

Use our scripts that automatically detect your system configuration and GPU availability:

```bash
# Windows (Command Prompt)
start_docker.bat

# Windows (PowerShell)
./start_docker.ps1

# Linux/macOS
chmod +x start_docker.sh
./start_docker.sh
```

#### 2. Start the Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### 3. Start the Frontend

```bash
cd frontend
pip install -r requirements.txt
python app.py
```

Then open your browser to: http://localhost:5173

## Usage

1. Ensure the Docker container is running (green indicator in the UI)
2. Upload a German payslip (PDF, JPG, PNG)
3. View the extracted information
4. (Optional) Enter an employee ID to validate the extracted data

## Configuration

The system is configured via the `backend/config.yml` file. A comprehensive example with all possible options is available in `config_example.yml`.

For this project, we're using the quadrant window mode with only top_left and bottom_right windows being processed:

```yaml
# Processing Settings
processing:
  mode: "direct"
  window_mode: "quadrant"  # Divide the document into four quadrants
  selected_windows:        # Only process these specific quadrants
    - "top_left"           # Contains employee name
    - "bottom_right"       # Contains net amount
```

### Custom Prompts

You can customize the instructions sent to the model for each window using multiline YAML strings:

```yaml
prompts:
  quadrant:
    top_left: |
      Extract employee name from this part of the German payslip.
      Look for text after 'Name' or 'Herrn/Frau'.
      Return JSON: {"found_in_top_left": {"employee_name": "NAME"}}
```

## Docker Container API

The Docker container exposes these endpoints:

- `/process/pdf` - Process PDF files
- `/process/image` - Process image files
- `/status` - Get container status and GPU information

The container accepts custom processing parameters including window modes and custom prompts.

## Troubleshooting

- **No Docker Container**: If the status indicator is red, ensure Docker is running with:
  ```bash
  docker ps | grep qwen-payslip-processor
  ```
  
- **Container Issues**: If needed, restart the container:
  ```bash
  docker restart qwen-payslip-processor
  ```

- **Memory Errors**: If you encounter "Out of Memory" errors when pulling or running the container:
  1. Stop all running Docker containers: `docker stop $(docker ps -q)`
  2. For Windows: Configure WSL2 memory settings in `.wslconfig`
  3. For all platforms: Increase Docker Desktop memory allocation
  4. Restart Docker Desktop completely

- **GPU Issues**: If GPU acceleration isn't working:
  1. Ensure your GPU drivers are up to date
  2. For NVIDIA: Install NVIDIA Container Toolkit
  3. Check Docker logs: `docker logs qwen-payslip-processor`

- **Logs**: Check backend logs in `backend/logs/payslip_processor.log`

## License

MIT
