/**
 * Booking Out Validation
 * Shows popup warning and red error field if trying to book out more than available stock
 */

document.addEventListener('DOMContentLoaded', function() {

    // Only run on Booking Out (OUT) forms
    const urlParams = new URLSearchParams(window.location.search);
    const transactionType = urlParams.get('transaction_type');

    if (transactionType !== 'OUT') {

        return;
    }
    
    // Get batch_ref from URL
    let batchRef = urlParams.get('batch_ref');

    if (!batchRef) {
        // Try from form field
        const batchRefField = document.querySelector('[name="batch_ref"]');
        if (batchRefField) {
            batchRef = batchRefField.value;

        }
    }
    
    if (!batchRef) {

        return;
    }
    
    // Get the form
    const form = document.querySelector('form');
    if (!form) {

        return;
    }

    // Get quantity input fields
    const kgPerBoxEl = document.getElementById('id_kg_per_box');
    const totalBoxesEl = document.getElementById('id_total_boxes');
    const quantityEl = document.getElementById('id_quantity');
    
    // Create error message container
    const errorContainer = document.createElement('div');
    errorContainer.id = 'booking-out-error';
    errorContainer.style.cssText = 'display:none; padding: 20px; margin: 30px 0; background-color: #ffebee; border: 3px solid #f44336; border-radius: 4px; color: #c62828; font-weight: bold; font-size: 16px; width: 100%; box-sizing: border-box;';
    
    // Insert error container after the Quantity field instead of at top of form
    const quantityRow = quantityEl ? quantityEl.closest('.form-row') || quantityEl.parentElement : null;
    if (quantityRow && quantityRow.parentElement) {
        quantityRow.parentElement.insertBefore(errorContainer, quantityRow.nextSibling);
    } else {
        // Fallback: insert at top of form
        form.insertBefore(errorContainer, form.firstChild);
    }
    
    function validateAndShowError() {
        // Calculate booking out quantity
        let bookingOutQty = 0;
        
        if (kgPerBoxEl && totalBoxesEl && kgPerBoxEl.value && totalBoxesEl.value) {
            bookingOutQty = parseFloat(kgPerBoxEl.value) * parseFloat(totalBoxesEl.value);
        } else if (quantityEl && quantityEl.value) {
            bookingOutQty = parseFloat(quantityEl.value);
        }
        
        // Only proceed if user has entered a quantity
        if (!bookingOutQty || bookingOutQty <= 0) {

            errorContainer.style.display = 'none';
            if (quantityEl) {
                quantityEl.style.borderColor = '';
                quantityEl.style.borderWidth = '';
            }
            return;
        }

        // Fetch available stock for this batch_ref
        fetch(`/inventory/available_stock/?batch_ref=${encodeURIComponent(batchRef)}`)
            .then(response => response.json())
            .then(data => {

                if (data.error) {

                    errorContainer.style.display = 'none';
                    return;
                }
                
                const available = parseFloat(data.available) || 0;

                // ONLY show error if booking out EXCEEDS available
                if (bookingOutQty > available) {

                    const message = `⚠️ BOOKING OUT EXCEEDS AVAILABLE STOCK!<br><br>` +
                        `Booking Out Qty: <strong>${bookingOutQty.toFixed(2)}</strong><br>` +
                        `Available Stock: <strong>${available.toFixed(2)}</strong><br><br>` +
                        `Total IN: ${parseFloat(data.total_in).toFixed(2)}<br>` +
                        `Already OUT: ${parseFloat(data.total_out).toFixed(2)}<br><br>` +
                        `<strong>Please reduce the booking out quantity.</strong>`;
                    
                    errorContainer.innerHTML = message;
                    errorContainer.style.display = 'block';
                    
                    // Highlight the quantity field
                    if (quantityEl) {
                        quantityEl.style.borderColor = '#f44336';
                        quantityEl.style.borderWidth = '2px';
                    }
                } else {
                    // QTY IS CORRECT - NO ERROR

                    errorContainer.style.display = 'none';
                    if (quantityEl) {
                        quantityEl.style.borderColor = '';
                        quantityEl.style.borderWidth = '';
                    }
                }
            })
            .catch(error => {

                errorContainer.style.display = 'none';
            });
    }
    
    // Function to check if save is allowed - returns promise
    function canSave() {
        return new Promise((resolve, reject) => {
            // Calculate booking out quantity
            let bookingOutQty = 0;
            
            if (kgPerBoxEl && totalBoxesEl && kgPerBoxEl.value && totalBoxesEl.value) {
                bookingOutQty = parseFloat(kgPerBoxEl.value) * parseFloat(totalBoxesEl.value);
            } else if (quantityEl && quantityEl.value) {
                bookingOutQty = parseFloat(quantityEl.value);
            }
            
            // If no qty, allow save
            if (!bookingOutQty || bookingOutQty <= 0) {

                resolve(true);
                return;
            }
            
            // Check available stock
            fetch(`/inventory/available_stock/?batch_ref=${encodeURIComponent(batchRef)}`)
                .then(response => response.json())
                .then(data => {
                    const available = parseFloat(data.available) || 0;
                    
                    if (bookingOutQty > available) {

                        resolve(false);
                    } else {

                        resolve(true);
                    }
                })
                .catch(error => {

                    resolve(true); // Allow save on error
                });
        });
    }
    
    // Listen to quantity changes
    if (kgPerBoxEl) {
        kgPerBoxEl.addEventListener('input', function() {
            // Hide error immediately when user starts typing
            errorContainer.style.display = 'none';
            if (quantityEl) {
                quantityEl.style.borderColor = '';
                quantityEl.style.borderWidth = '';
            }
            // Then validate after a short delay
            setTimeout(validateAndShowError, 300);
        });
        kgPerBoxEl.addEventListener('change', validateAndShowError);
        kgPerBoxEl.addEventListener('blur', validateAndShowError);
    }
    
    if (totalBoxesEl) {
        totalBoxesEl.addEventListener('input', function() {
            // Hide error immediately when user starts typing
            errorContainer.style.display = 'none';
            if (quantityEl) {
                quantityEl.style.borderColor = '';
                quantityEl.style.borderWidth = '';
            }
            // Then validate after a short delay
            setTimeout(validateAndShowError, 300);
        });
        totalBoxesEl.addEventListener('change', validateAndShowError);
        totalBoxesEl.addEventListener('blur', validateAndShowError);
    }
    
    if (quantityEl) {
        quantityEl.addEventListener('input', function() {
            // Hide error immediately when user starts typing
            errorContainer.style.display = 'none';
            if (quantityEl) {
                quantityEl.style.borderColor = '';
                quantityEl.style.borderWidth = '';
            }
            // Then validate after a short delay
            setTimeout(validateAndShowError, 300);
        });
        quantityEl.addEventListener('change', validateAndShowError);
        quantityEl.addEventListener('blur', validateAndShowError);
    }
    
    // Listen for form submission - validate and block if needed
    form.addEventListener('submit', function(e) {

        e.preventDefault();
        
        canSave().then(allowed => {
            if (allowed) {

                // Remove this listener and submit
                form.removeEventListener('submit', arguments.callee);
                form.submit();
            } else {

                alert('❌ CANNOT SAVE\n\nBooking out quantity exceeds available stock.\n\nPlease reduce the quantity before saving.');
                
                // Show the error box
                validateAndShowError();
            }
        });
        
        return false;
    }, true);
    
    // Initial validation
    validateAndShowError();
});

