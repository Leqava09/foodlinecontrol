(function() {
    var updatedCells = {};
    
    /**
     * Fetch batch data and update cells
     */
    var fetchAndUpdate = function(dateText, cellsToUpdate) {
        if (!dateText || cellsToUpdate.length === 0) return;
        
        // Convert DD/MM/YYYY to YYYY-MM-DD
        var parts = dateText.split('/');
        if (parts.length !== 3) return;
        var isoDate = parts[2] + '-' + parts[1] + '-' + parts[0];

        fetch('/manufacturing/api/batch-date/?production_date=' + encodeURIComponent(isoDate))
            .then(function(response) { return response.json(); })
            .then(function(data) {

                if (data.success && data.batch_number) {
                    cellsToUpdate.forEach(function(cell, idx) {
                        // Cycle through batches if multiple
                        var batchNum = data.batches && data.batches[idx % data.batches.length]
                            ? data.batches[idx % data.batches.length].batch_number
                            : data.batch_number;
                        
                        cell.innerText = batchNum;
                        cell.style.fontWeight = 'bold';
                        cell.style.color = '#ff6f00';
                        cell.style.backgroundColor = '#fffde7';

                    });
                }
            })
            .catch(function(error) {

            });
    };
    
    /**
     * Scan for Production Out rows and update batch cells
     * Cell structure: [Date] [Batch Cell] [Production Out] [QTY] ...
     * So batch cell is 1 position BEFORE Production Out
     */
    var scanAndUpdate = function() {
        var allCells = document.querySelectorAll('td');
        var cellsByDate = {};
        
        for (var i = 0; i < allCells.length; i++) {
            var cell = allCells[i];
            var text = cell.innerText.trim();
            
            // Look for "Production Out" cells
            if (text.includes('Production Out')) {
                // Date is 2 cells before Production Out
                var dateCell = null;
                if (i >= 2) {
                    var dateCandidate = allCells[i - 2].innerText.trim();
                    if (dateCandidate.match(/^\d{2}\/\d{2}\/\d{4}$/)) {
                        dateCell = dateCandidate;
                    }
                }
                
                if (dateCell) {
                    // Batch cell is 1 cell BEFORE Production Out
                    var batchCell = allCells[i - 1];
                    
                    if (batchCell && (batchCell.innerText.trim() === '-' || batchCell.innerText.trim() === '')) {
                        // Create unique key for this cell
                        var cellKey = 'cell_' + i;
                        
                        if (!updatedCells[cellKey]) {
                            updatedCells[cellKey] = true;
                            
                            if (!cellsByDate[dateCell]) {
                                cellsByDate[dateCell] = [];
                            }
                            cellsByDate[dateCell].push(batchCell);

                        }
                    }
                }
            }
        }
        
        // Fetch and update for each date
        Object.keys(cellsByDate).forEach(function(dateText) {
            fetchAndUpdate(dateText, cellsByDate[dateText]);
        });
    };
    
    /**
     * Start polling every 500ms
     */
    var startPolling = function() {

        scanAndUpdate();
        
        setInterval(function() {
            scanAndUpdate();
        }, 500);
    };
    
    // Initialize on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', startPolling);
    } else {
        startPolling();
    }
    
})();
