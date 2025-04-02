from flask import Flask, render_template, request, jsonify
import requests
import os
import threading
import time
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size
app.config['BACKEND_URL'] = 'http://localhost:8000'

# Container status cache
container_status = {
    "status": "unknown",
    "last_checked": 0
}

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def check_container_status():
    """Background thread to periodically check container status"""
    while True:
        try:
            response = requests.get(f"{app.config['BACKEND_URL']}/container-status", timeout=5)
            if response.status_code == 200:
                # Update the container status cache with the response
                status_data = response.json()
                container_status.update(status_data)
                container_status["last_checked"] = time.time()
                # Add a custom field to indicate the status was successfully retrieved
                container_status["connection_ok"] = True
            else:
                # Backend responded but with an error
                container_status["status"] = "error"
                container_status["message"] = f"Backend returned status code {response.status_code}"
                container_status["last_checked"] = time.time()
                container_status["connection_ok"] = False
        except requests.exceptions.ConnectionError as e:
            # Connection error - backend is not running
            container_status["status"] = "error"
            container_status["message"] = "Cannot connect to backend server"
            container_status["last_checked"] = time.time()
            container_status["connection_ok"] = False
        except Exception as e:
            # Other error
            container_status["status"] = "error"
            container_status["message"] = str(e)
            container_status["last_checked"] = time.time()
            container_status["connection_ok"] = False
        
        # Sleep for 10 seconds before checking again
        time.sleep(10)

# Start background thread for container status checking
status_thread = threading.Thread(target=check_container_status, daemon=True)
status_thread.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/container-status')
def proxy_container_status():
    """Proxy the container status request to the backend"""
    try:
        # First check if the backend is reachable at all
        try:
            app.logger.info("Checking backend health at %s", app.config['BACKEND_URL'])
            health_response = requests.get(f"{app.config['BACKEND_URL']}/health", timeout=2)
            backend_available = health_response.status_code == 200
            app.logger.info("Backend health check result: %s (status %d)", 
                           "available" if backend_available else "unavailable", 
                           health_response.status_code)
        except Exception as e:
            app.logger.error(f"Backend health check failed: {str(e)}")
            backend_available = False
            
        # If backend is not available, return error
        if not backend_available:
            app.logger.warning("Backend is not available, returning 503")
            return jsonify({
                "status": "error", 
                "message": "Cannot connect to backend server", 
                "backend_available": False
            }), 503
            
        # Backend is available, now check container status
        app.logger.info("Checking container status")
        response = requests.get(f"{app.config['BACKEND_URL']}/container-status", timeout=5)
        if response.status_code == 200:
            status_data = response.json()
            # Add the backend availability flag
            status_data["backend_available"] = True
            app.logger.info(f"Container status: {status_data.get('status', 'unknown')}")
            return jsonify(status_data)
        else:
            # Return an error with the correct format for the frontend
            app.logger.error(f"Error response from backend container check: {response.status_code}")
            try:
                error_content = response.json()
                app.logger.error(f"Error content: {error_content}")
            except:
                app.logger.error(f"Could not parse error response as JSON: {response.text[:100]}")
                
            return jsonify({
                "status": "error", 
                "message": f"Backend returned status code {response.status_code}",
                "backend_available": True
            }), 500
    except Exception as e:
        app.logger.error(f"Unexpected error checking container status: {str(e)}")
        # Return a properly formatted error response
        return jsonify({
            "status": "error", 
            "message": str(e),
            "backend_available": False
        }), 500

