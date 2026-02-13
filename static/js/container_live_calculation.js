/**
 * Live Total Amount Calculation for Container & StockTransaction
 * Calculates: Total Amount = kg/Box (kg_per_box) × Total Amount of Boxes (total_boxes)
 */

(function() {
    'use strict';

    /**
     * Main calculation function - works for both Container and StockTransaction
     */
    function setupLiveCalculation() {
        // Use Django admin field ID convention: id_fieldname
        const kgPerBoxInput = document.getElementById('id_kg_per_box');
        const totalBoxesInput = document.getElementById('id_total_boxes');
        
        // For Container: display in readonly total_weight_container
        // For StockTransaction: display in editable booking_in_total_qty
        const totalAmountInput = document.getElementById('id_booking_in_total_qty') || 
                                 document.getElementById('id_total_weight_container');

        if (!kgPerBoxInput || !totalBoxesInput) {

            return;
        }

        /**
         * Performs the actual calculation
         */
        function calculateAndUpdate() {
            const kgPerBox = parseFloat(kgPerBoxInput.value) || 0;
            const totalBoxes = parseInt(totalBoxesInput.value) || 0;
            const result = (kgPerBox * totalBoxes).toFixed(2);

            if (totalAmountInput) {
                totalAmountInput.value = result;

            }
        }

        // Attach listeners to both fields - multiple events for responsiveness
        kgPerBoxInput.addEventListener('input', calculateAndUpdate);
        kgPerBoxInput.addEventListener('change', calculateAndUpdate);
        kgPerBoxInput.addEventListener('blur', calculateAndUpdate);

        totalBoxesInput.addEventListener('input', calculateAndUpdate);
        totalBoxesInput.addEventListener('change', calculateAndUpdate);
        totalBoxesInput.addEventListener('blur', calculateAndUpdate);

        // Initial calculation
        calculateAndUpdate();
    }

    // Wait for DOM to be fully loaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupLiveCalculation);
    } else {
        setupLiveCalculation();
    }

    // Also try setup after a short delay to catch dynamically loaded content
    setTimeout(setupLiveCalculation, 500);
})();
