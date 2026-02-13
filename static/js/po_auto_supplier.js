/**
 * Auto-populate Supplier field from first PO line item
 * Watches for changes in the first line item's sub_category and updates supplier accordingly
 */

(function() {
    'use strict';

    function updateSupplierFromFirstLineItem() {
        // Get the first line item's sub_category select (line 0)
        var $firstSubCategory = $('select[name="line_items-0-sub_category"]');
        if (!$firstSubCategory.length) {
            console.log('po_auto_supplier.js: First line item sub_category not found');
            return; // First line item doesn't have a sub_category select yet
        }

        var subCategoryId = $firstSubCategory.val();
        console.log('po_auto_supplier.js: First line item sub_category value:', subCategoryId);
        
        if (!subCategoryId) {
            console.log('po_auto_supplier.js: No sub_category selected');
            return; // No sub_category selected
        }

        // Get the supplier select
        var $supplierSelect = $('select[name="supplier"]');
        if (!$supplierSelect.length) {
            console.log('po_auto_supplier.js: Supplier select not found');
            return;
        }

        // Extract site ID from URL (e.g., /hq/Test/admin/ or /hq/1/admin/...)
        var urlMatch = window.location.pathname.match(/\/hq\/([a-zA-Z0-9_-]+)\//);
        var siteId = urlMatch ? urlMatch[1] : null;
        var sitePath = siteId ? `/hq/${siteId}` : '';
        console.log('po_auto_supplier.js: Extracted site_id from URL:', siteId, 'sitePath:', sitePath);

        // Fetch suppliers matching this sub_category
        var url = sitePath + '/admin/inventory/purchaseorder/get-suppliers-by-subcategory/';
        var currentValue = $supplierSelect.val();
        
        // Build AJAX data
        var ajaxData = { sub_category_id: subCategoryId };
        if (siteId) {
            ajaxData.site_id = siteId;
            console.log('po_auto_supplier.js: Adding site_id to AJAX data:', siteId);
        }

        console.log('po_auto_supplier.js: Calling API:', url, 'with data:', ajaxData);

        $.ajax({
            url: url,
            data: ajaxData,
            dataType: 'json',
            success: function(data) {
                console.log('po_auto_supplier.js: API response:', data);
                if (data.suppliers && data.suppliers.length > 0) {
                    // Auto-select the first supplier if none is currently selected
                    if (!currentValue || currentValue === '') {
                        $supplierSelect.val(data.suppliers[0].id);
                        $supplierSelect.trigger('change');
                        console.log('po_auto_supplier.js: Auto-selected supplier:', data.suppliers[0].name);
                    }
                } else {
                    console.log('po_auto_supplier.js: No suppliers returned from API');
                }
            },
            error: function(xhr, status, error) {
                console.log('po_auto_supplier.js: Error fetching suppliers:', status, error, xhr.responseText);
            }
        });
    }

    // Initialize on page load
    $(document).ready(function() {
        console.log('po_auto_supplier.js: Document ready, initializing supplier auto-population');
        
        // Listen for changes on first line item's sub_category
        $(document).on('change', 'select[name="line_items-0-sub_category"]', function() {
            console.log('po_auto_supplier.js: First line item sub_category changed');
            // Small delay to ensure the change is fully processed
            setTimeout(updateSupplierFromFirstLineItem, 100);
        });

        // Also try to populate supplier on initial load if form already has data
        setTimeout(updateSupplierFromFirstLineItem, 500);
    });
})();
