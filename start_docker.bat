@echo off
echo ==========================================================
echo      Qwen Payslip Processor - Docker Container Starter
echo ==========================================================
echo.
echo This script will help you start the Qwen Payslip Processor Docker container.
echo.
echo Prerequisites:
echo  - Docker Desktop installed and running
echo  - Internet connection for initial container download
echo.
echo IMPORTANT NOTES:
echo  - First download is ~14GB and may take 15-60 minutes depending on your connection
echo  - Initial container startup takes 5-10 minutes while the model loads
echo  - Container is ready when the backend detects it or when logs show:
echo    "Model loaded successfully" and "Uvicorn running on http://0.0.0.0:27842"
echo  - Check progress with: docker logs qwen-payslip-processor
echo.

REM Check if Docker is installed
where docker >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Docker is not installed or not in your PATH.
    echo Please install Docker Desktop from https://www.docker.com/products/docker-desktop
    echo.
    pause
    exit /b 1
)

REM Check Docker status
echo Checking Docker status...
docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Docker Desktop is not running or not accessible.
    echo Please start Docker Desktop and try again.
    echo.
    pause
    exit /b 1
)

REM Perform additional system checks and diagnostics 
echo Running system diagnostics for optimal performance...
echo.

REM Check for WSL configuration file
echo Checking WSL2 memory configuration...
if exist "%USERPROFILE%\.wslconfig" (
    echo Found .wslconfig file. Current WSL configuration:
    type "%USERPROFILE%\.wslconfig"
    
    REM Check if the memory configuration is adequate
    findstr /C:"memory=" "%USERPROFILE%\.wslconfig" >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo WARNING: Existing .wslconfig does not specify memory limits.
        echo For optimal performance with large models, consider adding these settings:
        echo.
        echo memory=16GB
        echo processors=8
        echo swap=32GB
        echo gpuSupport=true
        echo.
        
        set /p modify_config="Would you like to modify your existing .wslconfig file? (Y/N): "
        if /i "%modify_config%"=="Y" (
            echo You chose to modify your existing .wslconfig file.
            echo.
            echo !!! WARNING: This will backup your current config to .wslconfig.bak !!!
            echo.
            set /p confirm_modify="Are you sure you want to continue? (Y/N): "
            if /i "%confirm_modify%"=="Y" (
                echo Backing up current config...
                copy "%USERPROFILE%\.wslconfig" "%USERPROFILE%\.wslconfig.bak"
                
                echo Creating new WSL config file...
                echo [wsl2] > "%USERPROFILE%\.wslconfig"
                echo memory=16GB >> "%USERPROFILE%\.wslconfig"
                echo processors=8 >> "%USERPROFILE%\.wslconfig"
                echo swap=32GB >> "%USERPROFILE%\.wslconfig"
                echo gpuSupport=true >> "%USERPROFILE%\.wslconfig"
                echo Updated "%USERPROFILE%\.wslconfig" successfully.
                echo Your previous config was backed up to "%USERPROFILE%\.wslconfig.bak"
                echo You may need to restart Docker/WSL for these settings to take effect.
                echo To restart WSL, run: wsl --shutdown
            )
        )
    ) else (
        echo Your .wslconfig appears to have memory settings configured.
    )
) else (
    echo.
    echo WARNING: No .wslconfig found. For optimal performance with large models, you should create:
    echo %USERPROFILE%\.wslconfig with the following content:
    echo.
    echo [wsl2]
    echo memory=16GB
    echo processors=8
    echo swap=32GB
    echo gpuSupport=true
    echo.
    echo WARNING: Without these settings, Docker might run out of memory when pulling or running the container.
    
    REM Offer to create the config file
    set /p create_config="Would you like to create this file now? (Y/N): "
    if /i "%create_config%"=="Y" (
        echo Creating WSL config file...
        echo [wsl2] > "%USERPROFILE%\.wslconfig"
        echo memory=16GB >> "%USERPROFILE%\.wslconfig"
        echo processors=8 >> "%USERPROFILE%\.wslconfig"
        echo swap=32GB >> "%USERPROFILE%\.wslconfig"
        echo gpuSupport=true >> "%USERPROFILE%\.wslconfig"
        echo Created "%USERPROFILE%\.wslconfig" successfully.
        echo You may need to restart Docker/WSL for these settings to take effect.
        echo To restart WSL, run: wsl --shutdown
    )
)

