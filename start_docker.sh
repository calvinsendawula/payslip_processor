#!/bin/bash

echo "=========================================================="
echo "      Qwen Payslip Processor - Docker Container Starter"
echo "=========================================================="
echo
echo "This script will help you start the Qwen Payslip Processor Docker container."
echo
echo "Prerequisites:"
echo " - Docker installed and running"
echo " - Internet connection for initial container download"
echo
echo "IMPORTANT NOTES:"
echo " - First download is ~14GB and may take 15-60 minutes depending on your connection"
echo " - Initial container startup takes 5-10 minutes while the model loads"
echo " - Container is ready when the backend detects it or when logs show:"
echo "   \"Model loaded successfully\" and \"Uvicorn running on http://0.0.0.0:27842\""
echo " - Check progress with: docker logs qwen-payslip-processor"
echo

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed or not in your PATH."
    echo "Please install Docker from https://docs.docker.com/get-docker/"
    echo
    exit 1
fi

# Check Docker status
echo "Checking Docker status..."
if ! docker info &> /dev/null; then
    echo "ERROR: Docker is not running or not accessible."
    echo "Please start Docker and try again."
    echo
    exit 1
fi

# Check for WSL2 if running on Windows
if grep -q Microsoft /proc/version 2>/dev/null; then
    echo "Running on Windows Subsystem for Linux (WSL2)"
    
    # Check for WSL config
    WSL_CONFIG_PATH="$(wslpath "$(wslvar USERPROFILE)" 2>/dev/null)/.wslconfig"
    if [ -f "$WSL_CONFIG_PATH" ]; then
        echo "Found .wslconfig file. Current WSL configuration:"
        cat "$WSL_CONFIG_PATH"
        
        # Check if the config contains memory settings
        if ! grep -q "memory=" "$WSL_CONFIG_PATH"; then
            echo "WARNING: Existing .wslconfig does not specify memory limits."
            echo "For optimal performance with large models, consider adding these settings:"
            echo
            echo "[wsl2]"
            echo "memory=16GB"
            echo "processors=8"
            echo "swap=32GB"
            echo "gpuSupport=true"
            echo
            
            read -p "Would you like to modify your existing .wslconfig file? (Y/N): " modify_config
            if [[ $modify_config == [yY] || $modify_config == [yY][eE][sS] ]]; then
                echo "You chose to modify your existing .wslconfig file."
                echo
                echo "!!! WARNING: This will backup your current config to .wslconfig.bak !!!"
                echo
                read -p "Are you sure you want to continue? (Y/N): " confirm_modify
                if [[ $confirm_modify == [yY] || $confirm_modify == [yY][eE][sS] ]]; then
                    echo "Backing up current config..."
                    cp "$WSL_CONFIG_PATH" "${WSL_CONFIG_PATH}.bak"
                    
                    echo "Creating new WSL config file..."
                    echo "[wsl2]" > "$WSL_CONFIG_PATH"
                    echo "memory=16GB" >> "$WSL_CONFIG_PATH"
                    echo "processors=8" >> "$WSL_CONFIG_PATH"
                    echo "swap=32GB" >> "$WSL_CONFIG_PATH"
                    echo "gpuSupport=true" >> "$WSL_CONFIG_PATH"
                    echo "Updated $WSL_CONFIG_PATH successfully."
                    echo "Your previous config was backed up to ${WSL_CONFIG_PATH}.bak"
                    echo "You may need to restart Docker/WSL for these settings to take effect."
                    echo "To restart WSL, run: wsl --shutdown"
                fi
            fi
        else
            echo "Your .wslconfig appears to have memory settings configured."
        fi
    else
        echo "No .wslconfig found. For optimal performance with large models, consider creating:"
        echo "~/.wslconfig on your Windows host with the following content:"
        echo
        echo "[wsl2]"
        echo "memory=16GB"
        echo "processors=8"
        echo "swap=32GB"
        echo "gpuSupport=true"
        echo
        echo "WARNING: Without these settings, Docker might run out of memory when pulling or running the container."
        
        read -p "Would you like to create this file now? (Y/N): " create_config
        if [[ $create_config == [yY] || $create_config == [yY][eE][sS] ]]; then
            echo "Creating WSL config file..."
            echo "[wsl2]" > "$WSL_CONFIG_PATH"
            echo "memory=16GB" >> "$WSL_CONFIG_PATH"
            echo "processors=8" >> "$WSL_CONFIG_PATH"
            echo "swap=32GB" >> "$WSL_CONFIG_PATH"
            echo "gpuSupport=true" >> "$WSL_CONFIG_PATH"
            echo "Created $WSL_CONFIG_PATH successfully."
            echo "You may need to restart Docker/WSL for these settings to take effect."
            echo "To restart WSL, run: wsl --shutdown"
        fi
    fi
