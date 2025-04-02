#!/bin/bash

# Qwen Payslip Processor - Application Starter (Linux/macOS)
echo "=========================================================="
echo "     Qwen Payslip Processor - Application Starter"
echo "=========================================================="
echo
echo "This script will start the entire Qwen Payslip Processor application:"
echo " 1. Ensure Docker container is running"
echo " 2. Start the backend server"
echo " 3. Start the frontend web interface"
echo

# Check Docker is installed
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed or not in your PATH."
    echo "Please install Docker from https://docs.docker.com/get-docker/"
    echo
    read -p "Press Enter to exit" 
    exit 1
fi

# Check Docker is running
echo "Checking Docker status..."
if ! docker info &> /dev/null; then
    echo "ERROR: Docker is not running or not accessible."
    echo "Please start Docker and try again."
    echo
    read -p "Press Enter to exit" 
    exit 1
fi

# Check if container is running
echo "Checking Docker container status..."
if ! docker ps | grep -q "27842/tcp"; then
    echo
    echo "Docker container is not running. Checking if it exists..."
    
    # Check if container exists but is stopped
    if docker ps -a | grep -q "qwen-payslip-processor"; then
        echo "Container exists but is not running. Starting existing container..."
        docker start qwen-payslip-processor
        
        if [ $? -eq 0 ]; then
            echo "Container started successfully!"
        else
            echo "Failed to start existing container. It may be corrupted."
            
            read -p "Do you want to remove the container and create a new one? (Y/N): " remove_container
            if [[ $remove_container == [yY] || $remove_container == [yY][eE][sS] ]]; then
                docker rm qwen-payslip-processor
                echo "Removed existing container. Will create a new one."
                
                # Run start_docker.sh to create a new container
                echo "Running container setup script..."
                bash ./start_docker.sh
                
                # Check if container was created and started
                if ! docker ps | grep -q "27842/tcp"; then
                    echo "ERROR: Container failed to start."
                    echo "This could be due to:"
                    echo " - Not enough memory allocated to Docker"
                    echo " - Network connection issues when pulling the image"
                    echo " - Port 27842 is already in use by another application"
                    echo
                    echo "Let's check if Docker is running properly:"
                    
                    # Additional diagnostic information
                    echo "1. Checking Docker system info..."
                    docker system info | grep -E "Memory|CPU"
                    
                    echo "2. Checking port availability..."
                    if lsof -i :27842 2>/dev/null; then
                        echo " - Port 27842 is already in use!"
                        echo " - Please close the application using this port and try again."
                    else
                        echo " - Port 27842 is available."
                    fi
                    
                    # Check images
                    echo "3. Checking if Docker image exists..."
                    if ! docker images | grep -q "calvin189/qwen-payslip-processor"; then
                        echo " - Image does not exist locally, download is required (~14GB)"
                        echo " - Make sure you have a stable internet connection"
                    else
                        echo " - Image exists locally."
                    fi
                    
                    # Provide user with recovery options
                    echo
                    echo "Please try the following:"
                    echo "1. Run start_docker.sh manually to see detailed errors"
                    echo "2. Restart Docker and try again"
                    echo "3. Make sure you have enough memory available in Docker resources"
                    echo "4. For detailed logs use: docker logs qwen-payslip-processor"
                    echo
                    
                    # Offer to try running start_docker.sh directly
                    read -p "Do you want to manually run start_docker.sh now? (Y/N): " try_again
                    if [[ $try_again == [yY] || $try_again == [yY][eE][sS] ]]; then
                        echo "Starting start_docker.sh directly..."
                        bash ./start_docker.sh
                        
                        # Check again if container is running after manual run
                        if ! docker ps | grep -q "27842/tcp"; then
                            echo "Container still not running. Please address the issues shown in start_docker.sh"
                            read -p "Press Enter to exit"
                            exit 1
                        else
                            echo "Success! Container is now running."
                        fi
                    else
                        read -p "Press Enter to exit"
                        exit 1
                    fi
                fi
            else
                echo "Container startup cancelled."
                read -p "Press Enter to exit"
                exit 1
            fi
        fi
    else
        # Container doesn't exist, run start_docker.sh
        echo "Container doesn't exist. Running container setup script..."
        bash ./start_docker.sh
        
        # Check if container was created and started
        if ! docker ps | grep -q "27842/tcp"; then
            echo "ERROR: Container failed to start."
            echo "Please check the output from start_docker.sh for detailed error information."
            echo "You may need to adjust Docker settings, particularly memory allocation."
            echo
            echo "For detailed logs, run: docker logs qwen-payslip-processor"
            
            read -p "Press Enter to exit"
            exit 1
        else
            echo "Container successfully created and started!"
        fi
    fi