@app.route('/api/restart-container-with-gpu', methods=['POST'])
def proxy_restart_container_with_gpu():
    """Proxy the restart container with GPU request to the backend"""
    try:
        response = requests.post(f"{app.config['BACKEND_URL']}/restart-container-with-gpu", timeout=60)
        return jsonify(response.json())
    except Exception as e:
        app.logger.error(f"Error restarting container with GPU: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500

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
        
        # Send to backend
        try:
            with open(filepath, 'rb') as f:
                files = {'file': (filename, f, 'application/pdf')}
                response = requests.post(
                    f"{app.config['BACKEND_URL']}/api/process-payslip", 
                    files=files
                )
            
            # Clean up the temporary file
            os.remove(filepath)
            
            if response.status_code == 200:
                result = response.json()
                # Format the response to match the expected structure
                return jsonify({
                    'employee': {
                        'name': result.get('employee_name', 'Unknown')
                    },
                    'payment': {
                        'gross': result.get('gross_amount', '0'),
                        'net': result.get('net_amount', '0')
                    },
                    'processing_time': result.get('processing_time', None)
                })
            else:
                error_message = 'Backend processing failed'
                try:
                    error_data = response.json()
                    if 'detail' in error_data:
                        error_message = error_data['detail']
                except:
                    pass
                return jsonify({'error': error_message}), response.status_code
                
        except Exception as e:
            app.logger.error(f"Error in file processing: {str(e)}")
            return jsonify({'error': str(e)}), 500
        finally:
            # Make sure file is removed even if there's an error
            if os.path.exists(filepath):
                os.remove(filepath)

@app.route('/upload-payslip-single', methods=['POST'])
def upload_payslip_single():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    # Get page and quadrant specifications
    employee_name_page = request.form.get('employee_name_page', None)
    employee_name_quadrant = request.form.get('employee_name_quadrant', None)
    gross_page = request.form.get('gross_page', None)
    gross_quadrant = request.form.get('gross_quadrant', None)
    net_page = request.form.get('net_page', None)
    net_quadrant = request.form.get('net_quadrant', None)
    
    # Convert page numbers to integers if provided
    if employee_name_page and employee_name_page.isdigit():
        employee_name_page = int(employee_name_page)
    else:
        employee_name_page = None
        
    if gross_page and gross_page.isdigit():
        gross_page = int(gross_page)
    else:
        gross_page = None
        
    if net_page and net_page.isdigit():
        net_page = int(net_page)
    else:
        net_page = None
    
    if file:
        # Save file temporarily
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Send to backend for guided extraction
        try:
            with open(filepath, 'rb') as f:
                files = {'file': (filename, f, 'application/pdf')}
                
                # Prepare form data with page/quadrant specifications
                form_data = {}
                
                # Create page configs object
                page_configs = {}
                
                if employee_name_page is not None:
                    if employee_name_page not in page_configs:
                        page_configs[employee_name_page] = {}
                    page_configs[employee_name_page]['employee_name'] = {
                        'quadrant': employee_name_quadrant or 'full'
                    }
                
                if gross_page is not None:
                    if gross_page not in page_configs:
                        page_configs[gross_page] = {}
                    page_configs[gross_page]['gross_amount'] = {
                        'quadrant': gross_quadrant or 'full'
                    }
                
                if net_page is not None:
                    if net_page not in page_configs:
                        page_configs[net_page] = {}
                    page_configs[net_page]['net_amount'] = {
                        'quadrant': net_quadrant or 'full'
                    }
                
                # Add the page configs as JSON
                if page_configs:
                    import json
                    form_data['page_configs'] = json.dumps(page_configs)
                
                app.logger.info(f"Sending file for processing with page configs: {form_data}")
                
                response = requests.post(
                    f"{app.config['BACKEND_URL']}/api/extract-payslip-single", 
                    files=files,
                    data=form_data
                )
            
            # Clean up the temporary file
            os.remove(filepath)
            
            if response.status_code == 200:
                result = response.json()
                # Format the response to match the expected structure
                return jsonify({
                    'employee': {
                        'name': result.get('employee_name', 'Unknown')
                    },
                    'payment': {
                        'gross': result.get('gross_amount', '0'),
                        'net': result.get('net_amount', '0')
                    },
                    'processing_time': result.get('processing_time', None)
                })
            else:
                error_message = 'Backend processing failed'
                try:
                    error_data = response.json()
                    if 'detail' in error_data:
                        error_message = error_data['detail']
                except:
                    pass
                return jsonify({'error': error_message}), response.status_code
                
        except Exception as e:
            app.logger.error(f"Error in single file processing: {str(e)}")
            return jsonify({'error': str(e)}), 500
        finally:
            # Make sure file is removed even if there's an error
            if os.path.exists(filepath):
                os.remove(filepath)

@app.route('/upload-payslip-batch', methods=['POST'])
def upload_payslip_batch():
    # Check if there are files in the request
    has_files = False
    for key in request.files:
        if request.files[key].filename:
            has_files = True
            break
    
    if not has_files:
        return jsonify({'error': 'No files uploaded'}), 400
    
    # Create a temporary directory for the batch
    import uuid
    batch_dir = os.path.join(app.config['UPLOAD_FOLDER'], f"batch_{uuid.uuid4().hex}")
    os.makedirs(batch_dir, exist_ok=True)
    
    try:
        # Save all files temporarily
        file_paths = []
        file_count = 0
        
        # Get all files from the request
        for key in request.files:
            file = request.files[key]
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                filepath = os.path.join(batch_dir, filename)
                file.save(filepath)
                file_paths.append((filename, filepath))
                file_count += 1
        
        if file_count == 0:
            return jsonify({'error': 'No valid files uploaded'}), 400
        
        # Send to backend for batch processing
        files_to_send = []
        for filename, filepath in file_paths:
            with open(filepath, 'rb') as f:
                files_to_send.append(('files', (filename, f, 'application/pdf')))
        
        app.logger.info(f"Sending {len(files_to_send)} files to backend for batch processing")
        
        response = requests.post(
            f"{app.config['BACKEND_URL']}/api/extract-payslip-batch", 
            files=files_to_send
        )
        
        # Clean up
        import shutil
        shutil.rmtree(batch_dir)
        
        if response.status_code == 200:
            result = response.json()
            # Format the results for the frontend
            return jsonify({
                'total_files': file_count,
                'successful': result.get('successful', 0),
                'failed': result.get('failed', 0),
                'results': result.get('results', [])
            })
        else:
            error_message = 'Backend batch processing failed'
            try:
                error_data = response.json()
                if 'detail' in error_data:
                    error_message = error_data['detail']
            except:
                pass
            return jsonify({'error': error_message}), response.status_code
            
    except Exception as e:
        app.logger.error(f"Error in batch processing: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        # Make sure directory is removed even if there's an error
        if os.path.exists(batch_dir):
            import shutil
            shutil.rmtree(batch_dir)

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

@app.route('/container-status')
def direct_container_status():
    """Catch direct requests to /container-status and redirect to the API endpoint"""
    return proxy_container_status()

@app.route('/restart-container-with-gpu', methods=['POST'])
def direct_restart_container_with_gpu():
    """Catch direct requests to /restart-container-with-gpu and redirect to the API endpoint"""
    return proxy_restart_container_with_gpu()

if __name__ == '__main__':
    app.run(debug=True, port=5173) 