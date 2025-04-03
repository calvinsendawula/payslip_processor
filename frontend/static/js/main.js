// Tab switching functionality
function showTab(tabName) {
    // Hide all tab contents
    const tabContents = document.querySelectorAll('.tab-content');
    tabContents.forEach(tab => tab.classList.remove('active'));
    
    // Show the selected tab content
    const selectedTab = document.getElementById(`${tabName}-tab`);
    if (selectedTab) {
        selectedTab.classList.add('active');
    } else {
        console.error(`Tab content with ID '${tabName}-tab' not found`);
    }
    
    // Update navigation items
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(nav => {
        if (nav.getAttribute('data-tab') === tabName) {
            nav.classList.add('active');
        } else {
            nav.classList.remove('active');
        }
    });
}

document.addEventListener('DOMContentLoaded', function() {
    // Docker container status check
    const dockerStatusIndicator = document.getElementById('docker-status-indicator');
    const dockerStatusText = document.getElementById('docker-status-text');
    
    // Processing mode selection
    const processingModeRadios = document.querySelectorAll('input[name="processing-mode"]');
    const singleUploadContainer = document.getElementById('payslip-single-upload');
    const batchUploadContainer = document.getElementById('payslip-batch-upload');
    const singleFileResults = document.getElementById('single-file-results');
    const batchResults = document.getElementById('batch-results');
    
    // Handle processing mode changes
    processingModeRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            if (this.value === 'single') {
                singleUploadContainer.style.display = 'block';
                batchUploadContainer.style.display = 'none';
                if (document.getElementById('payslip-results').style.display === 'block') {
                    singleFileResults.style.display = 'block';
                    batchResults.style.display = 'none';
                }
            } else if (this.value === 'batch') {
                singleUploadContainer.style.display = 'none';
                batchUploadContainer.style.display = 'block';
                if (document.getElementById('payslip-results').style.display === 'block') {
                    singleFileResults.style.display = 'none';
                    batchResults.style.display = 'block';
                }
            }
        });
    });
    
    // Check container status immediately and periodically
    checkContainerStatus();
    setInterval(checkContainerStatus, 10000); // Check every 10 seconds
    
    function checkContainerStatus() {
        // Show loading indicator
        dockerStatusIndicator.className = 'status-indicator loading';
        dockerStatusText.textContent = 'Checking Docker status...';

        // Call the API to check container status
        fetch('/api/container-status')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                const statusIndicator = document.getElementById('docker-status-indicator');
                const statusText = document.getElementById('docker-status-text');
                const restartButton = document.getElementById('restart-container-button');
                
                // First check if backend is available
                if (data.hasOwnProperty('backend_available') && !data.backend_available) {
                    // Backend is not available
                    statusIndicator.className = 'status-indicator error';
                    statusText.textContent = 'Error connecting to backend server';
                    if (restartButton) {
                        restartButton.style.display = 'none';
                    }
                    disableFormInputs();
                    return;
                }
                
                // Accept 'running' or 'ok' status values
                if (data.status === 'running' || data.status === 'ok') {
                    statusIndicator.className = 'status-indicator online';
                    statusText.textContent = 'Docker container running';
                    
                    // Show model info if available
                    if (data.model) {
                        statusText.textContent += ` (${data.model})`;
                    }
                    
                    // Show GPU status if available
                    if (data.gpu_available) {
                        const gpuBadge = document.createElement('span');
                        gpuBadge.className = data.using_gpu ? 'gpu-badge gpu-enabled' : 'gpu-badge gpu-disabled';
                        gpuBadge.textContent = data.using_gpu ? 'GPU ENABLED' : 'GPU NOT USED';
                        statusText.appendChild(document.createTextNode(' '));
                        statusText.appendChild(gpuBadge);
                        
                        // Show restart button if GPU is available but not used
                        if (!data.using_gpu) {
                            if (restartButton) {
                            restartButton.style.display = 'inline-block';
                            }
                        } else {
                            if (restartButton) {
                            restartButton.style.display = 'none';
                            }
                        }
                    } else {
                        if (restartButton) {
                        restartButton.style.display = 'none';
                        }
                    }
                    
                    // Enable form inputs
                    enableFormInputs();
                } else if (data.status === 'initializing') {
                    statusIndicator.className = 'status-indicator initializing';
                    statusText.textContent = 'Docker container starting...';
                    if (restartButton) {
                    restartButton.style.display = 'none';
                    }
                    
                    // Try again in 5 seconds
                    setTimeout(checkContainerStatus, 5000);
                    
                    // Disable form inputs
                    disableFormInputs();
                } else if (data.status === 'stopped') {
                    statusIndicator.className = 'status-indicator offline';
                    statusText.textContent = 'Docker container is stopped';
                    if (restartButton) {
                    restartButton.style.display = 'none';
                    }
                    
                    // Disable form inputs
                    disableFormInputs();
                } else if (data.status === 'not_found') {
                    statusIndicator.className = 'status-indicator offline';
                    statusText.textContent = 'Docker container not found';
                    if (restartButton) {
                    restartButton.style.display = 'none';
                    }
                    
                    // Disable form inputs
                    disableFormInputs();
                } else {
                    // Any other status is treated as an error
                    statusIndicator.className = 'status-indicator error';
                    statusText.textContent = data.message || 'Error checking Docker status';
                    if (restartButton) {
                    restartButton.style.display = 'none';
                    }
                    
                    // Disable form inputs
                    disableFormInputs();
                }
            })
            .catch(error => {
                console.error('Error checking container status:', error);
                const statusIndicator = document.getElementById('docker-status-indicator');
                const statusText = document.getElementById('docker-status-text');
                
                statusIndicator.className = 'status-indicator error';
                statusText.textContent = 'Error connecting to backend';
                
                // Disable form inputs
                disableFormInputs();
            });
    }
    
    function restartContainerWithGPU() {
        // Show loading state
        const restartButton = document.getElementById('restart-container-button');
        const originalText = restartButton.textContent;
        restartButton.textContent = 'Restarting...';
        restartButton.disabled = true;
        
        // Update status indicator
        const statusIndicator = document.getElementById('docker-status-indicator');
        const statusText = document.getElementById('docker-status-text');
        statusIndicator.className = 'status-indicator initializing';
        statusText.textContent = 'Restarting Docker container with GPU support...';
        
        // Call API to restart container
        fetch('/api/restart-container-with-gpu', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({})
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // Container is restarting, poll status
                statusText.textContent = 'Container restarting with GPU... ';
                
                // Poll status every 5 seconds
                const checkStatus = () => {
                    fetch('/api/container-status')
                        .then(response => response.json())
                        .then(statusData => {
                            if (statusData.status === 'running') {
                                // Container is up, check if GPU is enabled
                                if (statusData.using_gpu) {
                                    statusIndicator.className = 'status-indicator online';
                                    statusText.textContent = 'Docker container running with GPU';
                                    restartButton.style.display = 'none';
                                    enableFormInputs();
                                } else {
                                    // Container is running but not using GPU
                                    statusIndicator.className = 'status-indicator warning';
                                    statusText.textContent = 'Docker container running, but still not using GPU';
                                    restartButton.textContent = originalText;
                                    restartButton.disabled = false;
                                    enableFormInputs();
                                }
                            } else if (statusData.status === 'initializing') {
                                // Container still starting, check again
                                statusIndicator.className = 'status-indicator initializing';
                                statusText.textContent = 'Container still starting...';
                                setTimeout(checkStatus, 5000);
                            } else {
                                // Container in other state
                                statusIndicator.className = 'status-indicator warning';
                                statusText.textContent = `Container in unexpected state: ${statusData.status}`;
                                restartButton.textContent = originalText;
                                restartButton.disabled = false;
                            }
                        })
                        .catch(error => {
                            console.error('Error checking status during restart:', error);
                            statusIndicator.className = 'status-indicator error';
                            statusText.textContent = 'Error checking container status';
                            restartButton.textContent = originalText;
                            restartButton.disabled = false;
                        });
                };
                
                // Start polling
                setTimeout(checkStatus, 5000);
                
            } else {
                // Error restarting
                statusIndicator.className = 'status-indicator error';
                statusText.textContent = `Error restarting container: ${data.message}`;
                restartButton.textContent = originalText;
                restartButton.disabled = false;
            }
        })
        .catch(error => {
            console.error('Error restarting container:', error);
            statusIndicator.className = 'status-indicator error';
            statusText.textContent = 'Error communicating with backend';
            restartButton.textContent = originalText;
            restartButton.disabled = false;
        });
    }
    
    // Enable or disable form inputs based on container status
    function enableFormInputs() {
        const uploadForms = document.querySelectorAll('.upload-form');
        uploadForms.forEach(form => {
            const inputs = form.querySelectorAll('input, button, select');
            inputs.forEach(input => {
                input.disabled = false;
            });
        });
    }

    function disableFormInputs() {
        const uploadForms = document.querySelectorAll('.upload-form');
        uploadForms.forEach(form => {
            const inputs = form.querySelectorAll('input, button, select');
            inputs.forEach(input => {
                if (input.id !== 'restart-container-button') {
                    input.disabled = true;
                }
            });
        });
    }
    
    // Tab switching
    const navItems = document.querySelectorAll('.nav-item');
    const tabContents = document.querySelectorAll('.tab-content');
    
    navItems.forEach(item => {
        item.addEventListener('click', function() {
            // Remove active class from all nav items
            navItems.forEach(nav => nav.classList.remove('active'));
            // Add active class to clicked nav item
            this.classList.add('active');
            
            // Hide all tab contents
            tabContents.forEach(tab => tab.classList.remove('active'));
            // Show the corresponding tab content
            const tabId = this.getAttribute('data-tab');
            document.getElementById(`${tabId}-tab`).classList.add('active');
        });
    });
    
    // Payslip Upload Functionality
    const payslipDropArea = document.getElementById('payslip-drop-area');
    const payslipFileInput = document.getElementById('payslip-file-input');
    const payslipUploadBtn = document.getElementById('payslip-upload-btn');
    const payslipResults = document.getElementById('payslip-results');
    const payslipLoading = document.getElementById('payslip-loading');
    const payslipContent = document.getElementById('payslip-results-content');
    
    // Setup drag and drop for payslips
    payslipDropArea.addEventListener('click', () => payslipFileInput.click());
    
    payslipDropArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        payslipDropArea.style.borderColor = '#257f49';
    });
    
    payslipDropArea.addEventListener('dragleave', () => {
        payslipDropArea.style.borderColor = '#005f3d';
    });
    
    payslipDropArea.addEventListener('drop', (e) => {
        e.preventDefault();
        payslipDropArea.style.borderColor = '#005f3d';
        
        if (e.dataTransfer.files.length) {
            payslipFileInput.files = e.dataTransfer.files;
            updatePayslipFileName();
        }
    });
    
    payslipFileInput.addEventListener('change', updatePayslipFileName);
    
    function updatePayslipFileName() {
        if (payslipFileInput.files.length) {
            const fileName = payslipFileInput.files[0].name;
            payslipDropArea.querySelector('p').textContent = `Ausgewählte Datei: ${fileName}`;
        }
    }
    
    // Handle payslip upload
    payslipUploadBtn.addEventListener('click', () => {
        if (!payslipFileInput.files.length) {
            alert('Bitte wählen Sie zuerst eine Datei aus');
            return;
        }
        
        const file = payslipFileInput.files[0];
        const formData = new FormData();
        formData.append('file', file);
        
        // Always use vertical mode
        formData.append('window_mode', 'vertical');
        
        // Get references to DOM elements and check if they exist
        const payslipResults = document.getElementById('payslip-results');
        const payslipLoading = document.getElementById('payslip-loading');
        const payslipContent = document.getElementById('payslip-results-content');
        
        // Show loading state - using optional chaining to avoid errors
        if (payslipResults) payslipResults.style.display = 'block';
        if (payslipLoading) payslipLoading.style.display = 'block';
        if (payslipContent) payslipContent.style.display = 'none';
        
        // Reset the employee search if it was previously displayed
        const employeeSearch = document.querySelector('.search-container');
        const employeeIdInput = document.getElementById('employee-id');
        
        if (employeeSearch) {
            employeeSearch.style.display = 'none';
        }
        if (employeeIdInput) {
            employeeIdInput.value = '';
        }
        
        // Define the statusElement variable
        const statusElement = document.getElementById('payslip-status');
        
        // Get processing mode
        const processingMode = document.querySelector('input[name="processing-mode"]:checked');
        
        // Default to single file processing if no mode is selected
        if (!processingMode || processingMode.value === 'single') {
            // Send to backend for extraction
            fetch('/upload-payslip', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(data => {
                        throw new Error(data.error || 'Fehler bei der Verarbeitung der Gehaltsabrechnung');
                    });
                }
                return response.json();
            })
            .then(data => {
                // Hide loading, show results
                if (payslipLoading) payslipLoading.style.display = 'none';
                if (payslipContent) payslipContent.style.display = 'block';
                
                // Make sure the single file results are displayed
                if (document.getElementById('single-file-results')) {
                    document.getElementById('single-file-results').style.display = 'block';
                }
                if (document.getElementById('batch-results')) {
                    document.getElementById('batch-results').style.display = 'none';
                }
                
                // Display the extracted data
                displayExtractedData(data);
            })
            .catch(error => {
                if (payslipLoading) payslipLoading.style.display = 'none';
                if (payslipContent) payslipContent.style.display = 'block';
                
                // Show error message
                if (statusElement) {
                    statusElement.innerHTML = 
                        `<span class="material-icons">error</span><span>${error.message || "Fehler bei der Verarbeitung der Gehaltsabrechnung"}</span>`;
                    statusElement.className = 'summary-item error';
                }
                
                // Clear other fields
                const elements = [
                    'employee-name', 'employee-name-match', 'employee-name-expected',
                    'gross-amount', 'gross-amount-match', 'gross-amount-expected',
                    'net-amount', 'net-amount-match', 'net-amount-expected'
                ];
                
                elements.forEach(id => {
                    const element = document.getElementById(id);
                    if (element) {
                        if (id.includes('match')) {
                            element.innerHTML = '';
                        } else {
                            element.textContent = '';
                        }
                    }
                });
            });
        } else if (processingMode.value === 'batch') {
            // Get batch file input
            const batchFileInput = document.getElementById('payslip-batch-file-input');
            
            if (!batchFileInput.files || batchFileInput.files.length === 0) {
                alert('Bitte wählen Sie mindestens eine Datei aus.');
                payslipLoading.style.display = 'none';
                return;
            }
            
            // Create form data
            const batchFormData = new FormData();
            
            // Append all files
            Array.from(batchFileInput.files).forEach((file, index) => {
                batchFormData.append(`file_${index}`, file);
            });
            
            // Always use vertical mode for batch processing too
            batchFormData.append('window_mode', 'vertical');
            
            // Send the request
            fetch('/upload-payslip-batch', {
                method: 'POST',
                body: batchFormData
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(data => {
                        throw new Error(data.error || 'Fehler bei der Stapelverarbeitung');
                    });
                }
                return response.json();
            })
            .then(data => {
                // Hide loading indicator
                if (payslipLoading) payslipLoading.style.display = 'none';
                if (payslipContent) payslipContent.style.display = 'block';
                
                // Make sure the batch results are displayed
                if (document.getElementById('single-file-results')) {
                    document.getElementById('single-file-results').style.display = 'none';
                }
                if (document.getElementById('batch-results')) {
                    document.getElementById('batch-results').style.display = 'block';
                }
                
                // Display batch results
                displayBatchResults(data);
            })
            .catch(error => {
                console.error('Batch upload error:', error);
                if (payslipLoading) payslipLoading.style.display = 'none';
                if (payslipContent) payslipContent.style.display = 'block';
                
                // Show error message
                if (statusElement) {
                    statusElement.innerHTML = 
                        `<span class="material-icons">error</span><span>${error.message || "Fehler bei der Stapelverarbeitung"}</span>`;
                    statusElement.className = 'summary-item error';
                }
            });
        }
    });
    
    // Update UI with validation results (new)
    function updateValidationResults(data) {
        const statusElement = document.getElementById('payslip-status');
        const nameMatch = document.getElementById('employee-name-match');
        const nameExpected = document.getElementById('employee-name-expected');
        const grossMatch = document.getElementById('gross-amount-match');
        const grossExpected = document.getElementById('gross-amount-expected');
        const netMatch = document.getElementById('net-amount-match');
        const netExpected = document.getElementById('net-amount-expected');
        
        // Check if employee was found
        if (data.employeeFound) {
            // Update name validation
            if (data.validation.name.matches) {
                nameMatch.innerHTML = '<span class="material-icons">check_circle</span>';
                nameMatch.className = 'detail-match match-success';
                nameExpected.className = 'detail-expected';
                nameExpected.textContent = '';
            } else {
                nameMatch.innerHTML = '<span class="material-icons">error</span>';
                nameMatch.className = 'detail-match match-error';
                nameExpected.className = 'detail-expected show';
                nameExpected.textContent = `(Erwartet: ${pageData.employee.name.stored})`;
            }
            
            // Update payment information
            document.getElementById('payment-gross').textContent = `${pageData.payment.gross.extracted} €`;
            const grossMatch = document.getElementById('payment-gross-match');
            const grossExpected = document.getElementById('payment-gross-expected');
            
            if (pageData.payment.gross.matches) {
                grossMatch.innerHTML = '<span class="material-icons">check_circle</span>';
                grossMatch.className = 'detail-match match-success';
                grossExpected.className = 'detail-expected';
                grossExpected.textContent = '';
            } else {
                grossMatch.innerHTML = '<span class="material-icons">error</span>';
                grossMatch.className = 'detail-match match-error';
                grossExpected.className = 'detail-expected show';
                grossExpected.textContent = `(Erwartet: ${pageData.payment.gross.stored} €)`;
            }
            
            document.getElementById('payment-net').textContent = `${pageData.payment.net.extracted} €`;
            const netMatch = document.getElementById('payment-net-match');
            const netExpected = document.getElementById('payment-net-expected');
            
            if (pageData.payment.net.matches) {
                netMatch.innerHTML = '<span class="material-icons">check_circle</span>';
                netMatch.className = 'detail-match match-success';
                netExpected.className = 'detail-expected';
                netExpected.textContent = '';
            } else {
                netMatch.innerHTML = '<span class="material-icons">error</span>';
                netMatch.className = 'detail-match match-error';
                netExpected.className = 'detail-expected show';
                netExpected.textContent = `(Erwartet: ${pageData.payment.net.stored} €)`;
            }
            
            // Update overall status
            const allMatch = pageData.employee.name.matches && 
                            pageData.payment.gross.matches && 
                            pageData.payment.net.matches;
            
            if (allMatch) {
                statusElement.innerHTML = '<span class="material-icons">check_circle</span><span>Gehaltsabrechnung erfolgreich validiert</span>';
                statusElement.className = 'summary-item success';
            } else {
                statusElement.innerHTML = '<span class="material-icons">error</span><span>Abweichungen festgestellt</span>';
                statusElement.className = 'summary-item error';
            }
        } else {
            // Employee not found
            statusElement.innerHTML = '<span class="material-icons">error</span><span>Mitarbeiter nicht gefunden</span>';
            statusElement.className = 'summary-item error';
            
            // Reset validation indicators
            nameMatch.innerHTML = '<span class="material-icons">help</span>';
            nameMatch.className = 'detail-match';
            nameExpected.className = 'detail-expected';
            nameExpected.textContent = '';
            
            grossMatch.innerHTML = '<span class="material-icons">help</span>';
            grossMatch.className = 'detail-match';
            grossExpected.className = 'detail-expected';
            grossExpected.textContent = '';
            
            netMatch.innerHTML = '<span class="material-icons">help</span>';
            netMatch.className = 'detail-match';
            netExpected.className = 'detail-expected';
            netExpected.textContent = '';
        }
    }
    
    // Ensure data has the correct format before displaying
    function ensureDataFormat(data) {
        if (!data) return { employee: { name: "" }, payment: { gross: "", net: "" } };
        
        // If data already has the correct structure, return it as is
        if (data.employee && data.payment) return data;
        
        // Create properly formatted data object
        return {
            employee: {
                name: data.extracted_data?.employee?.name || ""
            },
            payment: {
                gross: data.extracted_data?.payment?.gross || "",
                net: data.extracted_data?.payment?.net || ""
            },
            processing_time: data.processing?.processing_time_seconds + " seconds" || ""
        };
    }
    
    // Display initially extracted data (new)
    function displayExtractedData(data) {
        // Format data to ensure it has the expected structure
        data = ensureDataFormat(data);
        
        // Store the extracted data for later validation
        currentExtractedData = data;
        
        // Display the extracted data
        const employeeNameEl = document.getElementById('employee-name');
        const grossAmountEl = document.getElementById('gross-amount');
        const netAmountEl = document.getElementById('net-amount');
        
        if (employeeNameEl) employeeNameEl.textContent = data.employee.name || '';
        if (grossAmountEl) grossAmountEl.textContent = data.payment.gross || '';
        if (netAmountEl) netAmountEl.textContent = data.payment.net || '';
        
        // Display processing time if available
        const statusElement = document.getElementById('payslip-status');
        if (statusElement) {
        if (data.processing_time) {
            statusElement.innerHTML = 
                `<span class="material-icons">check_circle</span><span>Verarbeitung abgeschlossen in ${data.processing_time}</span>`;
            statusElement.className = 'summary-item success';
        } else {
            statusElement.innerHTML = 
                `<span class="material-icons">check_circle</span><span>Verarbeitung abgeschlossen</span>`;
            statusElement.className = 'summary-item success';
            }
        }
        
        // Set all indicators to pending state
        const nameMatch = document.getElementById('employee-name-match');
        const grossMatch = document.getElementById('gross-amount-match');
        const netMatch = document.getElementById('net-amount-match');
        
        if (nameMatch) {
        nameMatch.innerHTML = '<span class="material-icons">pending</span>';
        nameMatch.className = 'detail-match match-pending';
        }
        
        if (grossMatch) {
        grossMatch.innerHTML = '<span class="material-icons">pending</span>';
        grossMatch.className = 'detail-match match-pending';
        }
        
        if (netMatch) {
        netMatch.innerHTML = '<span class="material-icons">pending</span>';
        netMatch.className = 'detail-match match-pending';
        }
        
        // Show the employee search container
        const employeeSearch = document.querySelector('.search-container');
        if (employeeSearch) {
            employeeSearch.style.display = 'block';
        }
    }
    
    // Function to display batch results
    function displayBatchResults(data) {
        // Update batch statistics
        if (document.getElementById('batch-total')) {
            document.getElementById('batch-total').textContent = data.total_files || 0;
        }
        if (document.getElementById('batch-success')) {
            document.getElementById('batch-success').textContent = data.successful || 0;
        }
        if (document.getElementById('batch-error')) {
            document.getElementById('batch-error').textContent = data.failed || 0;
        }
        
        // Populate the results table
        const tableBody = document.getElementById('batch-results-body');
        if (tableBody) {
            tableBody.innerHTML = '';
            
            if (data.results && data.results.length > 0) {
                data.results.forEach(result => {
                    const row = document.createElement('tr');
                    
                    // File name cell
                    const fileCell = document.createElement('td');
                    fileCell.textContent = result.filename || 'Unbekannt';
                    row.appendChild(fileCell);
                    
                    // Employee name cell
                    const nameCell = document.createElement('td');
                    nameCell.textContent = result.employee_name || 'Nicht gefunden';
                    row.appendChild(nameCell);
                    
                    // Gross amount cell
                    const grossCell = document.createElement('td');
                    grossCell.textContent = result.gross_amount || 'Nicht gefunden';
                    row.appendChild(grossCell);
                    
                    // Net amount cell
                    const netCell = document.createElement('td');
                    netCell.textContent = result.net_amount || 'Nicht gefunden';
                    row.appendChild(netCell);
                    
                    // Status cell
                    const statusCell = document.createElement('td');
                    const statusSpan = document.createElement('span');
                    statusSpan.className = `batch-status ${result.success ? 'success' : 'error'}`;
                    statusSpan.innerHTML = result.success ? 
                        '<span class="material-icons">check_circle</span>Erfolgreich' : 
                        '<span class="material-icons">error</span>Fehler';
                    statusCell.appendChild(statusSpan);
                    row.appendChild(statusCell);
                    
                    tableBody.appendChild(row);
                });
            } else {
                const row = document.createElement('tr');
                const cell = document.createElement('td');
                cell.setAttribute('colspan', '5');
                cell.textContent = 'Keine Ergebnisse verfügbar';
                cell.style.textAlign = 'center';
                row.appendChild(cell);
                tableBody.appendChild(row);
            }
        }
    }
    
    // Property Upload Functionality
    const propertyDropArea = document.getElementById('property-drop-area');
    const propertyFileInput = document.getElementById('property-file-input');
    const propertyUploadBtn = document.getElementById('property-upload-btn');
    const propertyResults = document.getElementById('property-results');
    const propertyLoading = document.getElementById('property-loading');
    const propertyContent = document.getElementById('property-content');
    
    // Setup drag and drop for property listings
    propertyDropArea.addEventListener('click', () => propertyFileInput.click());
    
    propertyDropArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        propertyDropArea.style.borderColor = '#257f49';
    });
    
    propertyDropArea.addEventListener('dragleave', () => {
        propertyDropArea.style.borderColor = '#005f3d';
    });
    
    propertyDropArea.addEventListener('drop', (e) => {
        e.preventDefault();
        propertyDropArea.style.borderColor = '#005f3d';
        
        if (e.dataTransfer.files.length) {
            propertyFileInput.files = e.dataTransfer.files;
            updatePropertyFileName();
        }
    });
    
    propertyFileInput.addEventListener('change', updatePropertyFileName);
    
    function updatePropertyFileName() {
        if (propertyFileInput.files.length) {
            const fileName = propertyFileInput.files[0].name;
            propertyDropArea.querySelector('p').textContent = `Ausgewählte Datei: ${fileName}`;
        }
    }
    
    // Handle property upload
    propertyUploadBtn.addEventListener('click', () => {
        if (!propertyFileInput.files.length) {
            alert('Bitte wählen Sie zuerst eine Datei aus');
            return;
        }
        
        const file = propertyFileInput.files[0];
        const formData = new FormData();
        formData.append('file', file);
        
        // Show loading state
        propertyResults.style.display = 'block';
        propertyLoading.style.display = 'block';
        propertyContent.style.display = 'none';
        
        // Send to backend
        fetch('/upload-property', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(data => {
                    throw new Error(data.error || 'Fehler bei der Verarbeitung des Immobilienangebots');
                });
            }
            return response.json();
        })
        .then(data => {
            // Hide loading, show results
            propertyLoading.style.display = 'none';
            propertyContent.style.display = 'block';
            
            // Extract only the relevant parts from the property data
            let livingSpace = data.living_space;
            let purchasePrice = data.purchase_price;
            
            // For living space, extract just the measurement part if it contains "Wohnfläche"
            if (livingSpace.includes("Wohnfläche")) {
                const match = livingSpace.match(/ca\.\s+\d+\s*m²/);
                if (match) {
                    livingSpace = match[0];
                }
            }
            
            // For purchase price, extract just the amount if it contains "Kaufpreis"
            if (purchasePrice.includes("Kaufpreis")) {
                const match = purchasePrice.match(/\d+\.\d+,\d+\s*€/);
                if (match) {
                    purchasePrice = match[0];
                }
            }
            
            // Update property information
            document.getElementById('property-space').textContent = livingSpace;
            document.getElementById('property-price').textContent = purchasePrice;
        })
        .catch(error => {
            propertyLoading.style.display = 'none';
            propertyContent.style.display = 'block';
            
            // Show error message in property space and price fields
            document.getElementById('property-space').textContent = 'Fehler: ' + error.message;
            document.getElementById('property-price').textContent = '';
        });
    });

    // Add restart button event listener if it exists
    const restartButton = document.getElementById('restart-container-button');
    if (restartButton) {
        restartButton.addEventListener('click', restartContainerWithGPU);
    }
    
    // Setup form event listeners
    setupPayslipFormSubmit();
    setupPropertyFormSubmit();
    
    // Show initial tab
    showTab('payslips');
    
    // Add tab switching handlers
    const payslipTab = document.querySelector('.nav-item[data-tab="payslips"]');
    if (payslipTab) {
        console.log('Found payslips tab, adding click handler');
        payslipTab.addEventListener('click', function() {
            showTab('payslips');
        });
    } else {
        console.error('Payslips tab element not found');
    }
    
    const propertyTab = document.querySelector('.nav-item[data-tab="properties"]');
    if (propertyTab) {
        console.log('Found properties tab, adding click handler');
        propertyTab.addEventListener('click', function() {
            showTab('properties');
        });
    } else {
        console.error('Properties tab element not found');
    }

    // Setup batch upload button
    const batchUploadBtn = document.getElementById('payslip-batch-upload-btn');
    if (batchUploadBtn) {
        batchUploadBtn.addEventListener('click', handleBatchUpload);
    }
    
    // Setup batch upload drag-and-drop functionality
    setupBatchUpload();

    // Setup payslip file upload
    setupPayslipUpload();
});

