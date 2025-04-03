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
            health_response = requests.get(f"{app.config['BACKEND_URL']}/health", timeout=10)
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
        response = requests.get(f"{app.config['BACKEND_URL']}/container-status", timeout=15)
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

def cleanup_gpu_memory():
    """
    Call the backend endpoint to clean up GPU memory
    This helps prevent memory issues when processing multiple files
    without restarting the container
    """
    try:
        app.logger.info("Requesting GPU memory cleanup")
        response = requests.get(f"{app.config['BACKEND_URL']}/api/cleanup-memory", timeout=30)
        if response.status_code == 200:
            app.logger.info("GPU memory cleanup successful")
            return True
        else:
            app.logger.warning(f"GPU memory cleanup failed with status {response.status_code}")
            return False
    except Exception as e:
        app.logger.error(f"Error requesting GPU memory cleanup: {str(e)}")
        return False

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
                
                # Always use vertical window mode
                data = {'window_mode': 'vertical'}
                
                response = requests.post(
                    f"{app.config['BACKEND_URL']}/api/extract-payslip", 
                    files=files,
                    data=data
                )
            
            # Clean up the temporary file
            os.remove(filepath)
            
            # Always request GPU memory cleanup after processing
            cleanup_gpu_memory()
            
            if response.status_code == 200:
                result = response.json()
                return jsonify(result)
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

@app.route('/upload-payslip-batch', methods=['POST'])
def upload_payslip_batch():
    files = []
    
    # Extract all files from the form data
    for key, file in request.files.items():
        if file.filename != '':
            # Save file temporarily
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            files.append((filename, filepath))
    
    if not files:
        return jsonify({'error': 'No valid files found'}), 400
    
    batch_results = []
    
    try:
        # Process each file individually
        for filename, filepath in files:
            app.logger.info(f"Processing file: {filename}")
            try:
                with open(filepath, 'rb') as f:
                    files_dict = {'file': (filename, f, 'application/pdf')}
                    
                    # Always use vertical window mode
                    data = {'window_mode': 'vertical'}
                    
                    response = requests.post(
                        f"{app.config['BACKEND_URL']}/api/extract-payslip", 
                        files=files_dict,
                        data=data
                    )
                
                # Check for successful processing
                if response.status_code == 200:
                    result = response.json()
                    batch_results.append({
                        'filename': filename,
                        'success': True,
                        'data': result
                    })
                else:
                    error_message = 'Backend processing failed'
                    try:
                        error_data = response.json()
                        if 'detail' in error_data:
                            error_message = error_data['detail']
                    except:
                        pass
                    batch_results.append({
                        'filename': filename,
                        'success': False,
                        'error': error_message
                    })
                    
                # Always request GPU memory cleanup after each file
                cleanup_gpu_memory()
                    
            except Exception as e:
                app.logger.error(f"Error processing file {filename}: {str(e)}")
                batch_results.append({
                    'filename': filename,
                    'success': False,
                    'error': str(e)
                })
    finally:
        # Clean up all temporary files
        for _, filepath in files:
            if os.path.exists(filepath):
                os.remove(filepath)
    
    # Return batch results
    return jsonify({
        'batch_results': batch_results,
        'total_files': len(files),
        'successful_files': sum(1 for result in batch_results if result.get('success', False))
    })

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
                files = {'file': (filename, f, 'application/pdf')}
                
                # Always use whole window mode for property documents
                data = {'window_mode': 'whole'}
                
                response = requests.post(
                    f"{app.config['BACKEND_URL']}/api/extract-property", 
                    files=files,
                    data=data
                )
            
            # Clean up the temporary file
            os.remove(filepath)
            
            # Always request GPU memory cleanup after processing
            cleanup_gpu_memory()
            
            if response.status_code == 200:
                result = response.json()
                return jsonify(result)
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
            app.logger.error(f"Error in property file processing: {str(e)}")
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