from flask import Flask, render_template, request, jsonify
import requests
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size
app.config['BACKEND_URL'] = 'http://localhost:8000'

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload-payslip', methods=['POST'])
def upload_payslip():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file:
        # Save file temporarily
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Send to backend for extraction only
        try:
            with open(filepath, 'rb') as f:
                files = {'file': (filename, f)}
                response = requests.post(
                    f"{app.config['BACKEND_URL']}/api/extract-payslip", 
                    files=files
                )
            
            # Clean up the temporary file
            os.remove(filepath)
            
            if response.status_code == 200:
                return jsonify(response.json())
            else:
                return jsonify({'error': response.json().get('detail', 'Backend processing failed')}), response.status_code
                
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            # Make sure file is removed even if there's an error
            if os.path.exists(filepath):
                os.remove(filepath)

@app.route('/validate-payslip', methods=['POST'])
def validate_payslip():
    # Get validation data from request
    try:
        data = request.json
        if not data or 'employeeId' not in data or 'extractedData' not in data:
            return jsonify({'error': 'Invalid request data'}), 400
        
        # Send validation request to backend
        response = requests.post(
            f"{app.config['BACKEND_URL']}/api/validate-payslip-by-id",
            json=data
        )
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'error': response.json().get('detail', 'Validation failed')}), response.status_code
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/upload-property', methods=['POST'])
def upload_property():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file:
        # Save file temporarily
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Send to backend
        try:
            with open(filepath, 'rb') as f:
                files = {'file': (filename, f)}
                response = requests.post(
                    f"{app.config['BACKEND_URL']}/api/process-property", 
                    files=files
                )
            
            # Clean up the temporary file
            os.remove(filepath)
            
            if response.status_code == 200:
                return jsonify(response.json())
            else:
                return jsonify({'error': response.json().get('detail', 'Backend processing failed')}), response.status_code
                
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            # Make sure file is removed even if there's an error
            if os.path.exists(filepath):
                os.remove(filepath)

if __name__ == '__main__':
    app.run(debug=True, port=5173) 