fi

# Check disk space
echo
echo "Checking available disk space..."
# Determine OS for disk space check
if [ "$(uname)" = "Darwin" ]; then
    # macOS
    DISK_FREE=$(df -h . | awk 'NR==2 {print $4}')
    DISK_FREE_GB=$(df -g . | awk 'NR==2 {print $4}')
    echo "Available disk space: $DISK_FREE ($DISK_FREE_GB GB)"
    
    if [ "$DISK_FREE_GB" -lt 20 ]; then
        echo
        echo "WARNING: Less than 20GB of free disk space available!"
        echo "The Docker image requires at least 14GB for download plus additional space."
        echo "Insufficient disk space may cause download failures."
        echo
        read -p "Do you want to continue anyway? (Y/N): " continue_anyway
        if [[ ! $continue_anyway == [yY] && ! $continue_anyway == [yY][eE][sS] ]]; then
            echo "Operation cancelled due to low disk space."
            exit 1
        fi
    fi
else
    # Linux
    DISK_FREE=$(df -h . | awk 'NR==2 {print $4}')
    # Try to extract GB value from human-readable format (e.g., "10G")
    DISK_FREE_GB=$(df -h . | awk 'NR==2 {print $4}' | grep -o -E '[0-9]+' | head -1)
    echo "Available disk space: $DISK_FREE"
    
    if [ -n "$DISK_FREE_GB" ] && [ "$DISK_FREE_GB" -lt 20 ]; then
        echo
        echo "WARNING: Less than 20GB of free disk space available!"
        echo "The Docker image requires at least 14GB for download plus additional space."
        echo "Insufficient disk space may cause download failures."
        echo
        read -p "Do you want to continue anyway? (Y/N): " continue_anyway
        if [[ ! $continue_anyway == [yY] && ! $continue_anyway == [yY][eE][sS] ]]; then
            echo "Operation cancelled due to low disk space."
            exit 1
        fi
    fi
fi

# Check for port availability
echo
echo "Checking if port 27842 is available..."
if command -v lsof &>/dev/null; then
    if lsof -i :27842 &>/dev/null; then
        echo
        echo "WARNING: Port 27842 appears to be in use by another application!"
        echo "This will cause conflicts when starting the Docker container."
        echo
        echo "Please close the application using this port before continuing."
        read -p "Do you want to continue anyway? (Y/N): " continue_anyway
        if [[ ! $continue_anyway == [yY] && ! $continue_anyway == [yY][eE][sS] ]]; then
            echo "Operation cancelled due to port conflict."
            exit 1
        fi
    else
        echo "Port 27842 is available."
    fi
else
    # If lsof is not available, try using netstat
    if command -v netstat &>/dev/null; then
        if netstat -tuln | grep -q ":27842\b"; then
            echo
            echo "WARNING: Port 27842 appears to be in use by another application!"
            echo "This will cause conflicts when starting the Docker container."
            echo
            echo "Please close the application using this port before continuing."
            read -p "Do you want to continue anyway? (Y/N): " continue_anyway
            if [[ ! $continue_anyway == [yY] && ! $continue_anyway == [yY][eE][sS] ]]; then
                echo "Operation cancelled due to port conflict."
                exit 1
            fi
        else
            echo "Port 27842 is available."
        fi
    else
        echo "Unable to check port availability (neither lsof nor netstat found)."
    fi
fi

echo
echo "Checking if the container is already running..."
# Check by port first, then by name
if docker ps | grep -q "27842/tcp"; then
    echo
    echo "A Docker container using port 27842 is already running."
    echo
    docker ps | grep "27842/tcp"
    echo
    echo "Container is already running! You can start using the application."
    exit 0
else
    # Check specifically for our named container
    if docker ps | grep -q "qwen-payslip-processor"; then
        echo
        echo "The qwen-payslip-processor container is running (on a custom port)."
        echo
        docker ps | grep "qwen-payslip-processor"
        echo
        echo "Container is already running! You can start using the application."
        echo "Note: The container is using a non-standard port. Make sure your backend is configured correctly."
        exit 0
    fi
fi

# Check if container exists but is stopped (check both by name and by port configuration)
echo "Checking if a suitable container exists but is stopped..."

# Try to find container by name first
CONTAINER_ID=$(docker ps -a --filter "name=qwen-payslip-processor" --format "{{.ID}}" | head -n 1)