// Function to handle batch upload
function handleBatchUpload() {
    const batchFileInput = document.getElementById('payslip-batch-file-input');
    const payslipLoading = document.getElementById('payslip-loading');
    const payslipResults = document.getElementById('payslip-results');
    const payslipContent = document.getElementById('payslip-results-content');
    const statusElement = document.getElementById('payslip-status');
    
    if (!batchFileInput || !batchFileInput.files || batchFileInput.files.length === 0) {
        alert('Bitte wählen Sie mindestens eine Datei aus.');
        return;
    }
    
    // Show loading state
    if (payslipLoading) payslipLoading.style.display = 'block';
    if (payslipResults) payslipResults.style.display = 'block';
    if (payslipContent) payslipContent.style.display = 'none';
    
    // Create form data
    const batchFormData = new FormData();
    
    // Append all files
    Array.from(batchFileInput.files).forEach((file, index) => {
        batchFormData.append(`file_${index}`, file);
    });
    
    console.log(`Uploading ${batchFileInput.files.length} files for batch processing...`);
    
    // Send the request
    fetch('/upload-payslip-batch', {
        method: 'POST',
        body: batchFormData
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.error || 'Fehler bei der Stapelverarbeitung');
            });
        }
        return response.json();
    })
    .then(data => {
        // Hide loading indicator
        if (payslipLoading) payslipLoading.style.display = 'none';
        if (payslipContent) payslipContent.style.display = 'block';
        
        // Make sure the batch results are displayed
        if (document.getElementById('single-file-results')) {
            document.getElementById('single-file-results').style.display = 'none';
        }
        if (document.getElementById('batch-results')) {
            document.getElementById('batch-results').style.display = 'block';
        }
        
        // Display batch results
        displayBatchResults(data);
    })
    .catch(error => {
        console.error('Batch upload error:', error);
        if (payslipLoading) payslipLoading.style.display = 'none';
        if (payslipContent) payslipContent.style.display = 'block';
        
        // Show error message
        if (statusElement) {
            statusElement.innerHTML = 
                `<span class="material-icons">error</span><span>${error.message || "Fehler bei der Stapelverarbeitung"}</span>`;
            statusElement.className = 'summary-item error';
        }
    });
}

