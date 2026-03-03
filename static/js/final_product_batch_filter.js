(function($) {
    $(function() {
        var $prodDateField = $('#id_production_date');
        var $batchField = $('#id_batch');
        
        if (!$prodDateField.length || !$batchField.length) {
            return;
        }
        
        // Store original batch options
        var originalOptions = $batchField.find('option').clone();
        
        // Function to fetch and update batches for selected production date
        function updateBatchesForDate() {
            var prodDate = $prodDateField.val();
            
            if (!prodDate) {
                // No date selected - show empty
                $batchField.empty().append(
                    $('<option value="">---------</option>')
                );
                return;
            }
            
            // Convert date from DD-MM-YYYY or DD.MM.YYYY to YYYY-MM-DD format
            var formattedDate = prodDate;
            
            // Check if it's in DD-MM-YYYY or DD.MM.YYYY format (dashes or dots)
            if (prodDate.includes('-') || prodDate.includes('.')) {
                var separator = prodDate.includes('-') ? '-' : '.';
                var parts = prodDate.split(separator);
                if (parts.length === 3 && parts[0].length === 2) {
                    // DD-MM-YYYY or DD.MM.YYYY format
                    formattedDate = parts[2] + '-' + parts[1] + '-' + parts[0]; // YYYY-MM-DD
                } else if (parts.length === 3 && parts[0].length === 4) {
                    // Already YYYY-MM-DD format
                    formattedDate = prodDate;
                }
            }
            
            console.log('Fetching batches for date:', formattedDate);
            
            // Fetch batches for this date
            $.ajax({
                url: '/inventory/api/batches-for-date/',
                data: {production_date: formattedDate},
                dataType: 'json',
                success: function(data) {
                    var batches = data.batches || [];
                    var currentSelection = $batchField.val();
                    
                    console.log('API Response:', data);
                    console.log('Batches received:', batches);
                    console.log('Batch count:', batches.length);
                    
                    // Rebuild dropdown with only batches for this date
                    $batchField.empty().append(
                        $('<option value="">---------</option>')
                    );
                    
                    if (batches.length === 0) {
                        $batchField.append(
                            $('<option disabled></option>')
                                .text('No batches for this date')
                        );
                    } else {
                        batches.forEach(function(batch) {
                            $batchField.append(
                                $('<option></option>')
                                    .attr('value', batch.id)
                                    .text(batch.number)
                            );
                        });
                    }
                    
                    // Restore previous selection if it still exists
                    if (currentSelection) {
                        $batchField.val(currentSelection);
                    }
                },
                error: function(xhr, status, error) {
                    console.error('Error fetching batches:', error);
                    $batchField.empty().append(
                        $('<option value="">Error loading batches</option>')
                    );
                }
            });
        }
        
        // Update batches when production_date changes
        $prodDateField.on('change', updateBatchesForDate);
        
        // Trigger on page load if production_date is already set
        if ($prodDateField.val()) {
            updateBatchesForDate();
        }
    });
})(jQuery);
