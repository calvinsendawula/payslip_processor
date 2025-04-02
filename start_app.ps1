# Qwen Payslip Processor - Application Starter (PowerShell)
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "     Qwen Payslip Processor - Application Starter" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This script will start the entire Qwen Payslip Processor application:"
Write-Host " 1. Ensure Docker container is running"
Write-Host " 2. Start the backend server"
Write-Host " 3. Start the frontend web interface"
Write-Host ""

# Check Docker is installed
try {
    $null = Get-Command docker -ErrorAction Stop
} catch {
    Write-Host "ERROR: Docker is not installed or not in your PATH." -ForegroundColor Red
    Write-Host "Please install Docker Desktop from https://www.docker.com/products/docker-desktop"
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Check Docker is running
Write-Host "Checking Docker status..." -ForegroundColor Yellow
try {
    $null = docker info
} catch {
    Write-Host "ERROR: Docker Desktop is not running or not accessible." -ForegroundColor Red
    Write-Host "Please start Docker Desktop and try again."
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if container is running
Write-Host "Checking Docker container status..." -ForegroundColor Yellow
$containerRunning = docker ps | Select-String "27842/tcp"

if ($null -eq $containerRunning) {
    Write-Host ""
    Write-Host "Docker container is not running. Checking if it exists..." -ForegroundColor Yellow
    
    # Check if container exists but is stopped
    $containerExists = docker ps -a | Select-String "qwen-payslip-processor"
    
    if ($null -ne $containerExists) {
        Write-Host "Container exists but is not running. Starting existing container..." -ForegroundColor Yellow
        docker start qwen-payslip-processor
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Container started successfully!" -ForegroundColor Green
        } else {
            Write-Host "Failed to start existing container. It may be corrupted." -ForegroundColor Red
            
            $removeContainer = Read-Host "Do you want to remove the container and create a new one? (Y/N)"
            if ($removeContainer -eq "Y" -or $removeContainer -eq "y") {
                docker rm qwen-payslip-processor
                Write-Host "Removed existing container. Will create a new one." -ForegroundColor Yellow
                
                # Run start_docker.bat to create a new container
                Write-Host "Running container setup script..." -ForegroundColor Yellow
                Start-Process -FilePath "cmd.exe" -ArgumentList "/c start_docker.bat" -Wait
                
                # Check if container was created and started
                $containerRunning = docker ps | Select-String "27842/tcp"
                if ($null -eq $containerRunning) {
                    Write-Host "ERROR: Container failed to start." -ForegroundColor Red
                    Write-Host "This could be due to:" -ForegroundColor Yellow
                    Write-Host " - Not enough memory allocated to Docker" -ForegroundColor Yellow
                    Write-Host " - Network connection issues when pulling the image" -ForegroundColor Yellow
                    Write-Host " - Port 27842 is already in use by another application" -ForegroundColor Yellow
                    Write-Host ""
                    Write-Host "Let's check if Docker is running properly:" -ForegroundColor Cyan
                    
                    # Additional diagnostic information
                    Write-Host "1. Checking Docker memory settings..." -ForegroundColor Cyan
                    $wslConfig = Get-Content "$env:USERPROFILE\.wslconfig" -ErrorAction SilentlyContinue
                    if ($null -eq $wslConfig) {
                        Write-Host " - No .wslconfig file found!" -ForegroundColor Red
                        Write-Host " - For optimal performance with this container, create a file at:" -ForegroundColor Yellow
                        Write-Host "   $env:USERPROFILE\.wslconfig" -ForegroundColor Yellow
                        Write-Host " - With this content:" -ForegroundColor Yellow
                        Write-Host "[wsl2]" -ForegroundColor Yellow
                        Write-Host "memory=16GB" -ForegroundColor Yellow
                        Write-Host "processors=8" -ForegroundColor Yellow
                        Write-Host "swap=32GB" -ForegroundColor Yellow
                        Write-Host "gpuSupport=true" -ForegroundColor Yellow
                    } else {
                        Write-Host " - .wslconfig file found with settings:" -ForegroundColor Green
                        $wslConfig | ForEach-Object { Write-Host "   $_" -ForegroundColor Cyan }
                    }
                    
                    Write-Host "2. Checking port availability..." -ForegroundColor Cyan
                    $portInUse = netstat -ano | Select-String "27842"
                    if ($null -ne $portInUse) {
                        Write-Host " - Port 27842 is already in use!" -ForegroundColor Red
                        Write-Host " - Please close the application using this port and try again." -ForegroundColor Yellow
                    } else {
                        Write-Host " - Port 27842 is available." -ForegroundColor Green
                    }
                    
                    # Check images
                    Write-Host "3. Checking if Docker image exists..." -ForegroundColor Cyan
                    $imageExists = docker images | Select-String "calvin189/qwen-payslip-processor"
                    if ($null -eq $imageExists) {
                        Write-Host " - Image does not exist locally, download is required (~14GB)" -ForegroundColor Yellow
                        Write-Host " - Make sure you have a stable internet connection" -ForegroundColor Yellow
                    } else {
                        Write-Host " - Image exists locally." -ForegroundColor Green
                    }
                    
                    # Provide user with recovery options
                    Write-Host ""
                    Write-Host "Please try the following:" -ForegroundColor Cyan
                    Write-Host "1. Run start_docker.bat manually to see detailed errors" -ForegroundColor Yellow
                    Write-Host "2. Restart Docker Desktop and try again" -ForegroundColor Yellow
                    Write-Host "3. Make sure you have at least 16GB available in Docker resources" -ForegroundColor Yellow
                    Write-Host "4. For detailed logs use: docker logs qwen-payslip-processor" -ForegroundColor Yellow
                    Write-Host ""
                    
                    # Offer to try running start_docker.bat directly
                    $tryAgain = Read-Host "Do you want to manually run start_docker.bat now? (Y/N)"
                    if ($tryAgain -eq "Y" -or $tryAgain -eq "y") {
                        Write-Host "Starting start_docker.bat directly..." -ForegroundColor Cyan
                        # Use Start-Process with -NoNewWindow to see output in same window
                        Start-Process -FilePath "cmd.exe" -ArgumentList "/c start_docker.bat" -NoNewWindow -Wait
                        
                        # Check again if container is running after manual run
                        $containerRunning = docker ps | Select-String "27842/tcp"
                        if ($null -eq $containerRunning) {
                            Write-Host "Container still not running. Please address the issues shown in start_docker.bat" -ForegroundColor Red
                            Read-Host "Press Enter to exit"
                            exit 1
                        } else {
                            Write-Host "Success! Container is now running." -ForegroundColor Green
                        }
                    } else {
                        Read-Host "Press Enter to exit"
                        exit 1
                    }
                }
            } else {
                Write-Host "Container startup cancelled." -ForegroundColor Red
                Read-Host "Press Enter to exit"
                exit 1
            }
        }
    } else {
        # Container doesn't exist, run start_docker.bat
        Write-Host "Container doesn't exist. Running container setup script..." -ForegroundColor Yellow
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c start_docker.bat" -NoNewWindow -Wait
        
        # Check if container was created and started
        $containerRunning = docker ps | Select-String "27842/tcp"
        if ($null -eq $containerRunning) {
            Write-Host "ERROR: Container failed to start." -ForegroundColor Red
            Write-Host "Please check the output from start_docker.bat for detailed error information." -ForegroundColor Yellow
            Write-Host "You may need to adjust Docker settings, particularly memory allocation." -ForegroundColor Yellow
            Write-Host ""
            Write-Host "For detailed logs, run: docker logs qwen-payslip-processor" -ForegroundColor Yellow
            
            Read-Host "Press Enter to exit"
            exit 1
        } else {
            Write-Host "Container successfully created and started!" -ForegroundColor Green
        }
    }
} else {
    Write-Host "Docker container is running." -ForegroundColor Green
}

Write-Host ""
Write-Host "Starting the backend and frontend applications..." -ForegroundColor Cyan

# Check Python is installed
try {
    $null = Get-Command python -ErrorAction Stop
} catch {
    Write-Host "ERROR: Python is not installed or not in your PATH." -ForegroundColor Red
    Write-Host "Please install Python 3.11+ from https://www.python.org/downloads/"
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Prepare Python environment
Write-Host "Checking Python environment setup..." -ForegroundColor Yellow

# Check for existing virtual environment in root directory
$venvExists = Test-Path ".venv"
$venvActivateScript = ".\.venv\Scripts\Activate.ps1"

if ($venvExists) {
    Write-Host "Found existing virtual environment in root directory" -ForegroundColor Green
    
    # Check if activation script exists
    if (Test-Path $venvActivateScript) {
        Write-Host "Using existing virtual environment" -ForegroundColor Green
    } else {
        $venvActivateScript = ".\.venv\bin\Activate.ps1"  # Try Unix-style path
        if (-not (Test-Path $venvActivateScript)) {
            Write-Host "WARNING: Virtual environment exists but activation script not found" -ForegroundColor Yellow
            $venvExists = $false  # Mark as not usable
        }
    }
} else {
    # Create a root virtual environment if none exists
    Write-Host "No virtual environment found. Creating one in the root directory..." -ForegroundColor Yellow
    try {
        python -m venv .venv
        Write-Host "Virtual environment created successfully!" -ForegroundColor Green
        $venvExists = $true
    } catch {
        Write-Host "WARNING: Failed to create virtual environment. Will use global Python installation." -ForegroundColor Yellow
        $venvExists = $false
    }
}

# Install dependencies in root venv if it exists
if ($venvExists -and (Test-Path $venvActivateScript)) {
    Write-Host "Installing dependencies in the virtual environment..." -ForegroundColor Yellow
    try {
        & $venvActivateScript
        pip install -r requirements.txt
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Dependencies installed successfully." -ForegroundColor Green
        } else {
            Write-Host "WARNING: Error installing dependencies." -ForegroundColor Yellow
        }
        deactivate
    } catch {
        Write-Host "WARNING: Error activating virtual environment. Will use global Python." -ForegroundColor Yellow
        $venvExists = $false
    }
}

# Start backend in new window
Write-Host "Starting backend server..." -ForegroundColor Yellow
if ($venvExists) {
    # Use the virtual environment
    Start-Process -FilePath "powershell.exe" -ArgumentList "-Command cd $PWD; & '$venvActivateScript'; cd backend; pip install -r requirements.txt; python -m uvicorn app.main:app --reload --port 8000" -WindowStyle Normal
} else {
    # Use global Python
    Start-Process -FilePath "powershell.exe" -ArgumentList "-Command cd backend; pip install -r requirements.txt; python -m uvicorn app.main:app --reload --port 8000" -WindowStyle Normal
}

# Start frontend in new window
Write-Host "Starting frontend web interface..." -ForegroundColor Yellow
if ($venvExists) {
    # Use the virtual environment
    Start-Process -FilePath "powershell.exe" -ArgumentList "-Command cd $PWD; & '$venvActivateScript'; cd frontend; pip install -r requirements.txt; python app.py" -WindowStyle Normal
} else {
    # Use global Python
    Start-Process -FilePath "powershell.exe" -ArgumentList "-Command cd frontend; pip install -r requirements.txt; python app.py" -WindowStyle Normal
}

Write-Host ""
Write-Host "Application starting!" -ForegroundColor Green
Write-Host ""
Write-Host "The web interface will open automatically in your browser." -ForegroundColor Cyan
Write-Host "If it doesn't open automatically, access it at: http://localhost:5173" -ForegroundColor Cyan
Write-Host ""
Write-Host "Container logs can be viewed with: docker logs qwen-payslip-processor" -ForegroundColor Cyan
Write-Host ""
Write-Host "To stop the application:" -ForegroundColor Yellow
Write-Host " 1. Close both PowerShell windows" -ForegroundColor Yellow
Write-Host " 2. (Optional) Stop the container with: docker stop qwen-payslip-processor" -ForegroundColor Yellow

# Wait a moment for services to start
Start-Sleep -Seconds 5

# Open the application in the browser
Start-Process "http://localhost:5173" 