// Function to setup batch upload drag-and-drop
function setupBatchUpload() {
    const batchDropArea = document.getElementById('payslip-batch-drop-area');
    const batchFileInput = document.getElementById('payslip-batch-file-input');
    const batchFileList = document.getElementById('batch-file-list');
    
    if (!batchDropArea || !batchFileInput || !batchFileList) return;
    
    // Handle click on drop area to trigger file input
    batchDropArea.addEventListener('click', () => {
        batchFileInput.click();
    });
    
    // Prevent default behaviors for drag events
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        batchDropArea.addEventListener(eventName, preventDefaults, false);
    });
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    // Highlight the drop area when dragging files over it
    ['dragenter', 'dragover'].forEach(eventName => {
        batchDropArea.addEventListener(eventName, () => {
            batchDropArea.classList.add('drag-active');
        }, false);
    });
    
    // Remove highlight when dragging leaves the drop area
    ['dragleave', 'drop'].forEach(eventName => {
        batchDropArea.addEventListener(eventName, () => {
            batchDropArea.classList.remove('drag-active');
        }, false);
    });
    
    // Handle dropped files
    batchDropArea.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            batchFileInput.files = files;
            updateBatchFileList(files);
        }
    }, false);
    
    // Handle selected files from file input
    batchFileInput.addEventListener('change', function() {
        if (this.files && this.files.length > 0) {
            updateBatchFileList(this.files);
        }
    });
    
    // Update batch file list
    function updateBatchFileList(files) {
        batchFileList.innerHTML = '';
        
        if (files.length === 0) {
            const noFilesElement = document.createElement('p');
            noFilesElement.textContent = 'Keine Dateien ausgewählt';
            batchFileList.appendChild(noFilesElement);
            return;
        }
        
        Array.from(files).forEach((file) => {
            const fileItem = document.createElement('div');
            fileItem.className = 'batch-file-item';
            
            const fileName = document.createElement('div');
            fileName.className = 'batch-file-name';
            fileName.textContent = file.name;
            
            fileItem.appendChild(fileName);
            batchFileList.appendChild(fileItem);
        });
    }
}

