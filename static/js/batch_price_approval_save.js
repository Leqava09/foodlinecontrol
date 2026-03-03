/**
 * Batch Price Approval Auto-Save via AJAX - WITH SELLING PRICE DEFAULT
 * Only runs on the change/edit view (form page), not on list view
 */

(function() {

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    function getCsrfToken() {
        // Try 1: Get from cookie
        let token = getCookie('csrftoken');
        if (token) return token;
        
        // Try 2: Get from meta tag (Django default)
        const metaTag = document.querySelector('[name=csrfmiddlewaretoken]');
        if (metaTag) return metaTag.value;
        
        // Try 3: Get from input field in form
        const inputField = document.querySelector('[name=csrfmiddlewaretoken]');
        if (inputField) return inputField.value;
        
        console.warn('CSRF token not found');
        return '';
    }

    let pendingRequests = new Set();
    let recentlySaved = new Set();
    
    let savedValues = {};
    const STORAGE_KEY = 'batch_approval_saved_values';
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
            savedValues = JSON.parse(stored);

        }
    } catch (e) {

    }
    
    function persistSavedValues() {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(savedValues));

        } catch (e) {

        }
    }

    function saveApproval(element) {
        const id = element.dataset.approvalId;
        if (!id) {
            console.warn('No approval ID found on element', element);
            return;
        }

        if (recentlySaved.has(id)) {
            console.log('Recently saved, skipping:', id);
            return;
        }

        const payload = new FormData();
        let savedValue = null;
        let fieldType = null;

        if (element.classList.contains('batch-price-input')) {
            let raw = element.value || '';
            let num = parseFloat(raw.replace(/\s/g, '').replace(',', '.')) || 0;
            const price = num.toFixed(2);
            savedValue = price;
            fieldType = 'price';
            payload.append('batch_price_per_unit', price);
            console.log('Saving price:', { id, price, fieldType });

        } 
        else if (element.classList.contains('batch-approval-checkbox')) {
            const approved = element.checked;
            savedValue = approved;
            fieldType = 'checkbox';
            payload.append('is_approved', approved ? 'true' : 'false');
            console.log('Saving checkbox:', { id, approved, fieldType });

        } 
        else {
            console.warn('Unknown element type', element);
            return;
        }

        const storageKey = `${fieldType}_${id}`;
        savedValues[storageKey] = savedValue;
        persistSavedValues();

        const url = `/costing/admin/batch-price-approval/${id}/update/`;
        const csrfToken = getCsrfToken();
        const requestId = `approval-${id}-${fieldType}-${Date.now()}`;
        
        console.log('AJAX Request:', { url, csrfToken: csrfToken ? 'present' : 'MISSING', requestId });
        
        pendingRequests.add(requestId);
        recentlySaved.add(id);

        fetch(url, {
            method: 'POST',
            body: payload,
            headers: {
                'X-CSRFToken': csrfToken
            },
            credentials: 'same-origin'
        })
        .then(response => {
            console.log('Response received:', { status: response.status, requestId });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return response.json();
        })
        .then(data => {
            console.log('Save successful:', { data, requestId, id, fieldType });
            if (fieldType === 'price') {
                element.style.borderColor = '#4caf50';
                element.style.boxShadow = '0 0 5px #4caf50';
                setTimeout(() => {
                    element.style.borderColor = '#ccc';
                    element.style.boxShadow = 'none';
                }, 800);
            }
        })
        .catch(error => {
            console.error('❌ Save approval FAILED:', {
                error: error.message,
                approval_id: id,
                field_type: fieldType,
                url: url,
                requestId: requestId,
                stack: error.stack
            });
        })
        .finally(() => {
            pendingRequests.delete(requestId);
            setTimeout(() => recentlySaved.delete(id), 500);
        });
    }

    function attachListeners(priceInputs, checkboxes) {
        priceInputs.forEach((input, idx) => {
            const id = input.dataset.approvalId;
            const storageKey = `price_${id}`;
            
            if (savedValues[storageKey] !== undefined) {
                const num = parseFloat(savedValues[storageKey]);
                input.value = isNaN(num) ? '' : num.toFixed(2);

            }
            
            input.dataset.listener = 'true';
            input.addEventListener('blur', function() { saveApproval(this); });
            input.addEventListener('keyup', function(e) {
                if (e.key === 'Enter') saveApproval(this);
            });
        });

        checkboxes.forEach((cb, idx) => {
            const id = cb.dataset.approvalId;
            const storageKey = `checkbox_${id}`;
            
            if (savedValues[storageKey] === true) {
                cb.checked = true;

            } else if (savedValues[storageKey] === false) {
                cb.checked = false;
            }
            
            cb.dataset.listener = 'true';
            cb.addEventListener('change', function() { saveApproval(this); });
        });
    }

    document.addEventListener('DOMContentLoaded', function() {
        // ✅ CHECK: Only run on change view (form page)
        const priceInputs = document.querySelectorAll('.batch-price-input');
        
        if (priceInputs.length === 0) {
            return;
        }

        const checkboxes = document.querySelectorAll('.batch-approval-checkbox');

        attachListeners(priceInputs, checkboxes);

        // MutationObserver for dynamic elements
        if (document.body) {
            const observer = new MutationObserver(function(mutations) {
                mutations.forEach(function(mutation) {
                    if (mutation.addedNodes.length) {
                        const newInputs = document.querySelectorAll('.batch-price-input:not([data-listener])');
                        const newChecks = document.querySelectorAll('.batch-approval-checkbox:not([data-listener])');
                        if (newInputs.length > 0 || newChecks.length > 0) {

                            attachListeners(newInputs, newChecks);
                        }
                    }
                });
            });
            observer.observe(document.body, { childList: true, subtree: true });
        }

        // Form submission handler
        setTimeout(function() {
            const form = document.querySelector('form');
            if (!form) return;

            let submitting = false;
            form.addEventListener('submit', function(e) {
                if (submitting || form.dataset.ajaxDone === 'true') {
                    form.dataset.ajaxDone = '';
                    return;
                }

                e.preventDefault();
                submitting = true;

                if (pendingRequests.size === 0) {
                    form.dataset.ajaxDone = 'true';
                    form.submit();
                    return;
                }

                let waitTime = 0;
                const checkInterval = setInterval(function() {
                    waitTime += 50;
                    if (pendingRequests.size === 0 || waitTime > 2000) {
                        clearInterval(checkInterval);
                        form.dataset.ajaxDone = 'true';
                        form.submit();
                    }
                }, 50);
                
                return false;
            }, true);
        }, 500);
    });

})();

// ============ POPULATE PRICE INPUTS WITH SELLING PRICE ============
document.addEventListener('DOMContentLoaded', function() {
    // ✅ CHECK: Only run on change view (form page)
    const sellingPriceField = document.getElementById('id_price');
    if (!sellingPriceField) {
        return; // Not on change view, skip silently
    }
    
    setTimeout(function() {

        const currentSellingPrice = parseFloat(sellingPriceField.value) || 0;
        
        const allPriceInputs = document.querySelectorAll('.batch-price-input');

        allPriceInputs.forEach((input, idx) => {
            const currentVal = parseFloat(input.value) || 0;
            const id = input.dataset.approvalId;
            
            if (currentVal === 0 || input.value === '') {
                input.value = currentSellingPrice.toFixed(2);
            } else {
            }
        });

    }, 800);
});
