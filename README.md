# Payslip Processor Setup Guide
DISCLAIMER: the employee search function is not working right now, but the extraction is accurate. Also, make sure to adjust the docker commands based on your available memory, don't allocate more than what you have and always leave 8GB spared for your device to use. e.g if you have 50GB RAM, set the docker command and docker configs to use at most 42GB.

## Initial Setup
1. Clone the repository:
   ```
   git clone https://github.com/calvinsendawula/payslip_processor.git
   cd payslip_processor
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Linux/macOS
   source venv/bin/activate
   ```

3. Install requirements:
   ```
   pip install -r requirements.txt
   ```

## Docker Resource Configuration

### Windows WSL2 Configuration:
NOTE: Check how many processor cores your device has. Here I have 20 so I will set it to use 12 processors.

![image](https://github.com/user-attachments/assets/cee7933c-9eeb-46f9-855a-629c5d2cce81)

1. Create/edit file at `C:\Users\YourUsername\.wslconfig`:
   ```
   [wsl2]
   memory=42GB
   processors=12
   swap=42GB
   gpuSupport=true
   ```

2. Restart WSL:
   ```
   wsl --shutdown
   ```
   
   You need to restart docker as well after this.

### Linux Configuration:
Ensure your system has sufficient RAM allocated to Docker. You need to modify system settings to match the above but for linux.

## Docker Container Setup

### GPU Version (NVIDIA GPU)

**Windows PowerShell:**
```powershell
docker run -d -p 27842:27842 --gpus all `
  -e FORCE_CPU=false `
  -e PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb=64,garbage_collection_threshold=0.6,expandable_segments:True `
  -e PYTORCH_NO_CUDA_MEMORY_CACHING=1 `
  -e CUDA_CACHE_DISABLE=1 `
  -e NVIDIA_DRIVER_CAPABILITIES=compute,utility,video `
  -e NVIDIA_VISIBLE_DEVICES=0 `
  -e OMP_NUM_THREADS=1 `
  -e MKL_NUM_THREADS=1 `
  -e MEMORY_ISOLATION=none `
  --memory=12g `
  --memory-swap=24g `
  --shm-size=6g `
  --ipc=host `
  --ulimit memlock=-1 `
  --name qwen-processor `
  calvin189/qwen-payslip-processor:latest
```

**Linux/macOS/Bash:**
```bash
docker run -d -p 27842:27842 --gpus all \
  -e FORCE_CPU=false \
  -e PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb=64,garbage_collection_threshold=0.6,expandable_segments:True \
  -e PYTORCH_NO_CUDA_MEMORY_CACHING=1 \
  -e CUDA_CACHE_DISABLE=1 \
  -e NVIDIA_DRIVER_CAPABILITIES=compute,utility,video \
  -e NVIDIA_VISIBLE_DEVICES=0 \
  -e OMP_NUM_THREADS=1 \
  -e MKL_NUM_THREADS=1 \
  -e MEMORY_ISOLATION=none \
  --memory=12g \
  --memory-swap=24g \
  --shm-size=6g \
  --ipc=host \
  --ulimit memlock=-1 \
  --name qwen-processor \
  calvin189/qwen-payslip-processor:latest
```

### CPU Version (No GPU)

**Windows PowerShell:**
```powershell
docker run -d -p 27842:27842 `
  -e FORCE_CPU=true `
  -e PYTORCH_NO_CUDA_MEMORY_CACHING=1 `
  -e OMP_NUM_THREADS=8 `
  -e MKL_NUM_THREADS=8 `
  -e MEMORY_ISOLATION=none `
  --memory=42g `
  --memory-swap=42g `
  --shm-size=16g `
  --ipc=host `
  --ulimit memlock=-1 `
  --name qwen-processor `
  calvin189/qwen-payslip-processor:latest
```

**Linux/macOS/Bash:**
```bash
docker run -d -p 27842:27842 \
  -e FORCE_CPU=true \
  -e PYTORCH_NO_CUDA_MEMORY_CACHING=1 \
  -e OMP_NUM_THREADS=8 \
  -e MKL_NUM_THREADS=8 \
  -e MEMORY_ISOLATION=none \
  --memory=42g \
  --memory-swap=42g \
  --shm-size=16g \
  --ipc=host \
  --ulimit memlock=-1 \
  --name qwen-processor \
  calvin189/qwen-payslip-processor:latest
```

## Starting the Application

1. Start the backend:
   ```
   cd backend
   python -m app.seed_db
   uvicorn app.main:app --reload
   ```

2. In a new terminal, start the frontend:
   ```
   cd frontend
   python app.py
   ```

The Docker container will download model files on first run, which may take up to an hour depending on your internet speed. Wait for "application startup complete" in the Docker logs before proceeding.

Access the application at: http://localhost:5173