# If that didn't work, try by port configuration
if [ -z "$CONTAINER_ID" ]; then
    CONTAINER_ID=$(docker ps -a --filter "publish=27842" --format "{{.ID}}" | head -n 1)
fi

if [ -n "$CONTAINER_ID" ]; then
    echo
    echo "Found existing suitable container (ID: $CONTAINER_ID). Starting container..."
    docker start $CONTAINER_ID
    
    if [ $? -eq 0 ]; then
        echo
        echo "Container started successfully! The backend will now be able to communicate with it."
        echo
        echo "You can now start the backend and frontend applications."
        echo "The container status will be displayed in the UI."
        exit 0
    else
        echo
        echo "Failed to start existing container. It may be corrupted."
        echo
        read -p "Do you want to remove the container and create a new one? (Y/N): " remove_container
        if [[ $remove_container == [yY] || $remove_container == [yY][eE][sS] ]]; then
            docker rm $CONTAINER_ID
            echo "Removed existing container. Will create a new one."
        else
            echo "Container startup cancelled."
            exit 1
        fi
    fi
else
    echo "No existing containers found that match our requirements."
fi

# Check for NVIDIA GPU support
echo "Checking for GPU support..."
GPU_AVAILABLE=false
DOCKER_GPU_PARAM=""

# Check for NVIDIA GPU
if command -v nvidia-smi &> /dev/null && nvidia-smi &> /dev/null; then
    # Test if nvidia-docker is configured correctly
    if docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi &> /dev/null; then
        echo "NVIDIA GPU detected and nvidia-docker is working!"
        GPU_AVAILABLE=true
        DOCKER_GPU_PARAM="--gpus all"
    else
        echo "NVIDIA GPU detected but nvidia-docker is not configured correctly."
        echo "See https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html"
    fi
# Check for macOS with Metal GPU support
elif [ "$(uname)" = "Darwin" ] && sysctl -n machdep.cpu.brand_string | grep -q "Apple"; then
    echo "Apple Silicon detected. Docker will use Metal for GPU acceleration if available."
    # No special flags needed for Docker Desktop on macOS - it will use Metal automatically
else
    echo "No compatible GPU detected or drivers not installed. Container will run on CPU."
fi

# Check if the image exists locally
echo
echo "Checking if Docker image exists locally..."
if docker images | grep -q "calvin189/qwen-payslip-processor"; then
    echo "Found local image. No need to download."
    NEED_PULL=0
else
    echo "Image not found locally. Will need to download (~14GB)."
    NEED_PULL=1
fi

echo
echo "Starting Qwen Payslip Processor container..."
echo

if [ "$GPU_AVAILABLE" = true ]; then
    echo "Using GPU acceleration with the following command:"
    echo "docker run -d -p 27842:27842 $DOCKER_GPU_PARAM --name qwen-payslip-processor --memory=12g --memory-swap=24g --shm-size=1g calvin189/qwen-payslip-processor:latest"
else
    echo "Using CPU with the following command:"
    echo "docker run -d -p 27842:27842 --name qwen-payslip-processor --memory=12g --memory-swap=24g --shm-size=1g calvin189/qwen-payslip-processor:latest"
fi
echo

if [ $NEED_PULL -eq 1 ]; then
    echo "This will download a large (~14GB) Docker image and may take 15-60+ minutes depending on your connection."
else
    echo "No download needed. Container will start using local image."
fi

