document.addEventListener('DOMContentLoaded', function() {
    // Tab switching
    const navItems = document.querySelectorAll('.nav-item');
    const tabContents = document.querySelectorAll('.tab-content');
    
    // Current extracted data storage - new addition
    let currentExtractedData = null;
    
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
    const payslipContent = document.getElementById('payslip-content');
    
    // Employee Search Functionality (new)
    const employeeSearch = document.getElementById('employee-search');
    const employeeIdInput = document.getElementById('employee-id');
    const validateBtn = document.getElementById('validate-btn');
    
    // Hide the search container initially
    if (employeeSearch) {
        employeeSearch.style.display = 'none';
    }
    
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
    
    // Setup validation click handler (new)
    if (validateBtn) {
        validateBtn.addEventListener('click', validateWithEmployeeId);
    }
    
    // Handle employee ID validation (new)
    function validateWithEmployeeId() {
        const employeeId = employeeIdInput.value.trim();
        
        if (!employeeId) {
            alert('Bitte geben Sie eine Mitarbeiter-ID ein');
            return;
        }
        
        if (!currentExtractedData) {
            alert('Keine extrahierten Daten vorhanden. Bitte laden Sie zuerst eine Gehaltsabrechnung hoch.');
            return;
        }
        
        // Show loading state during validation
        const statusElement = document.getElementById('payslip-status');
        statusElement.innerHTML = '<span class="material-icons">hourglass_top</span><span>Validierung läuft...</span>';
        statusElement.className = 'summary-item';
        
        // Send validation request to backend
        fetch('/validate-payslip', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                employeeId: employeeId,
                extractedData: currentExtractedData
            })
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(data => {
                    throw new Error(data.error || 'Fehler bei der Validierung');
                });
            }
            return response.json();
        })
        .then(data => {
            // Update the UI with validation results
            updateValidationResults(data);
        })
        .catch(error => {
            // Show error message
            statusElement.innerHTML = 
                `<span class="material-icons">error</span><span>${error.message || "Fehler bei der Validierung"}</span>`;
            statusElement.className = 'summary-item error';
        });
    }
    
    // Update UI with validation results (new)
    function updateValidationResults(data) {
        const statusElement = document.getElementById('payslip-status');
        const nameMatch = document.getElementById('employee-name-match');
        const nameExpected = document.getElementById('employee-name-expected');
        const grossMatch = document.getElementById('payment-gross-match');
        const grossExpected = document.getElementById('payment-gross-expected');
        const netMatch = document.getElementById('payment-net-match');
        const netExpected = document.getElementById('payment-net-expected');
        
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
                nameExpected.textContent = `(Erwartet: ${data.validation.name.expected})`;
            }
            
            // Update gross amount validation
            if (data.validation.gross.matches) {
                grossMatch.innerHTML = '<span class="material-icons">check_circle</span>';
                grossMatch.className = 'detail-match match-success';
                grossExpected.className = 'detail-expected';
                grossExpected.textContent = '';
            } else {
                grossMatch.innerHTML = '<span class="material-icons">error</span>';
                grossMatch.className = 'detail-match match-error';
                grossExpected.className = 'detail-expected show';
                grossExpected.textContent = `(Erwartet: ${data.validation.gross.expected} €)`;
            }
            
            // Update net amount validation
            if (data.validation.net.matches) {
                netMatch.innerHTML = '<span class="material-icons">check_circle</span>';
                netMatch.className = 'detail-match match-success';
                netExpected.className = 'detail-expected';
                netExpected.textContent = '';
            } else {
                netMatch.innerHTML = '<span class="material-icons">error</span>';
                netMatch.className = 'detail-match match-error';
                netExpected.className = 'detail-expected show';
                netExpected.textContent = `(Erwartet: ${data.validation.net.expected} €)`;
            }
            
            // Update overall status
            const allMatch = data.validation.name.matches && 
                            data.validation.gross.matches && 
                            data.validation.net.matches;
            
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
    
    // Display initially extracted data (new)
    function displayExtractedData(data) {
        // Store the extracted data for later validation
        currentExtractedData = data;
        
        // Display the data
        document.getElementById('employee-name').textContent = data.employee.name;
        document.getElementById('payment-gross').textContent = data.payment.gross;
        document.getElementById('payment-net').textContent = data.payment.net;
        
        // Set all indicators to pending state
        const nameMatch = document.getElementById('employee-name-match');
        const grossMatch = document.getElementById('payment-gross-match');
        const netMatch = document.getElementById('payment-net-match');
        
        nameMatch.innerHTML = '<span class="material-icons">pending</span>';
        nameMatch.className = 'detail-match match-pending';
        
        grossMatch.innerHTML = '<span class="material-icons">pending</span>';
        grossMatch.className = 'detail-match match-pending';
        
        netMatch.innerHTML = '<span class="material-icons">pending</span>';
        netMatch.className = 'detail-match match-pending';
        
        // Update status to show we need validation
        const statusElement = document.getElementById('payslip-status');
        statusElement.innerHTML = '<span class="material-icons">info</span><span>Daten extrahiert. Bitte geben Sie eine Mitarbeiter-ID ein, um zu validieren.</span>';
        statusElement.className = 'summary-item info';
        
        // Show the employee search container
        if (employeeSearch) {
            employeeSearch.style.display = 'block';
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
        
        // Show loading state
        payslipResults.style.display = 'block';
        payslipLoading.style.display = 'block';
        payslipContent.style.display = 'none';
        
        // Reset the employee search if it was previously displayed
        if (employeeSearch) {
            employeeSearch.style.display = 'none';
            employeeIdInput.value = '';
        }
        
        // Define the statusElement variable that was missing
        const statusElement = document.getElementById('payslip-status');
        
        // Send to backend for extraction only (not validation)
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
            payslipLoading.style.display = 'none';
            payslipContent.style.display = 'block';
            
            // Display the extracted data
            displayExtractedData(data);
        })
        .catch(error => {
            payslipLoading.style.display = 'none';
            payslipContent.style.display = 'block';
            
            // Show error message
            statusElement.innerHTML = 
                `<span class="material-icons">error</span><span>${error.message || "Fehler bei der Verarbeitung der Gehaltsabrechnung"}</span>`;
            statusElement.className = 'summary-item error';
            
            // Clear other fields
            document.getElementById('employee-name').textContent = '';
            document.getElementById('employee-name-match').innerHTML = '';
            document.getElementById('employee-name-expected').textContent = '';
            document.getElementById('payment-gross').textContent = '';
            document.getElementById('payment-gross-match').innerHTML = '';
            document.getElementById('payment-gross-expected').textContent = '';
            document.getElementById('payment-net').textContent = '';
            document.getElementById('payment-net-match').innerHTML = '';
            document.getElementById('payment-net-expected').textContent = '';
        });
    });
    
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
}); 