REM Check disk space
echo.
echo Checking available disk space...
for /f "tokens=3" %%a in ('dir /-c 2^>nul ^| findstr /c:"bytes free"') do set FREE_SPACE=%%a
echo Available disk space: %FREE_SPACE% bytes
REM Convert to GB (rough calculation)
set /a FREE_SPACE_GB=%FREE_SPACE:~0,-9%
echo Available disk space: ~%FREE_SPACE_GB% GB

if %FREE_SPACE_GB% LSS 20 (
    echo.
    echo WARNING: Less than 20GB of free disk space available!
    echo The Docker image requires at least 14GB for download plus additional space.
    echo Insufficient disk space may cause download failures.
    echo.
    set /p continue_anyway="Do you want to continue anyway? (Y/N): "
    if /i NOT "%continue_anyway%"=="Y" (
        echo Operation cancelled due to low disk space.
        pause
        exit /b 1
    )
)

REM Check for port availability
echo.
echo Checking if port 27842 is available...
netstat -ano | findstr ":27842" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo.
    echo WARNING: Port 27842 appears to be in use by another application!
    echo This will cause conflicts when starting the Docker container.
    echo.
    echo Please close the application using this port before continuing.
    set /p continue_anyway="Do you want to continue anyway? (Y/N): "
    if /i NOT "%continue_anyway%"=="Y" (
        echo Operation cancelled due to port conflict.
        pause
        exit /b 1
    )
) else (
    echo Port 27842 is available.
)

echo.
echo Checking if the container is already running...
REM Check by port first, then by name
docker ps | findstr "27842/tcp" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo.
    echo A Docker container using port 27842 is already running.
    echo.
    docker ps | findstr "27842/tcp"
    echo.
    echo Container is already running! You can start using the application.
    echo.
    pause
    exit /b 0
) else (
    REM Check specifically for our named container
    docker ps | findstr "qwen-payslip-processor" >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo.
        echo The qwen-payslip-processor container is running (on a custom port).
        echo.
        docker ps | findstr "qwen-payslip-processor"
        echo.
        echo Container is already running! You can start using the application.
        echo Note: The container is using a non-standard port. Make sure your backend is configured correctly.
        echo.
        pause
        exit /b 0
    )
)

REM Check if container exists but is stopped (check both by name and by port configuration)
echo Checking if a suitable container exists but is stopped...

REM First check for our named container
set CONTAINER_FOUND=0
for /f "tokens=1" %%i in ('docker ps -a --filter "name=qwen-payslip-processor" --format "{{.ID}}"') do (
    set CONTAINER_ID=%%i
    set CONTAINER_FOUND=1
)

REM Then check for any container configured for our port if we didn't find by name
if %CONTAINER_FOUND% EQU 0 (
    for /f "tokens=1" %%i in ('docker ps -a --filter "publish=27842" --format "{{.ID}}"') do (
        set CONTAINER_ID=%%i
        set CONTAINER_FOUND=1
    )
)

if %CONTAINER_FOUND% EQU 1 (
    echo.
    echo Found existing suitable container. Starting container...
    docker start %CONTAINER_ID%
    if %ERRORLEVEL% EQU 0 (
        echo.
        echo Container started successfully! The backend will now be able to communicate with it.
        echo.
        echo You can now start the backend and frontend applications.
        echo The container status will be displayed in the UI.
        pause
        exit /b 0
    ) else (
        echo.
        echo Failed to start existing container. It may be corrupted.
        echo.
        set /p remove_container="Do you want to remove the container and create a new one? (Y/N): "
        if /i "%remove_container%"=="Y" (
            docker rm %CONTAINER_ID%
            echo Removed existing container. Will create a new one.
        ) else (
            echo Container startup cancelled.
            pause
            exit /b 1
        )
    )
) else (
    echo No existing containers found that match our requirements.
)

