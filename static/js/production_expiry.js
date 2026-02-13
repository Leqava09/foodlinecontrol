(function() {
    document.addEventListener('DOMContentLoaded', function() {
        const prodInput = document.querySelector('input[id*="production_date"]');
        
        if (!prodInput) {

            return;
        }
        
        function updateExpiryDisplay() {
            const dateStr = prodInput.value;
            
            // Find the parent form-row of production_date input
            const prodRow = prodInput.closest('.form-row') || prodInput.closest('.grp-row');
            if (!prodRow) {

                return;
            }
            
            // Remove old display if exists
            const oldDisplay = prodRow.querySelector('.expiry-date-inline');
            if (oldDisplay) oldDisplay.remove();
            
            if (!dateStr) {
                return;
            }
            
            let date;
            
            // Check if date is in DD-MM-YYYY format
            if (dateStr.match(/^\d{2}-\d{2}-\d{4}$/)) {
                // Parse DD-MM-YYYY
                const parts = dateStr.split('-');
                const day = parseInt(parts[0], 10);
                const month = parseInt(parts[1], 10) - 1; // months are 0-indexed
                const year = parseInt(parts[2], 10);
                date = new Date(year, month, day);
            } 
            // Check if date is in YYYY-MM-DD format
            else if (dateStr.match(/^\d{4}-\d{2}-\d{2}$/)) {
                date = new Date(dateStr + 'T00:00:00');
            }
            else {

                return;
            }
            
            // Check if date is valid
            if (isNaN(date.getTime())) {

                return;
            }
            
            // Add 3 years
            date.setFullYear(date.getFullYear() + 3);
            
            // Format as DD/MM/YYYY
            const formatted = String(date.getDate()).padStart(2, '0') + '/' + 
                            String(date.getMonth() + 1).padStart(2, '0') + '/' + 
                            date.getFullYear();
            
            // Create display and insert RIGHT AFTER production input
            const display = document.createElement('div');
            display.className = 'expiry-date-inline';
            display.innerHTML = `<strong style="color: #417690; display: block; margin-top: 8px;">Expiry Date: ${formatted}</strong>`;
            
            prodInput.parentNode.appendChild(display);
        }
        
        // Update on production date change
        prodInput.addEventListener('change', updateExpiryDisplay);
        prodInput.addEventListener('input', updateExpiryDisplay);
        prodInput.addEventListener('blur', updateExpiryDisplay);
        
        // Initial load
        updateExpiryDisplay();
    });
})();
