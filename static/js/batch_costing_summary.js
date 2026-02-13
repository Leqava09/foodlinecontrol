/**
 * Batch Costing Summary Importer - Extended for Meat, Sauce, Packaging
 * WITH COSTING COLUMNS: Ideal Costing, Used Costing, Price per Unit, QUOTED
 * ✅ Only runs on change/edit view (form page)
 */
(function() {
    // Get currency from company settings (injected by Django), fallback to 'R'
    // Called dynamically each time to ensure window.COMPANY_CURRENCY is available
    function getCurrency() {
        return window.COMPANY_CURRENCY || 'R';
    }

    document.addEventListener('DOMContentLoaded', function() {
        console.log('=== BATCH COSTING SUMMARY JS LOADED ===');
        
        // ✅ Check if we're on the change form (not changelist)
        const container = document.getElementById('summary-items-container');
        if (!container) {
            console.log('No summary-items-container found, exiting');
            return;  // Exit if not on form page
        }

        console.log('Summary items container found');

        // ✅ Get production_date ID from the page URL
        // URL format: /admin/costing/batchcosting/{id}/change/
        const urlMatch = window.location.pathname.match(/\/batchcosting\/(\d+)\//);
        if (!urlMatch) {
            console.log('Not on edit page, exiting');
            return;
        }

        const batchCostingId = urlMatch[1];
        console.log('BatchCosting ID:', batchCostingId);

        // ✅ Get production_date from the BatchCosting object (injected by Django)
        // Or extract from data attribute on container
        let productionId = container.getAttribute('data-production-id');
        
        if (!productionId) {
            console.log('No production ID found in container data attribute');
            // Try to get from window object (if Django injected it)
            productionId = window.PRODUCTION_DATE_ID;
        }

        if (productionId) {
            console.log('Production ID found:', productionId);
            fetchAndImportSummaryData(productionId);
        } else {
            console.log('⚠ No production ID available, cannot load summary');
            container.innerHTML = '<p style="color: #d32f2f; padding: 10px;">Production date not set</p>';
        }
    });

    function fetchAndImportSummaryData(productionId) {
        if (!productionId) {
            const container = document.getElementById('summary-items-container');
            if (container) {
                container.innerHTML = '<p style="color: #999; padding: 10px;">Please select a production date</p>';
            }
            return;
        }

        const apiUrl = `/costing/api/batch-summary-items/${productionId}/`;
        
        console.log('Fetching batch summary from:', apiUrl, 'Production ID:', productionId);

        fetch(apiUrl)
            .then(response => {
                if (!response.ok) {
                    return response.text().then(text => {
                        throw new Error(`HTTP ${response.status}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                if (data.items && data.items.length > 0) {
                    importSummaryItems(data.items, data.total_batch_units);
                } else {
                    const container = document.getElementById('summary-items-container');
                    if (container) {
                        container.innerHTML = '<p style="color: #999; padding: 10px;">No data available</p>';
                    }
                }
            })
            .catch(error => {
                console.error('Error loading summary items:', error);
                const container = document.getElementById('summary-items-container');
                if (container) {
                    container.innerHTML = '<p style="color: #d32f2f; padding: 10px;">Error loading data: ' + error.message + '</p>';
                }
            });
    }

    function importSummaryItems(itemsList, totalBatchUnits) {

        if (!itemsList || itemsList.length === 0) return;

        const sections = { meat: [], sauce: [], packaging: [] };
        itemsList.forEach(item => {
            const section = item.section || 'meat';
            if (sections[section]) sections[section].push(item);
        });

        const allItems = [...sections.meat, ...sections.sauce, ...sections.packaging];
        let rows = [];

        const itemGroups = {};
        allItems.forEach(item => {
            const key = item.item_name || 'unknown';
            if (!itemGroups[key]) itemGroups[key] = [];
            itemGroups[key].push(item);
        });

        // Build rows
        Object.keys(itemGroups).forEach(itemName => {
            const group = itemGroups[itemName];
            if (!group || group.length === 0) return;

            const first = group[0];
            const unit = first.unit || '';
            const ideal = parseFloat(first.ideal) || 0;
            const idealCosting = parseFloat(first.ideal_costing) || 0;
            const firstUsed = parseFloat(first.used) || 0;
            const firstUsedCosting = parseFloat(first.used_costing) || 0;
            const quotedValue = parseFloat(first.quoted) || 0;
            const pricePerUnit = parseFloat(first.price_per_unit) || 0;
            const firstBatchRef = first.batch_ref || '-';
            const cur = getCurrency();

            // First row
            let firstRow = '<tr>';
            firstRow += `<td style="border: 1px solid #ddd; padding: 10px; text-align: left; width: 200px; font-size: 12px;" rowspan="${group.length}">${itemName}</td>`;
            firstRow += `<td style="border: 1px solid #ddd; padding: 10px; text-align: center; width: 60px; font-size: 12px;" rowspan="${group.length}">${unit}</td>`;
            firstRow += `<td style="border: 1px solid #ddd; padding: 10px; text-align: right; background-color: #c3e7f7; width: 90px; font-size: 12px;" rowspan="${group.length}"><strong>${ideal.toFixed(2)}</strong></td>`;
            firstRow += `<td style="border: 1px solid #ddd; padding: 10px; text-align: right; background-color: #c3e7f7; width: 135px; font-size: 12px;" rowspan="${group.length}"><strong>${cur} ${idealCosting.toFixed(2)}</strong></td>`;
            firstRow += `<td style="border: 1px solid #ddd; padding: 8px; text-align: right; background-color: #c8e6c9; width: 90px; font-size: 12px;"><strong>${firstUsed.toFixed(2)}</strong></td>`;
            firstRow += `<td style="border: 1px solid #ddd; padding: 8px; text-align: right; background-color: #c8e6c9; width: 135px; font-size: 12px;"><strong>${cur} ${firstUsedCosting.toFixed(2)}</strong></td>`;
            firstRow += `<td style="border: 1px solid #ddd; padding: 8px; text-align: right; background-color: #fffacd; width: 135px; font-size: 12px;" rowspan="${group.length}"><strong>${cur} ${quotedValue.toFixed(2)}</strong></td>`;
            firstRow += `<td style="border: 1px solid #ddd; padding: 8px; text-align: right; width: 80px; font-size: 11px;">${pricePerUnit.toFixed(4)}</td>`;
            firstRow += `<td style="border: 1px solid #ddd; padding: 8px; text-align: left; color: #666; width: 200px; font-size: 11px;">${firstBatchRef}</td>`;
            firstRow += '</tr>';
            rows.push(firstRow);

            // Detail rows
            for (let i = 1; i < group.length; i++) {
                const g = group[i];
                const used = parseFloat(g.used) || 0;
                const usedCosting = parseFloat(g.used_costing) || 0;
                const batchRef = g.batch_ref || '-';
                const containerPrice = parseFloat(g.price_per_unit) || 0;

                let detailRow = '<tr>';
                detailRow += `<td style="border: 1px solid #ddd; padding: 8px; text-align: right; background-color: #c8e6c9; width: 90px; font-size: 12px;">${used.toFixed(2)}</td>`;
                detailRow += `<td style="border: 1px solid #ddd; padding: 8px; text-align: right; background-color: #c8e6c9; width: 135px; font-size: 12px;">${cur} ${usedCosting.toFixed(2)}</td>`;
                detailRow += `<td style="border: 1px solid #ddd; padding: 8px; text-align: right; width: 80px; font-size: 11px;">${containerPrice.toFixed(4)}</td>`;
                detailRow += `<td style="border: 1px solid #ddd; padding: 8px; text-align: left; color: #666; width: 200px; font-size: 11px;">${batchRef}</td>`;
                detailRow += '</tr>';
                rows.push(detailRow);
            }

        });

        // Calculate totals
        let totalIdealCosting = 0, totalUsedCosting = 0, totalQuoted = 0;
        Object.keys(itemGroups).forEach(itemName => {
            const group = itemGroups[itemName];
            if (!group) return;
            const first = group[0];
            totalIdealCosting += parseFloat(first.ideal_costing) || 0;
            totalQuoted += parseFloat(first.quoted) || 0;
            group.forEach(item => {
                totalUsedCosting += parseFloat(item.used_costing) || 0;
            });
        });

        // Separator
        rows.push('<tr style="background-color: #ffffff; height: 8px;"><td colspan="9" style="border: none; padding: 0;"></td></tr>');

        // Get currency at render time (after Django has set window.COMPANY_CURRENCY)
        const cur = getCurrency();

        // Totals row
        rows.push(`<tr style="background-color: #4a7c8c; color: white; font-weight: bold;">
            <td style="border: 1px solid #ddd; padding: 12px;">TOTALS</td>
            <td style="border: 1px solid #ddd; padding: 12px;"></td>
            <td style="border: 1px solid #ddd; padding: 12px;"></td>
            <td style="border: 1px solid #ddd; padding: 12px; text-align: right;">${cur} ${totalIdealCosting.toFixed(2)}</td>
            <td style="border: 1px solid #ddd; padding: 12px;"></td>
            <td style="border: 1px solid #ddd; padding: 12px; text-align: right;">${cur} ${totalUsedCosting.toFixed(2)}</td>
            <td style="border: 1px solid #ddd; padding: 12px; text-align: right;">${cur} ${totalQuoted.toFixed(2)}</td>
            <td colspan="2" style="border: 1px solid #ddd; padding: 12px;"></td>
        </tr>`);

        // Price per unit
        const ppu_ideal = totalBatchUnits > 0 ? (totalIdealCosting / totalBatchUnits) : 0;
        const ppu_used = totalBatchUnits > 0 ? (totalUsedCosting / totalBatchUnits) : 0;
        const ppu_quoted = totalBatchUnits > 0 ? (totalQuoted / totalBatchUnits) : 0;

        rows.push(`<tr style="background-color: #4a7c8c; color: white; font-weight: bold;">
            <td style="border: 1px solid #ddd; padding: 12px;">PRICE / UNIT</td>
            <td style="border: 1px solid #ddd; padding: 12px;"></td>
            <td style="border: 1px solid #ddd; padding: 12px;"></td>
            <td style="border: 1px solid #ddd; padding: 12px; text-align: right;">${cur} ${ppu_ideal.toFixed(2)}</td>
            <td style="border: 1px solid #ddd; padding: 12px;"></td>
            <td style="border: 1px solid #ddd; padding: 12px; text-align: right;">${cur} ${ppu_used.toFixed(2)}</td>
            <td style="border: 1px solid #ddd; padding: 12px; text-align: right;">${cur} ${ppu_quoted.toFixed(2)}</td>
            <td colspan="2" style="border: 1px solid #ddd; padding: 12px;"></td>
        </tr>`);

        // Render table
        const html = `<table style="width: 100%; border-collapse: collapse; font-size: 13px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <thead>
                <tr style="background-color: #4a7c8c; color: white; font-weight: bold;">
                    <th style="border: 1px solid #ddd; padding: 12px; text-align: center;">ITEM</th>
                    <th style="border: 1px solid #ddd; padding: 12px; text-align: center;">UNIT</th>
                    <th style="border: 1px solid #ddd; padding: 12px; text-align: center;">IDEAL</th>
                    <th style="border: 1px solid #ddd; padding: 12px; text-align: center;">IDEAL COSTING</th>
                    <th style="border: 1px solid #ddd; padding: 12px; text-align: center;">USED</th>
                    <th style="border: 1px solid #ddd; padding: 12px; text-align: center;">USED COSTING</th>
                    <th style="border: 1px solid #ddd; padding: 12px; text-align: center;">QUOTED</th>
                    <th style="border: 1px solid #ddd; padding: 12px; text-align: center;">PRICE / UNIT</th>
                    <th style="border: 1px solid #ddd; padding: 12px; text-align: center;">BATCH REF</th>
                </tr>
            </thead>
            <tbody>${rows.join('')}</tbody>
        </table>
        `;

        const container = document.getElementById('summary-items-container');
        if (container) {
            container.innerHTML = html;

        }
    }

    // Debug functions
    window.debugBatchSummaryAPI = function(productionDate) {
        const apiUrl = `/costing/api/batch-summary-items/${productionDate}/`;

        fetch(apiUrl)
            .then(r => r.json())
            .then(data => {
                console.group('API Response');

                console.table(data.items);
                console.groupEnd();
            })
            .catch(() => {});
    };

    window.reimportBatchSummary = function() {
        const field = document.querySelector('select[name="production_date"], input[name="production_date"]');
        if (field && field.value) {

            fetchAndImportSummaryData(field.value);
        }
    };
})();