REM Check for NVIDIA GPU support
echo Checking for GPU support...
set GPU_AVAILABLE=0
set DOCKER_GPU_PARAM=

REM Check for NVIDIA GPU
where nvidia-smi >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    nvidia-smi >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo Testing NVIDIA Docker support...
        docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi >nul 2>&1
        if %ERRORLEVEL% EQU 0 (
            echo NVIDIA GPU detected and NVIDIA Docker support working!
            set GPU_AVAILABLE=1
            set DOCKER_GPU_PARAM=--gpus all
        ) else (
            echo NVIDIA GPU detected but Docker GPU support not configured correctly.
            echo See https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html
        )
    ) else (
        echo NVIDIA GPU driver issues detected. Please update your GPU drivers.
    )
) else (
    echo No NVIDIA GPU detected or drivers not installed. Container will run on CPU.
)

REM Check if the image exists locally
echo.
echo Checking if Docker image exists locally...
docker images | findstr "calvin189/qwen-payslip-processor" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Found local image. No need to download.
    set NEED_PULL=0
) else (
    echo Image not found locally. Will need to download (~14GB).
    set NEED_PULL=1
)

echo.
echo Starting Qwen Payslip Processor container...
echo.

if %GPU_AVAILABLE% EQU 1 (
    echo Using GPU acceleration with the following command:
    echo docker run -d -p 27842:27842 %DOCKER_GPU_PARAM% --name qwen-payslip-processor --memory=12g --memory-swap=24g --shm-size=1g calvin189/qwen-payslip-processor:latest
) else (
    echo Using CPU with the following command:
    echo docker run -d -p 27842:27842 --name qwen-payslip-processor --memory=12g --memory-swap=24g --shm-size=1g calvin189/qwen-payslip-processor:latest
)
echo.

if %NEED_PULL% EQU 1 (
    echo This will download a large (~14GB) Docker image and may take 15-60+ minutes depending on your connection.
) else (
    echo No download needed. Container will start using local image.
)

