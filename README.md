# Updated README for Payslip Processor
# Gehaltsabrechnungs-Verarbeitung

A full-stack application that processes payslips using AI vision to extract and validate payment information against stored records.

## Overview

This application demonstrates how AI vision models can be used to extract structured information from documents. It uses Llama 3.2 Vision to analyze German payslips and property listings, extracting key information and validating it against expected values.

## Features

- **Payslip Processing**: Extract employee information and payment details from German payslips
- **Property Listing Analysis**: Extract living space and purchase price from German property listings
- **Validation System**: Compare extracted values with expected values in the database
- **Error Detection**: Highlight discrepancies between extracted and expected values
- **Demonstration Mode**: Includes intentional discrepancies to showcase error detection capabilities

## Requirements

- Python 3.11.5
- Ollama (for AI vision processing)
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

### 1. Install Ollama

1. Visit [Ollama's website](https://ollama.ai/) and download the appropriate version for your OS
2. Install Ollama following their instructions
3. Start the Llama model:

```bash
ollama run llama3.2-vision
```

This will download and run the model if it's not already present (download size should be around 6GB for the 11B parameter model). Keep this terminal window open as it needs to stay running.

### 2. Install Dependencies

#### Backend (FastAPI)

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

#### Frontend (Flask)

```bash
cd frontend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Install PDF Processing Tools

#### Windows
Download and install poppler from: https://github.com/oschwartz10612/poppler-windows/releases/
Add the bin directory to your PATH.

#### macOS
```bash
brew install poppler
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt-get install -y poppler-utils
```

### 4. Seed the Database

```bash
cd backend
python -m app.seed_db
```

This will create a SQLite database with sample employee records that match the provided sample payslips.

### 5. Start the Backend

```bash
cd backend
uvicorn app.main:app --reload
```

### 6. Start the Frontend

In a new terminal:

```bash
cd frontend
python app.py
```

### 7. Access the Application

Open your browser and navigate to: http://localhost:5173

## Using the Application

1. Select the "Gehaltsabrechnung" tab for payslip processing or "Immobilienangebot" tab for property listings
2. Drag and drop a PDF or image file, or click to select a file
3. Click "Hochladen und Analysieren" to process the file
4. View the extracted information and validation results

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
3. Update the prompt template in `aisettings` to extract the relevant information from your payslip format

## System Architecture

The system uses Ollama's Llama 3.2 Vision 11B parameters model for processing payslip images. The model runs locally through Ollama's API, which the backend communicates with to extract payment information from uploaded documents.

- **Frontend**: Flask web application that handles file uploads and displays results
- **Backend**: FastAPI application that processes files and communicates with the AI model
- **Database**: SQLite database that stores expected values for validation
- **AI Model**: Llama 3.2 Vision running locally through Ollama

## API Documentation

The backend provides the following endpoints:

- `POST /api/process-payslip`: Process a payslip file and return extracted information
  - Accepts: PDF or image files (multipart/form-data)
  - Returns: JSON with comparison results

- `POST /api/process-property`: Process a property listing and return extracted information
  - Accepts: PDF or image files (multipart/form-data)
  - Returns: JSON with extracted property details

## Troubleshooting

- **Model Loading Issues**: If Ollama fails to load the model, ensure you have sufficient RAM and VRAM
- **PDF Processing Errors**: Make sure poppler-utils is correctly installed and accessible in your PATH
- **Extraction Accuracy**: The system is optimized for the provided sample files; other formats require prompt adjustments
