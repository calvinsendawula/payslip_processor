document.addEventListener('DOMContentLoaded', function() {
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
    const payslipContent = document.getElementById('payslip-content');
    
    // Setup drag and drop for payslips
    payslipDropArea.addEventListener('click', () => payslipFileInput.click());
    
    payslipDropArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        payslipDropArea.style.borderColor = '#1976d2';
    });
    
    payslipDropArea.addEventListener('dragleave', () => {
        payslipDropArea.style.borderColor = '#ccc';
    });
    
    payslipDropArea.addEventListener('drop', (e) => {
        e.preventDefault();
        payslipDropArea.style.borderColor = '#ccc';
        
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
        
        // Show loading state
        payslipResults.style.display = 'block';
        payslipLoading.style.display = 'block';
        payslipContent.style.display = 'none';
        
        // Define the statusElement variable that was missing
        const statusElement = document.getElementById('payslip-status');
        
        // Send to backend
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
            
            // Get the first page data
            const pageData = data.pages[0];
            
            // Update employee name
            document.getElementById('employee-name').textContent = pageData.employee.name.extracted;
            const nameMatch = document.getElementById('employee-name-match');
            const nameExpected = document.getElementById('employee-name-expected');
            
            if (pageData.employee.name.matches) {
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
        })
        .catch(error => {
            payslipLoading.style.display = 'none';
            payslipContent.style.display = 'block';
            
            // Show error message
            document.getElementById('payslip-status').innerHTML = 
                `<span class="material-icons">error</span><span>${error.message || "404: Keine gültigen Gehaltsabrechnungsdaten gefunden"}</span>`;
            document.getElementById('payslip-status').className = 'summary-item error';
            
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
        propertyDropArea.style.borderColor = '#1976d2';
    });
    
    propertyDropArea.addEventListener('dragleave', () => {
        propertyDropArea.style.borderColor = '#ccc';
    });
    
    propertyDropArea.addEventListener('drop', (e) => {
        e.preventDefault();
        propertyDropArea.style.borderColor = '#ccc';
        
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