set /p confirm="Do you want to start the container now? (Y/N): "
if /i "%confirm%"=="Y" (
    echo.
    
    if %NEED_PULL% EQU 1 (
        echo Downloading the Docker image first (~14GB)...
        echo This will take significant time. Please be patient.
        
        docker pull calvin189/qwen-payslip-processor:latest
        
        if %ERRORLEVEL% NEQ 0 (
            echo.
            echo ERROR: Failed to download the Docker image.
            echo This could be due to network issues or insufficient disk space.
            echo.
            pause
            exit /b 1
        )
    )
    
    echo.
    echo Starting the Docker container...
    echo.
    echo IMPORTANT: Initial startup takes 5-10 minutes while the model loads.
    echo Do not interrupt the process. Check progress with: docker logs qwen-payslip-processor
    echo The container is ready when you see: "Model loaded successfully"
    echo.
    
    if %GPU_AVAILABLE% EQU 1 (
        docker run -d -p 27842:27842 %DOCKER_GPU_PARAM% --name qwen-payslip-processor --memory=12g --memory-swap=24g --shm-size=1g calvin189/qwen-payslip-processor:latest
    ) else (
        docker run -d -p 27842:27842 --name qwen-payslip-processor --memory=12g --memory-swap=24g --shm-size=1g calvin189/qwen-payslip-processor:latest
    )
    
    if %ERRORLEVEL% EQU 0 (
        echo.
        echo Container starting! The backend will automatically detect when it's ready.
        echo Check progress with: docker logs qwen-payslip-processor
        echo.
        echo Expected logs when ready:
        echo "Loading checkpoint shards: 100%%|██████████| 4/4 [00:07^<00:00,  1.93s/it]"
        echo "Model loaded successfully!"
        echo "Uvicorn running on http://0.0.0.0:27842"
        
        REM Check container status after a few seconds
        echo.
        echo Waiting 10 seconds to verify container is running properly...
        timeout /t 10 >nul
        docker ps | findstr "qwen-payslip-processor" >nul 2>&1
        if %ERRORLEVEL% NEQ 0 (
            echo.
            echo WARNING: Container started but stopped immediately. Checking logs...
            echo.
            docker logs qwen-payslip-processor
            echo.
            echo Container failed to stay running. This is usually due to memory issues.
            echo Please check the logs above for specific errors.
        ) else (
            echo Container verified and running!
        )
    ) else (
        echo.
        echo ERROR: Failed to start the container. This could be due to:
        echo  - Not enough memory allocated to Docker
        echo  - The container name is already in use (try: docker rm qwen-payslip-processor)
        echo  - Permission issues or other Docker configuration problems
        echo.
        echo Try the following steps if you encounter memory-related errors:
        echo 1. Stop all running Docker containers (docker stop $(docker ps -q))
        echo 2. Increase Docker memory limits in Docker Desktop settings
        echo 3. Restart Docker Desktop completely
        echo 4. Create or modify .wslconfig with memory settings
        echo 5. Restart WSL with: wsl --shutdown
        
        REM Offer recovery options
        echo.
        echo Would you like to:
        echo 1. Try to remove the existing container (if name conflict)
        echo 2. Show Docker system information (useful for diagnostics)
        echo 3. Exit
        set /p recovery_option="Enter option (1-3): "
        
        if "%recovery_option%"=="1" (
            echo Attempting to remove existing container...
            docker rm qwen-payslip-processor
            
            echo Retrying container startup...
            if %GPU_AVAILABLE% EQU 1 (
                docker run -d -p 27842:27842 %DOCKER_GPU_PARAM% --name qwen-payslip-processor --memory=12g --memory-swap=24g --shm-size=1g calvin189/qwen-payslip-processor:latest
            ) else (
                docker run -d -p 27842:27842 --name qwen-payslip-processor --memory=12g --memory-swap=24g --shm-size=1g calvin189/qwen-payslip-processor:latest
            )
            
            if %ERRORLEVEL% EQU 0 (
                echo Container started successfully on second attempt!
            ) else (
                echo Failed to start container even after removing existing one.
                echo See error details above.
            )
        ) else if "%recovery_option%"=="2" (
            echo.
            echo Docker system information:
            echo.
            docker system info
            echo.
            docker system df
        )
    )
) else (
    echo.
    echo Container startup cancelled.
)

echo.
echo You can now start the backend and frontend applications.
echo The container status will be displayed in the UI.

REM Add section at the end for manual Docker image management
echo.
echo ==========================================================
echo REFERENCE: Manual Docker Container Management
echo ==========================================================
echo.
echo If you prefer to manage the Docker container separately or run it on another machine:
echo.
echo 1. Pull the image manually:
echo    docker pull calvin189/qwen-payslip-processor:latest
echo.
echo 2. Run with GPU support:
echo    docker run -d -p 27842:27842 --gpus all --name qwen-payslip-processor --memory=12g --memory-swap=24g --shm-size=1g calvin189/qwen-payslip-processor:latest
echo.
echo 3. Run without GPU (CPU only):
echo    docker run -d -p 27842:27842 --name qwen-payslip-processor --memory=12g --memory-swap=24g --shm-size=1g calvin189/qwen-payslip-processor:latest
echo.
echo 4. Using a custom port (replace PORT with your preferred port):
echo    docker run -d -p PORT:27842 --name qwen-payslip-processor --memory=12g --memory-swap=24g --shm-size=1g calvin189/qwen-payslip-processor:latest
echo.
echo 5. When running on a separate machine, update the backend's config_payslip.yml and config_property.yml:
echo    host: "machine-ip-address"  (Replace with the IP of the Docker host)
echo    port: 27842  (Or your custom port if changed)
echo.
echo ==========================================================
echo.
pause 