else
    echo "Docker container is running."
fi

echo
echo "Setting up Python environment..."

# Check Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed or not in your PATH."
    echo "Please install Python 3.11+ from https://www.python.org/downloads/"
    echo
    read -p "Press Enter to exit"
    exit 1
fi

# Check for existing virtual environment in root directory
if [ -d ".venv" ]; then
    echo "Found existing virtual environment in root directory."
    
    # Check activation script
    if [ -f ".venv/bin/activate" ]; then
        echo "Using existing virtual environment."
        VENV_EXISTS=true
    else
        echo "WARNING: Virtual environment exists but activation script not found."
        VENV_EXISTS=false
    fi
else
    echo "No virtual environment found. Creating one in the root directory..."
    python3 -m venv .venv
    
    if [ $? -eq 0 ]; then
        echo "Virtual environment created successfully!"
        VENV_EXISTS=true
    else
        echo "WARNING: Failed to create virtual environment. Will use global Python."
        VENV_EXISTS=false
    fi
fi

# Install dependencies in root venv if it exists
if [ "$VENV_EXISTS" = true ] && [ -f ".venv/bin/activate" ]; then
    echo "Installing dependencies in the virtual environment..."
    source .venv/bin/activate
    pip install -r requirements.txt
    
    if [ $? -eq 0 ]; then
        echo "Dependencies installed successfully."
    else
        echo "WARNING: Error installing dependencies."
    fi
    deactivate
fi

echo
echo "Starting the backend and frontend applications..."

# Determine the OS type
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    OPEN_CMD="open"
else
    # Linux
    OPEN_CMD="xdg-open"
fi

# Start the backend in a new terminal window
echo "Starting backend server..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    if [ "$VENV_EXISTS" = true ]; then
        osascript -e 'tell app "Terminal" to do script "cd '$(pwd)' && source .venv/bin/activate && cd backend && pip install -r requirements.txt && python3 -m uvicorn app.main:app --reload --port 8000"'
    else
        osascript -e 'tell app "Terminal" to do script "cd '$(pwd)'/backend && python3 -m pip install -r requirements.txt && python3 -m uvicorn app.main:app --reload --port 8000"'
    fi
