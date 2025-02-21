# Payslip Processor

A full-stack application that processes payslips using AI vision to extract and validate payment information against stored records.

## Requirements

- Python 3.11.5
- Node.js 18+ 
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

### 2. Backend Setup

1. Open a new terminal window and create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Install poppler-utils (required for PDF processing):
- On Ubuntu/Debian: 
  ```bash
  sudo apt-get install poppler-utils
  ```
- On macOS: 
  ```bash
  brew install poppler
  ```
- On Windows:
  1. Download the latest release (e.g., `Release-24.08.0-0.zip`) from [poppler-windows releases](https://github.com/oschwartz10612/poppler-windows/releases/)
  2. Extract the ZIP file to a permanent location (e.g., `C:\Program Files\poppler`)
  3. Add the bin directory to your system's PATH environment variable:
     - Open System Properties > Advanced > Environment Variables
     - Under System Variables, find and select "Path"
     - Click "Edit" and add the path to your poppler bin directory (e.g., `C:\Program Files\poppler\bin`)
     - Click "OK" to save

4. Initialize the database with mock data:
```bash
cd backend
python -m app.seed_db
```

5. Start the backend server:
```bash
uvicorn app.main:app --reload
```

The backend will be available at `http://localhost:8000`

### 3. Frontend Setup

1. Open a new terminal window and install Node.js dependencies:
```bash
cd frontend
npm install
```

2. Start the development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`

## Usage

1. Ensure Ollama is running with the Llama 3.2 Vision 11B model (`ollama run llama3.2-vision`)
2. Ensure the backend server is running
3. Open the frontend application in your browser
4. Upload a payslip (PDF or image format)
5. The system will process the payslip and compare the extracted information with stored records

## Sample Data

The repository includes two sample payslips in the `sample` folder:
- `payslip_true_positive.pdf`: A payslip that matches the expected values in the database
- `payslip_litmus.pdf`: A payslip with intentional inconsistencies to demonstrate the validation system

**Important**: The system is configured specifically for these sample payslips. To use it with different payslips, you'll need to:
1. Modify the seed data in `backend/app/seed_db.py` to match your expected values
2. Adjust the extraction logic in `backend/app/main.py` to match your payslip format
3. Update the prompt template to extract the relevant information from your payslip format

## Notes

- The system requires Ollama running with Llama 3.2 Vision 11B model
- Mock employee data is provided through the seed_db script and corresponds to the sample payslips
- Supported file formats: PDF, PNG, JPG, JPEG
- Make sure you have at least 16GB of RAM available for running the Llama model

## API Documentation

The backend provides the following endpoints:

- `POST /api/process-payslip`: Process a payslip file and return extracted information
  - Accepts: PDF or image files (multipart/form-data)
  - Returns: JSON with comparison results

## Development

- Backend: FastAPI + SQLAlchemy + Ollama
- Frontend: React + Material-UI
- Database: SQLite

## System Architecture

The system uses Ollama's Llama 3.2 Vision 11B parameters model for processing payslip images. The model runs locally through Ollama's API, which the backend communicates with to extract payment information from uploaded documents.
