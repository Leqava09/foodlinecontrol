(function($) {
    'use strict';
    
    $(document).ready(function() {
        console.log('=== PO INLINE MOVE JS LOADED ===');
        
        // Debug: Log ALL form fields to understand the naming
        setTimeout(function() {
            console.log('=== DEBUG: All form field names ===');
            $('select').each(function() {
                var name = $(this).attr('name');
                if (name && (name.indexOf('category') > -1 || name.indexOf('supplier') > -1 || name.indexOf('stock') > -1)) {
                    console.log('Select:', name, 'Value:', $(this).val());
                }
            });
            $('input').each(function() {
                var name = $(this).attr('name');
                if (name && (name.indexOf('quantity') > -1 || name.indexOf('price') > -1)) {
                    console.log('Input:', name, 'Value:', $(this).val());
                }
            });
        }, 2000);
        
        // Find the inline group - Grappelli wraps inlines in div.grp-group
        var $inline = null;
        
        // Try by ID first
        $inline = $('#purchaseorderlineitem_set-group');
        console.log('Try #purchaseorderlineitem_set-group:', $inline.length);
        
        // Try finding by h2 text
        if (!$inline.length) {
            $('div.grp-group').each(function() {
                var headerText = $(this).find('h2').first().text();
                console.log('Found grp-group with header:', headerText);
                if (headerText.indexOf('PO Line Items') > -1 || headerText.indexOf('Line Item') > -1) {
                    $inline = $(this);
                    return false;
                }
            });
        }
        
        // Try any inline with purchaseorderlineitem in ID
        if (!$inline.length) {
            $inline = $('[id*="purchaseorderlineitem"]').closest('.grp-group');
            console.log('Try [id*=purchaseorderlineitem]:', $inline.length);
        }
        
        console.log('Final inline found:', $inline.length);
        
        // Find the Supplier fieldset
        var $targetFieldset = null;
        var fieldsets = $('fieldset.grp-module');
        console.log('Total fieldsets:', fieldsets.length);
        
        fieldsets.each(function(i) {
            var headerText = $(this).find('h2').first().text();
            console.log('Fieldset', i, ':', headerText);
            if (headerText.indexOf('Supplier') > -1) {
                $targetFieldset = $(this);
                return false;
            }
        });
        
        // If found both, move inline before Supplier
        if ($inline.length && $targetFieldset && $targetFieldset.length) {
            $inline.insertBefore($targetFieldset);
            console.log('=== INLINE MOVED ABOVE SUPPLIER ===');
        } else {
            console.log('FAILED: inline=', $inline.length, 'target=', $targetFieldset ? $targetFieldset.length : 0);
        }
        
        // ========== HIDE "TODAY" LINKS ON DATE FIELDS ==========
        function hideTodayLinks() {
            // Grappelli uses .grp-now for "Today" links
            $('.grp-now').hide();
            // Hide by text content
            $('a').filter(function() {
                var text = $(this).text().trim().toLowerCase();
                return text === 'today' || text === 'tod' || text === 'now';
            }).hide();
            // Hide in date shortcuts area
            $('.grp-date-shortcuts, .date-shortcuts, span.datetimeshortcuts').hide();
            // Hide links near date inputs
            $('input.vDateField').each(function() {
                $(this).siblings('a').not('[class*="calendar"]').hide();
                $(this).parent().find('a').filter(function() {
                    return !$(this).find('img').length && !$(this).hasClass('grp-calendar-icon');
                }).hide();
            });
            console.log('Today links hidden');
        }
        
        // Run immediately and after a delay (for dynamically added elements)
        hideTodayLinks();
        setTimeout(hideTodayLinks, 500);
        setTimeout(hideTodayLinks, 1500);
        
        // Inject CSS to ensure "Today" stays hidden
        $('<style>')
            .text('.grp-now, .grp-date-shortcuts, .date-shortcuts, span.datetimeshortcuts a:first-child { display: none !important; }')
            .appendTo('head');
        
        // ========== SUPPLIER FILTERING ==========
        function updateSupplierFilter() {
            console.log('updateSupplierFilter called');
            
            // Try multiple possible field name patterns
            var $subCat = $('select[name*="-0-sub_category"]').first();
            if (!$subCat.length) {
                $subCat = $('select[name*="sub_category"]').first();
            }
            var subCatVal = $subCat.val();
            console.log('Sub-category select found:', $subCat.length, 'name:', $subCat.attr('name'), 'value:', subCatVal);
            
            if (subCatVal) {
                console.log('Filtering supplier by sub_category:', subCatVal);
                fetchSuppliers('sub_category_id', subCatVal);
                return;
            }
            
            // Fallback to category
            var $cat = $('select[name*="-0-category"]').not('[name*="sub_category"]').first();
            if (!$cat.length) {
                $cat = $('select[name*="category"]').not('[name*="sub_category"]').first();
            }
            var catVal = $cat.val();
            console.log('Category select found:', $cat.length, 'name:', $cat.attr('name'), 'value:', catVal);
            
            if (catVal) {
                console.log('Filtering supplier by category:', catVal);
                fetchSuppliers('category_id', catVal);
            } else {
                console.log('No category or subcategory selected yet');
            }
        }
        
        function fetchSuppliers(paramName, paramValue) {
            var $supplierSelect = $('select[name="supplier"]');
            console.log('po_inline_move.js: Supplier select found:', $supplierSelect.length);
            
            if (!$supplierSelect.length) {
                console.log('po_inline_move.js: Supplier select not found');
                return;
            }
            
            var currentValue = $supplierSelect.val();
            var url = paramName === 'sub_category_id' 
                ? '/admin/inventory/purchaseorder/get-suppliers-by-subcategory/'
                : '/admin/inventory/purchaseorder/get-suppliers-by-category/';
            
            // Extract site ID from URL (e.g., /hq/Test/admin/ or /hq/1/admin/...)
            console.log('po_inline_move.js: Current pathname:', window.location.pathname);
            var urlMatch = window.location.pathname.match(/\/hq\/([a-zA-Z0-9_-]+)\//);
            var siteId = urlMatch ? urlMatch[1] : null;
            console.log('po_inline_move.js: URL match result:', urlMatch);
            console.log('po_inline_move.js: Extracted siteId:', siteId);
            var sitePath = siteId ? `/hq/${siteId}` : '';
            console.log('po_inline_move.js: sitePath:', sitePath);
            
            // Build full URL with sitePath
            url = sitePath + url;
            console.log('po_inline_move.js: Final URL before AJAX:', url);
            
            var ajaxData = {};
            if (paramName === 'sub_category_id') {
                ajaxData.sub_category_id = paramValue;
            } else {
                ajaxData.category_id = paramValue;
            }
            
            if (siteId) {
                ajaxData.site_id = siteId;
                console.log('po_inline_move.js: Adding site_id to request:', siteId);
            }
            
            console.log('po_inline_move.js: Fetching from:', url, 'with data:', ajaxData);
            
            $.ajax({
                url: url,
                data: ajaxData,
                dataType: 'json',
                success: function(data) {
                    console.log('po_inline_move.js: Received', data.suppliers.length, 'suppliers:', data.suppliers);
                    $supplierSelect.empty();
                    $supplierSelect.append('<option value="">---------</option>');
                    
                    $.each(data.suppliers, function(i, supplier) {
                        var selected = (supplier.id == currentValue) ? ' selected' : '';
                        $supplierSelect.append('<option value="' + supplier.id + '"' + selected + '>' + supplier.name + '</option>');
                    });
                },
                error: function(xhr, status, error) {
                    console.log('po_inline_move.js: AJAX Error:', status, error, xhr.responseText);
                }
            });
        }
        
        // Listen for changes on first line item category - use broader selector
        $(document).on('change', 'select[name*="-0-category"]', function() {
            var name = $(this).attr('name');
            // Skip if it's the sub_category field
            if (name && name.indexOf('sub_category') === -1) {
                console.log('Category changed:', name, $(this).val());
                // Category changed, wait for sub_category to be populated by smart_selects
                setTimeout(updateSupplierFilter, 800);
            }
        });
        
        // Listen for changes on first line item sub_category
        $(document).on('change', 'select[name*="-0-sub_category"]', function() {
            console.log('Sub-category changed:', $(this).attr('name'), $(this).val());
            updateSupplierFilter();
        });
        
        // Also use MutationObserver to catch when smart_selects updates the sub_category dropdown
        setTimeout(function() {
            var subCatSelect = $('select[name*="-0-sub_category"]').get(0);
            if (subCatSelect) {
                var observer = new MutationObserver(function(mutations) {
                    mutations.forEach(function(mutation) {
                        if (mutation.type === 'childList') {
                            console.log('Sub-category options changed (MutationObserver)');
                            setTimeout(updateSupplierFilter, 300);
                        }
                    });
                });
                observer.observe(subCatSelect, { childList: true });
                console.log('MutationObserver attached to sub_category select:', subCatSelect.name);
            } else {
                console.log('Could not attach MutationObserver - sub_category select not found');
            }
        }, 1500);
        
        // Run on page load after a delay
        setTimeout(function() {
            console.log('Initial supplier filter run');
            updateSupplierFilter();
        }, 1000);
    });
})(django.jQuery || jQuery);
