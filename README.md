# Payslip Processor with Qwen2.5-VL-7B

A FastAPI application that processes German payslips using the Qwen2.5-VL-7B vision-language model.

![DokProz](https://github.com/user-attachments/assets/00d063af-e50a-431e-b468-04ffaa75f3a5)

## ⚠️ Important Notes - Please Read First

This application is currently optimized for processing a specific payslip format (sample_payslip_v2.pdf). The vision-language model has been specifically trained with prompts tailored to this document structure.

### Key Points to Understand
- The application is NOT a generic payslip processor
- Each different payslip format requires specific guidance
- Current implementation extracts:
  - Employee name (from top section after "Herrn/Frau")
  - Gross amount (Gesamt-Brutto from top-right corner)
  - Net amount (Auszahlungsbetrag from bottom-right corner)
- The model CAN process any document type but needs specific guidance for each new format

## Resolution Settings and Processing Time
The application uses a progressive resolution approach starting from a high resolution (default: 1500px) and gradually reducing it if needed depending on the capabliities of your GPU. This affects processing time significantly:

- Higher initial resolution = Better accuracy but slower processing
- Lower initial resolution = Faster processing but potentially reduced accuracy
- Processing time varies based on your GPU's VRAM:
  - Example: With 8GB VRAM (5GB used by model):
    - 1500px resolution: ~14 minutes per page (high accuracy)
    - Lower resolutions: Significantly faster but may reduce accuracy

You can adjust these settings in `backend/config.yml`:
```yaml
image:
  initial_resolution: 1500  # Starting resolution
  resolution_steps: [1500, 1200, 1000, 800, 600]  # Progressive reduction steps
```

> **Important Notes**: 
> - The `initial_resolution` must be less than or equal to the first value in the `resolution_steps` list
> - While you can reduce the resolution steps to speed up processing, always keep at least one value in the list
> - For optimal performance, experiment with different resolution values to find the right balance between speed and accuracy for your specific GPU

### Recommended Parameter Ranges
For the best balance between processing time and accuracy, consider these ranges:

| Parameter | Minimum | Recommended | Maximum | Notes |
|-----------|---------|-------------|---------|-------|
| `initial_resolution` | 600 | 1000-1200 | 1500 | Higher values significantly increase processing time |
| `resolution_steps` | Single value | 2-3 values | 5 values | More steps = more attempts but longer processing |
| `pdf.dpi` | 300 | 450 | 600 | Higher DPI values capture more detail but require more memory |

These ranges are based on how practical it would be to run the program. For most 8GB+ VRAM GPUs:
- Starting at 1000px resolution offers a good balance
- Starting at 1500px provides the highest accuracy
- Values below 600px may miss small text or details
- Values above 1500px rarely provide additional accuracy but greatly increase processing time

## System Requirements

### Hardware Requirements
- **GPU**: CUDA-capable NVIDIA GPU
- **VRAM (Video RAM) Requirements:**
  - Minimum: 8GB VRAM (non-negotiable)
  - Recommended: 12GB VRAM or more
  - Example compatible GPUs:
    - NVIDIA RTX 3060 (12GB VRAM)
    - NVIDIA RTX 3080 (10GB VRAM)
    - NVIDIA RTX 4070 (12GB VRAM)
    - Or any GPU with 8GB+ VRAM
  - Note: VRAM capacity is more important than GPU processing power

### Software Requirements
- **Python Version:**
  - Required: Python 3.10 or higher
  - Recommended: Python 3.11.5
- **Disk Space:** ~7GB for model files
- **Operating System:** Windows, Linux, or macOS
- **PDF Processing Tools:**
  - Windows: Poppler (added to PATH)
  - Linux: poppler-utils
  - macOS: poppler via homebrew

## Setup Instructions

### 1. Environment Setup
```bash
# Create virtual environment
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install PyTorch with CUDA support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### 2. Install PDF Processing Tools

**For Windows:**
1. Download Poppler from https://github.com/oschwartz10612/poppler-windows/releases/
2. Install and add the `bin` directory to your system's PATH
3. Verify installation by running `pdfinfo -v` in a new terminal

**For Linux:**
```bash
sudo apt-get install -y poppler-utils
```

**For macOS:**
```bash
brew install poppler
```

### 3. Model Setup and Configuration

```bash
# Download and cache model files (one-time setup, ~7GB)
cd backend
python setup_model.py
```

> **IMPORTANT**: This downloads the Qwen2.5-VL-7B model (approximately 7GB) to a local `model_cache` folder in your project. This step must be completed once before using the application.
>
> The download takes 15-30 minutes depending on your internet connection. After completion, the application will use these cached files without redownloading.

The application uses dynamic memory management:
- Default: No explicit memory limit (uses up to 90% of available VRAM)
- To restrict memory usage, modify `backend/config.yaml`:
  ```yaml
  model:
    memory_limit_gb: 0  # This is currently set to 0 so the model will use whatever VRAM is available to it
  ```

### 4. Database Setup
```bash
cd backend
python -m app.seed_db
```

### 5. Start the Application
```bash
# Terminal 1 - Start backend
cd backend
uvicorn app.main:app --reload

# Terminal 2 - Start frontend
cd frontend
python app.py
```

Access the application at http://localhost:5173

## Testing the Application

### Sample Payslip Processing
1. Use `sample_payslip_v2.pdf` for testing
2. Expected values:
   - Employee Name: "Erika Mustermann"
   - Gross Amount: 2124.00
   - Net Amount: 1374.78


## Logging

The application creates detailed logs of all processing operations in:
```
backend/logs/payslip_processor.log
```

Log entries include:
- Timestamps for all operations
- Processing times for document extraction and validation
- Clear session separation between application runs
- Warning and error messages with detailed information
- Validation results and success/failure indicators

Logs are appended to the same file across multiple runs for easy troubleshooting and performance monitoring.

## Processing Different Payslip Formats

To adapt the system for different payslip formats:
1. Modify prompts in `backend/app/qwen_processor.py`
2. Update:
   - Field location descriptions
   - Search patterns and labels
   - Validation rules if needed

## Technical Architecture

- **Backend:** FastAPI
- **Frontend:** HTML + CSS
- **Model:** Qwen2.5-VL-7B vision-language model
- **Processing:** Sliding window approach with progressive resolution
- **Database:** SQLite with SQLAlchemy ORM

## Performance Considerations

- First-time processing may be slower due to GPU memory allocation
- Subsequent processing is faster
- Performance factors:
  - Available VRAM (more = faster processing)
  - Memory allocation settings in config.yaml
  - GPU acceleration is crucial for reasonable performance
  - Image resolution settings significantly impact processing time

## Troubleshooting

### Model Loading Issues
1. Verify `setup_model.py` completed successfully
2. Check `model_cache` directory contains model files
3. Verify CUDA availability:
   ```python
   python -c "import torch; print(torch.cuda.is_available())"
   ```

### PDF Processing Errors
1. Verify Poppler installation and PATH
2. Test PDF conversion manually
3. Check PDF is not corrupted or password-protected

## Support

For processing new payslip formats, provide:
1. Sample payslip (sensitive data redacted)
2. List of fields to extract
3. Clear indication of field locations

## Limitations

- Optimized for specific payslip format only
- Requires significant VRAM (8GB minimum)
- Not suitable for batch processing of varied formats
- Requires prompt engineering for new formats
- GPU required for practical use

## Overview

This application provides a complete solution for:
- Extracting employee information and payment details from German payslips
- Processing property listing documents to extract property details
- Validating extracted information against database records
- User-friendly interface for document upload and result viewing

The system uses a sliding window approach with the powerful Qwen2.5-VL-7B model for accurate data extraction from images and PDFs.

## Project Structure

```
payslip_processor/
├── backend/                 # FastAPI backend
│   ├── app/                # Main application code
│   ├── config.yml          # Configuration settings
│   ├── setup_model.py      # Model setup script
│   └── payslips.db         # SQLite database
├── frontend/               # frontend
│   ├── app.py             # Main frontend application
│   ├── static/            # Static assets
│   ├── templates/         # HTML templates
│   └── uploads/           # Temporary upload directory
├── model_cache/           # Cached model files
├── sample/                # Sample documents
└── requirements.txt       # Python dependencies
```

## Database Schema

The SQLite database contains the following tables:
- `payslips`: Stores processed payslip information
  - `id`: Unique identifier
  - `employee_name`: Extracted employee name
  - `gross_amount`: Gross salary amount
  - `net_amount`: Net salary amount
  - `processed_date`: Timestamp of processing
  - `file_path`: Path to original document