else
    # Linux - try to detect the terminal
    if command -v gnome-terminal &> /dev/null; then
        if [ "$VENV_EXISTS" = true ]; then
            gnome-terminal -- bash -c "cd $(pwd) && source .venv/bin/activate && cd backend && pip install -r requirements.txt && python3 -m uvicorn app.main:app --reload --port 8000; exec bash"
        else
            gnome-terminal -- bash -c "cd $(pwd)/backend && python3 -m pip install -r requirements.txt && python3 -m uvicorn app.main:app --reload --port 8000; exec bash"
        fi
    elif command -v xterm &> /dev/null; then
        if [ "$VENV_EXISTS" = true ]; then
            xterm -e "cd $(pwd) && source .venv/bin/activate && cd backend && pip install -r requirements.txt && python3 -m uvicorn app.main:app --reload --port 8000; exec bash" &
        else
            xterm -e "cd $(pwd)/backend && python3 -m pip install -r requirements.txt && python3 -m uvicorn app.main:app --reload --port 8000; exec bash" &
        fi
    elif command -v konsole &> /dev/null; then
        if [ "$VENV_EXISTS" = true ]; then
            konsole --new-tab -e "cd $(pwd) && source .venv/bin/activate && cd backend && pip install -r requirements.txt && python3 -m uvicorn app.main:app --reload --port 8000; exec bash" &
        else
            konsole --new-tab -e "cd $(pwd)/backend && python3 -m pip install -r requirements.txt && python3 -m uvicorn app.main:app --reload --port 8000; exec bash" &
        fi
    else
        echo "WARNING: Could not determine terminal. Starting backend in background."
        if [ "$VENV_EXISTS" = true ]; then
            (cd $(pwd) && source .venv/bin/activate && cd backend && pip install -r requirements.txt && python3 -m uvicorn app.main:app --reload --port 8000) &
        else
            (cd backend && python3 -m pip install -r requirements.txt && python3 -m uvicorn app.main:app --reload --port 8000) &
        fi
    fi
fi

# Start the frontend in a new terminal window
echo "Starting frontend web interface..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    if [ "$VENV_EXISTS" = true ]; then
        osascript -e 'tell app "Terminal" to do script "cd '$(pwd)' && source .venv/bin/activate && cd frontend && pip install -r requirements.txt && python3 app.py"'
    else
        osascript -e 'tell app "Terminal" to do script "cd '$(pwd)'/frontend && python3 -m pip install -r requirements.txt && python3 app.py"'
    fi
else
    # Linux - try to detect the terminal
    if command -v gnome-terminal &> /dev/null; then
        if [ "$VENV_EXISTS" = true ]; then
            gnome-terminal -- bash -c "cd $(pwd) && source .venv/bin/activate && cd frontend && pip install -r requirements.txt && python3 app.py; exec bash"
        else
            gnome-terminal -- bash -c "cd $(pwd)/frontend && python3 -m pip install -r requirements.txt && python3 app.py; exec bash"
        fi
    elif command -v xterm &> /dev/null; then
        if [ "$VENV_EXISTS" = true ]; then
            xterm -e "cd $(pwd) && source .venv/bin/activate && cd frontend && pip install -r requirements.txt && python3 app.py; exec bash" &
        else
            xterm -e "cd $(pwd)/frontend && python3 -m pip install -r requirements.txt && python3 app.py; exec bash" &
        fi
    elif command -v konsole &> /dev/null; then
        if [ "$VENV_EXISTS" = true ]; then
            konsole --new-tab -e "cd $(pwd) && source .venv/bin/activate && cd frontend && pip install -r requirements.txt && python3 app.py; exec bash" &
        else
            konsole --new-tab -e "cd $(pwd)/frontend && python3 -m pip install -r requirements.txt && python3 app.py; exec bash" &
        fi
    else
        echo "WARNING: Could not determine terminal. Starting frontend in background."
        if [ "$VENV_EXISTS" = true ]; then
            (cd $(pwd) && source .venv/bin/activate && cd frontend && pip install -r requirements.txt && python3 app.py) &
        else
            (cd frontend && python3 -m pip install -r requirements.txt && python3 app.py) &
        fi
    fi
fi

echo
echo "Application starting!"
echo
echo "The web interface will open automatically in your browser."
echo "If it doesn't open automatically, access it at: http://localhost:5173"
echo
echo "Container logs can be viewed with: docker logs qwen-payslip-processor"
echo
echo "To stop the application:"
echo " 1. Close the terminal windows or use Ctrl+C in each window"
echo " 2. (Optional) Stop the container with: docker stop qwen-payslip-processor"

# Wait a moment for services to start
sleep 5

# Open the application in the browser
if command -v $OPEN_CMD &> /dev/null; then
    $OPEN_CMD "http://localhost:5173"
else
    echo "Could not automatically open browser. Please navigate to http://localhost:5173"
fi 