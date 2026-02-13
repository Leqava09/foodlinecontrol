/**
 * HQ Purchase Order - Cascading inline dropdowns (v5 - minimal safe)
 *
 * Django form __init__ pre-populates all dropdowns for existing records.
 * This JS ONLY handles user-initiated cascading, line totals, and inline position.
 * It does NOT touch any values on page load.
 */
(function($) {
    'use strict';

    $(document).ready(function() {
        console.log('HQ PO JS v5 loaded');

        var baseUrl = window.location.pathname.split('/inventory/purchaseorder/')[0]
                    + '/inventory/purchaseorder/';

        // Guard: ignore all programmatic change events during first second of page load
        var userReady = false;
        setTimeout(function() { userReady = true; console.log('JS ready for user input'); }, 1000);

        function getSelectedSite() { return $('#id_site').val() || ''; }

        // =====================================================================
        // MOVE INLINE BETWEEN SITE AND TOTALS (pure DOM, no data changes)
        // =====================================================================
        setTimeout(function() {
            var $inline = $('div.grp-group').filter(function() {
                return $(this).find('h2, .grp-collapse-handler').first().text().toLowerCase().indexOf('hq po line item') >= 0;
            });
            if (!$inline.length) $inline = $('div[id*="hqpolineitem"]').first();
            if (!$inline.length) return;

            var $totals = null;
            $('fieldset.grp-module, div.grp-module').each(function() {
                if ($(this).find('h2, .grp-collapse-handler').first().text().indexOf('Totals') >= 0) {
                    $totals = $(this); return false;
                }
            });
            if ($totals && $totals.length) $inline.insertBefore($totals);
        }, 200);

        // =====================================================================
        // AJAX HELPERS
        // =====================================================================
        function loadProductNames(categoryId, siteId, $sel, cb) {
            if (!categoryId) { $sel.empty().append('<option value="">---------</option>'); if (cb) cb(); return; }
            $.getJSON(baseUrl + 'get-product-names/', { category_id: categoryId, site_id: siteId }, function(d) {
                $sel.empty().append('<option value="">---------</option>');
                $.each(d.product_names || [], function(i, v) { $sel.append($('<option>').val(v).text(v)); });
                if (cb) cb();
            });
        }

        function loadSkus(productName, categoryId, $sel, cb) {
            if (!productName) { $sel.empty().append('<option value="">---------</option>'); if (cb) cb(); return; }
            $.getJSON(baseUrl + 'get-skus/', { product_name: productName, category_id: categoryId }, function(d) {
                $sel.empty().append('<option value="">---------</option>');
                $.each(d.skus || [], function(i, s) {
                    $sel.append($('<option>').val(s.id).text(s.label).data('size', s.size));
                });
                if (cb) cb();
            });
        }

        // =====================================================================
        // CASCADING HANDLERS (delegated, only fire on real user interaction)
        // =====================================================================

        // Category → load Product Names
        $(document).on('change', 'select[name$="-category"]', function() {
            if (!userReady) return;
            var $row = $(this).closest('tr, .grp-tr');
            var $prodName = $row.find('select[name$="-product_name_select"]');
            var $sku = $row.find('select[name$="-sku_select"]');
            var $size = $row.find('input[name$="-size_display"]');
            var $product = $row.find('input[name$="-product"]');
            loadProductNames($(this).val(), getSelectedSite(), $prodName);
            $sku.empty().append('<option value="">---------</option>');
            $size.val('');
            $product.val('');
        });

        // Product Name → load SKUs
        $(document).on('change', 'select[name$="-product_name_select"]', function() {
            if (!userReady) return;
            var $row = $(this).closest('tr, .grp-tr');
            var $sku = $row.find('select[name$="-sku_select"]');
            var $size = $row.find('input[name$="-size_display"]');
            var $product = $row.find('input[name$="-product"]');
            var catId = $row.find('select[name$="-category"]').val();
            loadSkus($(this).val(), catId, $sku);
            $size.val('');
            $product.val('');
        });

        // SKU → set hidden product FK + size
        $(document).on('change', 'select[name$="-sku_select"]', function() {
            if (!userReady) return;
            var $row = $(this).closest('tr, .grp-tr');
            var productId = $(this).val();
            $row.find('input[name$="-product"]').val(productId);
            var size = productId ? ($(this).find(':selected').data('size') || '-') : '';
            $row.find('input[name$="-size_display"]').val(size);
        });

        // =====================================================================
        // LINE TOTAL (delegated, always active)
        // =====================================================================
        function calcLineTotal($row) {
            var q = parseFloat($row.find('input[name$="-quantity"]').val()) || 0;
            var p = parseFloat($row.find('input[name$="-unit_price"]').val()) || 0;
            var fmt = 'R ' + (q * p).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
            $row.find('.grp-td.line_total_display .grp-readonly, .grp-td.line_total_display p').text(fmt);
            $row.find('.field-line_total_display .readonly, .field-line_total_display p').text(fmt);
        }

        $(document).on('input change', 'input[name$="-quantity"], input[name$="-unit_price"]', function() {
            calcLineTotal($(this).closest('tr, .grp-tr'));
        });
    });
})(django.jQuery);