read -p "Do you want to start the container now? (Y/N): " confirm
if [[ $confirm == [yY] || $confirm == [yY][eE][sS] ]]; then
    echo
    
    if [ $NEED_PULL -eq 1 ]; then
        echo "Downloading the Docker image first (~14GB)..."
        echo "This will take significant time. Please be patient."
        
        docker pull calvin189/qwen-payslip-processor:latest
        
        if [ $? -ne 0 ]; then
            echo
            echo "ERROR: Failed to download the Docker image."
            echo "This could be due to network issues or insufficient disk space."
            echo
            exit 1
        fi
    fi
    
    echo
    echo "Starting the Docker container..."
    echo
    echo "IMPORTANT: Initial startup takes 5-10 minutes while the model loads."
    echo "Do not interrupt the process. Check progress with: docker logs qwen-payslip-processor" 
    echo "The container is ready when you see: \"Model loaded successfully\""
    echo
    
    if [ "$GPU_AVAILABLE" = true ]; then
        docker run -d -p 27842:27842 $DOCKER_GPU_PARAM --name qwen-payslip-processor --memory=12g --memory-swap=24g --shm-size=1g calvin189/qwen-payslip-processor:latest
    else
        docker run -d -p 27842:27842 --name qwen-payslip-processor --memory=12g --memory-swap=24g --shm-size=1g calvin189/qwen-payslip-processor:latest
    fi
    
    if [ $? -eq 0 ]; then
        echo
        echo "Container starting! The backend will automatically detect when it's ready."
        echo "Check progress with: docker logs qwen-payslip-processor"
        echo
        echo "Expected logs when ready:"
        echo "Loading checkpoint shards: 100%|██████████| 4/4 [00:07<00:00,  1.93s/it]"
        echo "Model loaded successfully!"
        echo "Uvicorn running on http://0.0.0.0:27842"
        
        # Check container status after a few seconds
        echo
        echo "Waiting 10 seconds to verify container is running properly..."
        sleep 10
        if ! docker ps | grep -q "qwen-payslip-processor"; then
            echo
            echo "WARNING: Container started but stopped immediately. Checking logs..."
            echo
            docker logs qwen-payslip-processor
            echo
            echo "Container failed to stay running. This is usually due to memory issues."
            echo "Please check the logs above for specific errors."
        else
            echo "Container verified and running!"
        fi
    else
        echo
        echo "ERROR: Failed to start the container. This could be due to:"
        echo " - Not enough memory allocated to Docker"
        echo " - The container name is already in use (try: docker rm qwen-payslip-processor)"
        echo " - Permission issues or other Docker configuration problems"
        echo
        echo "Try the following steps if you encounter memory-related errors:"
        echo "1. Stop all running Docker containers (docker stop \$(docker ps -q))"
        echo "2. Increase Docker memory limits in Docker Desktop settings"
        echo "3. Restart Docker completely"
        if grep -q Microsoft /proc/version 2>/dev/null; then
            echo "4. Create or modify .wslconfig on Windows with memory settings"
            echo "5. Restart WSL with: wsl --shutdown"
        fi
        
        # Offer recovery options
        echo
        echo "Would you like to:"
        echo "1. Try to remove the existing container (if name conflict)"
        echo "2. Show Docker system information (useful for diagnostics)"
        echo "3. Exit"
        read -p "Enter option (1-3): " recovery_option
        
        if [ "$recovery_option" = "1" ]; then
            echo "Attempting to remove existing container..."
            docker rm qwen-payslip-processor
            
            echo "Retrying container startup..."
            if [ "$GPU_AVAILABLE" = true ]; then
                docker run -d -p 27842:27842 $DOCKER_GPU_PARAM --name qwen-payslip-processor --memory=12g --memory-swap=24g --shm-size=1g calvin189/qwen-payslip-processor:latest
            else
                docker run -d -p 27842:27842 --name qwen-payslip-processor --memory=12g --memory-swap=24g --shm-size=1g calvin189/qwen-payslip-processor:latest
            fi
            
            if [ $? -eq 0 ]; then
                echo "Container started successfully on second attempt!"
            else
                echo "Failed to start container even after removing existing one."
                echo "See error details above."
            fi
        elif [ "$recovery_option" = "2" ]; then
            echo
            echo "Docker system information:"
            echo
            docker system info
            echo
            docker system df
        fi
    fi
else
    echo
    echo "Container startup cancelled."
fi

echo
echo "You can now start the backend and frontend applications."
echo "The container status will be displayed in the UI."

# Add section at the end for manual Docker image management
echo
echo "=========================================================="
echo "REFERENCE: Manual Docker Container Management"
echo "=========================================================="
echo
echo "If you prefer to manage the Docker container separately or run it on another machine:"
echo
echo "1. Pull the image manually:"
echo "   docker pull calvin189/qwen-payslip-processor:latest"
echo
echo "2. Run with GPU support:"
echo "   docker run -d -p 27842:27842 --gpus all --name qwen-payslip-processor --memory=12g --memory-swap=24g --shm-size=1g calvin189/qwen-payslip-processor:latest"
echo
echo "3. Run without GPU (CPU only):"
echo "   docker run -d -p 27842:27842 --name qwen-payslip-processor --memory=12g --memory-swap=24g --shm-size=1g calvin189/qwen-payslip-processor:latest"
echo
echo "4. Using a custom port (replace PORT with your preferred port):"
echo "   docker run -d -p PORT:27842 --name qwen-payslip-processor --memory=12g --memory-swap=24g --shm-size=1g calvin189/qwen-payslip-processor:latest"
echo
echo "5. When running on a separate machine, update the backend's config_payslip.yml and config_property.yml:"
echo "   host: \"machine-ip-address\"  (Replace with the IP of the Docker host)"
echo "   port: 27842  (Or your custom port if changed)"
echo
echo "=========================================================="
echo 