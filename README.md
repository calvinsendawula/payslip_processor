# Updated README for Payslip Processor
# Gehaltsabrechnungs-Verarbeitung

A full-stack application that processes payslips using AI vision to extract and validate payment information against stored records.

## Overview

This application demonstrates how AI vision models can be used to extract structured information from documents. It uses Qwen2.5-VL-7B to analyze German payslips and property listings, extracting key information and validating it against expected values.

## Features

- **Payslip Processing**: Extract employee information and payment details from German payslips
- **Property Listing Analysis**: Extract living space and purchase price from German property listings
- **Validation System**: Compare extracted values with expected values in the database
- **Error Detection**: Highlight discrepancies between extracted and expected values
- **Demonstration Mode**: Includes intentional discrepancies to showcase error detection capabilities

## Requirements

- Python 3.11.5
- poppler-utils (for PDF processing)
- GPU with 8GB+ VRAM recommended (can work with less but will be slower)
  - Windows: 
    1. Press Windows + R, type "dxdiag" and press Enter
    2. Go to the "Display" tab(s)
    3. If you have multiple displays, check all "Display" tabs - the GPU with the highest VRAM will be used
    4. Look for "Dedicated Memory" or "Display Memory" - this is your VRAM in MB/GB
  - Linux: Run `nvidia-smi` in terminal
  - macOS: Apple > About This Mac > System Report > Graphics/Displays

## Setup Instructions

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. **ONE-TIME MODEL SETUP** - Download and cache the model (about 7GB):
   ```
   cd backend
   python setup_model.py
   ```
   
   > **IMPORTANT**: This step downloads the Qwen2.5-VL-7B model files (approximately 7GB) to a local `model_cache` folder in your project. You only need to run this **ONCE**, and the model will be saved permanently for future use.
   >
   > The download process may take 15-30 minutes depending on your internet connection. After completion, the application will use these cached files without redownloading.

3. Install PDF processing tools:

   **For Windows**:
   - Download and install Poppler from https://github.com/oschwartz10612/poppler-windows/releases/
   - Add the `bin` directory to your PATH
   
   **For Linux**:
   ```
   apt-get install -y poppler-utils
   ```
  
## Running the Application

1. Seed the database first:
   ```
   cd backend
   python -m app.seed_db
   ```

2. Start the backend:
   ```
   cd backend
   uvicorn app.main:app --reload
   ```

3. In a separate terminal, start the frontend:
   ```
   cd frontend
   python app.py
   ```

4. Open the application in your browser:
   http://localhost:5173

## Using GPU Acceleration

This application supports GPU acceleration if you have an NVIDIA GPU. To enable it:

1. Install the CUDA-enabled version of PyTorch:
   ```
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
   ```

2. Run the model setup script as described above.

3. Start the application normally - it will automatically detect and use your GPU.

## Using the Application

1. Select the "Gehaltsabrechnung" tab for payslip processing or "Immobilienangebot" tab for property listings
2. Drag and drop a PDF or image file, or click to select a file
3. Click "Hochladen und Analysieren" to process the file
4. For payslips, enter an employee ID to validate the extracted information
5. View the extracted information and validation results

### Sample Files

The repository includes sample files in the `samples` directory:
- `german_payslip.pdf`: A sample German payslip
- `german_house_listing.pdf`: A sample German property listing

## Demonstration Features

### Intentional Discrepancy

The system includes an intentional discrepancy in the database to showcase the error detection capabilities:

- The sample payslip shows a net amount of 2,729.38 €
- The database has an expected net amount of 3,214.00 € (which is actually the base salary amount)
- When processing the payslip, the system will correctly extract 2,729.38 € but flag it as an error since it doesn't match the expected value

This demonstrates how the system can detect potential issues in payroll processing, useful for identifying mistakes or fraud.

## Customization

**Important**: The system is configured specifically for these sample payslips. To use it with different payslips, you'll need to:
1. Modify the seed data in `backend/app/seed_db.py` to match your expected values
2. Adjust the extraction logic in `backend/app/main.py` to match your payslip format
3. Update the prompt templates in `backend/app/qwen_processor.py` to extract the relevant information from your payslip format

## System Architecture

The system uses the Qwen2.5-VL-7B vision-language model for processing payslip and property listing images. The model runs locally and uses a sliding window approach to handle large documents efficiently.

- **Frontend**: Flask web application that handles file uploads and displays results
- **Backend**: FastAPI application that processes files and communicates with the vision model
- **Database**: SQLite database that stores expected values for validation
- **AI Model**: Qwen2.5-VL-7B vision-language model running locally 

## API Documentation

The backend provides the following endpoints:

- `POST /api/extract-payslip`: Process a payslip file and return extracted information
  - Accepts: PDF or image files (multipart/form-data)
  - Returns: JSON with extracted information

- `POST /api/validate-payslip-by-id`: Validate extracted information against a specific employee ID
  - Accepts: JSON with employee ID and extracted data
  - Returns: JSON with validation results

- `POST /api/process-property`: Process a property listing and return extracted information
  - Accepts: PDF or image files (multipart/form-data)
  - Returns: JSON with extracted property details

## Troubleshooting

- **Model Loading Issues**: If the model fails to load, ensure you have sufficient RAM and VRAM
- **PDF Processing Errors**: Make sure poppler-utils is correctly installed and accessible in your PATH
- **Extraction Accuracy**: The system is optimized for the provided sample files; other formats may require prompt adjustments
