document.addEventListener('DOMContentLoaded', function() {
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('file-input');
    const uploadText = document.getElementById('upload-text');
    const loadingContainer = document.getElementById('loading');
    const resultsContainer = document.getElementById('results');
    const employeeInfo = document.getElementById('employee-info');
    const paymentInfo = document.getElementById('payment-info');
    const pageIndicator = document.getElementById('page-indicator');
    const pagination = document.getElementById('pagination');
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');
    
    let currentResults = null;
    let currentPage = 0;
    
    // Handle file selection via click
    dropzone.addEventListener('click', function() {
        fileInput.click();
    });
    
    fileInput.addEventListener('change', function() {
        if (this.files.length > 0) {
            handleFile(this.files[0]);
        }
    });
    
    // Handle drag and drop
    dropzone.addEventListener('dragover', function(e) {
        e.preventDefault();
        dropzone.classList.add('dragover');
        uploadText.textContent = 'Drop the payslip here...';
    });
    
    dropzone.addEventListener('dragleave', function() {
        dropzone.classList.remove('dragover');
        uploadText.textContent = 'Drag and drop your payslip';
    });
    
    dropzone.addEventListener('drop', function(e) {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        uploadText.textContent = 'Drag and drop your payslip';
        
        if (e.dataTransfer.files.length > 0) {
            handleFile(e.dataTransfer.files[0]);
        }
    });
    
    // Handle pagination
    prevBtn.addEventListener('click', function() {
        if (currentPage > 0) {
            currentPage--;
            displayResults();
        }
    });
    
    nextBtn.addEventListener('click', function() {
        if (currentResults && currentPage < currentResults.pages.length - 1) {
            currentPage++;
            displayResults();
        }
    });
    
    function handleFile(file) {
        // Check file type
        const validTypes = ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg'];
        if (!validTypes.includes(file.type)) {
            alert('Please upload a PDF or image file (JPG, PNG)');
            return;
        }
        
        // Show loading
        dropzone.style.display = 'none';
        loadingContainer.style.display = 'flex';
        resultsContainer.style.display = 'none';
        
        // Create form data
        const formData = new FormData();
        formData.append('file', file);
        
        // Send to backend via our Flask endpoint
        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(data => {
                    throw new Error(data.error || 'Failed to process payslip');
                });
            }
            return response.json();
        })
        .then(data => {
            currentResults = data;
            currentPage = 0;
            displayResults();
        })
        .catch(error => {
            alert(error.message);
            // Hide loading, show upload again
            loadingContainer.style.display = 'none';
            dropzone.style.display = 'block';
        });
    }
    
    function displayResults() {
        if (!currentResults) return;
        
        // Hide loading, show results
        loadingContainer.style.display = 'none';
        resultsContainer.style.display = 'block';
        
        const pageData = currentResults.pages[currentPage];
        const totalPages = currentResults.total_pages;
        
        // Update page indicator if multiple pages
        if (totalPages > 1) {
            pageIndicator.textContent = `- Page ${pageData.page} of ${totalPages}`;
            pagination.style.display = 'flex';
            prevBtn.disabled = currentPage === 0;
            nextBtn.disabled = currentPage === currentResults.pages.length - 1;
        } else {
            pageIndicator.textContent = '';
            pagination.style.display = 'none';
        }
        
        // Render employee information
        employeeInfo.innerHTML = '';
        Object.entries(pageData.employee).forEach(([key, value]) => {
            employeeInfo.appendChild(createDataItem(key, value));
        });
        
        // Render payment information
        paymentInfo.innerHTML = '';
        Object.entries(pageData.payment).forEach(([key, value]) => {
            paymentInfo.appendChild(createDataItem(key, value));
        });
    }
    
    function createDataItem(key, value) {
        const item = document.createElement('div');
        item.className = 'data-item';
        
        const title = document.createElement('div');
        title.className = 'data-item-title';
        title.textContent = key.charAt(0).toUpperCase() + key.slice(1);
        
        const content = document.createElement('div');
        content.className = 'data-item-content';
        
        const extracted = document.createElement('div');
        extracted.textContent = `Extracted: ${value.extracted}`;
        
        content.appendChild(extracted);
        
        if (value.stored !== undefined) {
            const stored = document.createElement('div');
            stored.textContent = `Stored: ${value.stored}`;
            content.appendChild(stored);
            
            const chip = document.createElement('div');
            chip.className = `chip ${value.matches ? 'success' : 'error'}`;
            
            const icon = document.createElement('span');
            icon.className = 'material-icons';
            icon.textContent = value.matches ? 'check_circle' : 'cancel';
            
            const label = document.createElement('span');
            label.textContent = value.matches ? 'Match' : 'Mismatch';
            
            chip.appendChild(icon);
            chip.appendChild(label);
            content.appendChild(chip);
        }
        
        item.appendChild(title);
        item.appendChild(content);
        
        return item;
    }
}); 