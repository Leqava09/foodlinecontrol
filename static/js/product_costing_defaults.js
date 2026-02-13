/**
 * ProductCosting Default Change Confirmation
 * 
 * When a user changes the overhead or salary costing selection on an existing
 * ProductCosting record, this script shows a confirmation dialog asking whether
 * to update the snapshot values to the new default or keep the current ones.
 */
(function() {
    document.addEventListener('DOMContentLoaded', function() {
        const form = document.getElementById('productcosting_form');
        if (!form) return;
        
        const overheadField = document.getElementById('id_overhead_costing');
        const salaryField = document.getElementById('id_salary_costing');
        
        if (!overheadField && !salaryField) return;
        
        // Get original values from server-injected globals
        const originalOverheadId = window.ORIGINAL_OVERHEAD_COSTING_ID || '';
        const originalSalaryId = window.ORIGINAL_SALARY_COSTING_ID || '';
        const currentOverheadSnapshot = window.OVERHEAD_SNAPSHOT || 0;
        const currentSalarySnapshot = window.SALARY_SNAPSHOT || 0;
        
        // Track if defaults have changed
        let overheadChanged = false;
        let salaryChanged = false;
        let userConfirmedUpdate = false;
        
        // Create hidden field to communicate with server
        let hiddenField = document.getElementById('update_costing_snapshots');
        if (!hiddenField) {
            hiddenField = document.createElement('input');
            hiddenField.type = 'hidden';
            hiddenField.name = 'update_costing_snapshots';
            hiddenField.id = 'update_costing_snapshots';
            hiddenField.value = 'false';
            form.appendChild(hiddenField);
        }
        
        // Monitor overhead changes
        if (overheadField) {
            overheadField.addEventListener('change', function() {
                const currentVal = this.value;
                if (originalOverheadId && currentVal !== originalOverheadId) {
                    overheadChanged = true;
                } else {
                    overheadChanged = false;
                }
            });
        }
        
        // Monitor salary changes
        if (salaryField) {
            salaryField.addEventListener('change', function() {
                const currentVal = this.value;
                if (originalSalaryId && currentVal !== originalSalaryId) {
                    salaryChanged = true;
                } else {
                    salaryChanged = false;
                }
            });
        }
        
        // Intercept form submission
        form.addEventListener('submit', function(e) {
            // Only show popup if overhead or salary has changed AND this is an edit (not new record)
            if ((overheadChanged || salaryChanged) && (originalOverheadId || originalSalaryId)) {
                // Build message for user
                let changedItems = [];
                if (overheadChanged) {
                    changedItems.push('Overhead Costing');
                }
                if (salaryChanged) {
                    changedItems.push('Salary Costing');
                }
                
                const message = `You have changed the ${changedItems.join(' and ')}.\n\n` +
                    `Do you want to UPDATE the snapshot price values to the new default?\n\n` +
                    `• Click "OK" to use the NEW default values going forward\n` +
                    `• Click "Cancel" to keep the CURRENT snapshot values\n\n` +
                    `Note: This only affects the stored price per unit snapshots for this record.`;
                
                userConfirmedUpdate = confirm(message);
                hiddenField.value = userConfirmedUpdate ? 'true' : 'false';
            }
            
            // Allow form to submit
            return true;
        });
        
        // For new records (no original IDs), automatically set defaults
        if (!originalOverheadId && !originalSalaryId) {
            // New record - let Django's get_changeform_initial_data handle defaults
            // Snapshots will be captured automatically on first save
        }
    });
})();