// Add the missing setupPayslipFormSubmit function
function setupPayslipFormSubmit() {
    console.log("Setting up payslip form submission...");
    // This function is now defined but doesn't need to do anything
    // since the upload functionality is handled by the click events we've already set up
}

// Add setupPropertyFormSubmit if it doesn't exist
function setupPropertyFormSubmit() {
    console.log("Setting up property form submission...");
    // This function is now defined but doesn't need to do anything
    // since the upload functionality is handled by the click events we've already set up
}

// Function to set up payslip upload
function setupPayslipUpload() {
    const dropArea = document.getElementById('payslip-drop-area');
    const fileInput = document.getElementById('payslip-file-input');
    const uploadBtn = document.getElementById('payslip-upload-btn');
    
    if (!dropArea || !fileInput || !uploadBtn) {
        console.error('Missing required elements for payslip upload');
        return;
    }
    
    // Handle click on drop area to trigger file input
    dropArea.addEventListener('click', () => {
        fileInput.click();
    });
    
    // Prevent default behaviors for drag events
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, e => {
            e.preventDefault();
            e.stopPropagation();
        }, false);
    });
    
    // Highlight the drop area when dragging files over it
    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, () => {
            dropArea.classList.add('drag-active');
        }, false);
    });
    
    // Remove highlight when dragging leaves the drop area
    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, () => {
            dropArea.classList.remove('drag-active');
        }, false);
    });
    
    // Handle dropped files
    dropArea.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            updateFileName(files[0].name);
        }
    }, false);
    
    // Handle selected files from file input
    fileInput.addEventListener('change', function() {
        if (this.files && this.files.length > 0) {
            updateFileName(this.files[0].name);
        }
    });
    
    // Update file name display
    function updateFileName(fileName) {
        // Remove existing file name if present
        const existingFileName = dropArea.querySelector('.file-name');
        if (existingFileName) {
            existingFileName.remove();
        }
        
        // Update the text in the drop area
        const textElement = dropArea.querySelector('p');
        if (textElement) {
            textElement.textContent = `Ausgewählte Datei: ${fileName}`;
        } else {
            // Create file name display element if not using the paragraph
            const fileNameElement = document.createElement('div');
            fileNameElement.className = 'file-name';
            fileNameElement.textContent = fileName;
            dropArea.appendChild(fileNameElement);
        }
    }
    
    // Handle upload button click - now handled in the main click handler
    console.log('Payslip upload functionality initialized');
} 