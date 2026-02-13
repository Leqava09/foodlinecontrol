(function($) {
  console.log('[SKU] Script loaded');
  
 // ✅ NEW: Intercept smart-selects AJAX requests to add site filtering
  const originalAjax = $.ajax;
  $.ajax = function(settings) {
    // Check if this is a smart-selects chaining request
    if (settings.url && settings.url.includes('/chaining/filter/')) {
      console.log('[SKU] Intercepting smart-selects chaining request:', settings.url);
      
      // Wrap the success callback to filter results by site
      const originalSuccess = settings.success;
      settings.success = function(data, status, xhr) {
        console.log('[SKU] Chaining response received:', data);
        
        // If we get product options, they might be from all sites
        // Log what we're getting so we can verify
        if (typeof data === 'string') {
          try {
            data = JSON.parse(data);
          } catch (e) {
            // Not JSON, probably HTML
          }
        }
        
        console.log('[SKU] Processed chaining data:', data);
        
        // Call the original success handler
        if (originalSuccess) {
          originalSuccess(data, status, xhr);
        }
      };
    }
    
    return originalAjax.call(this, settings);
  };
  
  function populateSkuFromProduct(productSelect) {
    const productId = $(productSelect).val();
    
    console.log('[SKU] Populating for product:', productId);
    
    if (!productId) {
      console.log('[SKU] No product');
      return;
    }
    
    // Extract row index
    const nameMatch = $(productSelect).attr('name').match(/batch_items-(\d+)/);
    if (!nameMatch) {
      console.log('[SKU] Could not extract index');
      return;
    }
    
    const idx = nameMatch[1];
    console.log('[SKU] Row index:', idx);
    
    // Look for SKU select
    const $skuSelect = $('select[name="batch_items-' + idx + '-sku"]');
    console.log('[SKU] SKU select found:', $skuSelect.length);
    
    if ($skuSelect.length === 0) {
      console.log('[SKU] ERROR: No SKU select');
      return;
    }
    
    // Fetch SKU options
    const url = '/manufacturing/product-sku-options/' + productId + '/';
    console.log('[SKU] Fetching:', url);
    
    $.ajax({
      url: url,
      dataType: 'json',
      success: function(data) {
        console.log('[SKU] Response:', data);
        
        if (data.error) {
          console.error('[SKU] API Error:', data.error);
          return;
        }
        
        if (!data.options || data.options.length === 0) {
          console.log('[SKU] ⚠️  No SKU options found for this product');
          $skuSelect.html('<option value="">-- No SKUs available --</option>');
          return;
        }
        
        console.log('[SKU] ✓ Found', data.options.length, 'SKU options');
        
        // Populate SKU dropdown WITHOUT size text (size will show in separate read-only field)
        $skuSelect.html('<option value="">-- Select SKU --</option>');
        $.each(data.options, function(i, opt) {
          $skuSelect.append(
            $('<option>').val(opt.sku).attr('data-size', opt.size).text(opt.sku)  // ✅ Show only SKU, not size
          );
        });
        
        // After populating options, check if there's a saved value with size appended
        // and select the clean SKU version
        const currentVal = $skuSelect.val();
        if (currentVal && currentVal.includes('(')) {
          const cleanSku = currentVal.split('(')[0].trim();
          console.log('[SKU] Selecting clean SKU:', cleanSku, 'from saved:', currentVal);
          $skuSelect.val(cleanSku);
        }
        
        console.log('[SKU] ✓ SKU dropdown populated - size will update dynamically when SKU selected');
      },
      error: function(xhr, status, error) {
        console.error('[SKU] ✗ AJAX Error:', status, error);
        console.error('[SKU] Response:', xhr.responseText);
        $skuSelect.html('<option value="">-- Error loading SKUs --</option>');
      }
    });
  }
    function updateSizeForRow(idx, sizeValue) {
    console.log('[SKU] Updating size for row', idx, 'to:', sizeValue);
    
    // Find the SKU select field first to identify the row
    const $skuSelect = $('select[name="batch_items-' + idx + '-sku"]');
    if ($skuSelect.length === 0) {
      console.log('[SKU] SKU select not found for row', idx);
      return;
    }
    
    // In Grappelli, the structure is: div.grp-tr > div.grp-td.sku > select
    const $row = $skuSelect.closest('.grp-tr');
    if ($row.length === 0) {
      console.log('[SKU] Could not find .grp-tr row container');
      return;
    }
    
    console.log('[SKU] Found grp-tr row');
    
    // Find the size cell - it's a div.grp-td.size in the same row
    const $sizeCell = $row.find('div.grp-td.size').first();
    console.log('[SKU] Size cell found:', $sizeCell.length);
    
    if ($sizeCell.length === 0) {
      console.log('[SKU] Could not find size cell div.grp-td.size');
      return;
    }
    
    // Clear and update the text in the size cell
    $sizeCell.text(sizeValue);
    console.log('[SKU] ✓ Size updated to:', sizeValue);
  }
  
  // Before form submission, clean up any SKU values with size appended
  $(document).on('submit', 'form', function() {
    $('select[name*="-sku"]').each(function() {
      const $skuSelect = $(this);
      const val = $skuSelect.val();
      
      if (val && val.includes('(')) {
        // This SKU has size appended - strip it before submitting
        const cleanSku = val.split('(')[0].trim();
        console.log('[SKU] Pre-submit clean: removing size from:', val, 'keeping:', cleanSku);
        $skuSelect.val(cleanSku);
      }
    });
  });
  
  // Listen for category changes
  $(document).on('change', 'select[name*="-category"]', function() {
    console.log('[SKU] Category changed:', $(this).attr('name'));
    
    const nameMatch = $(this).attr('name').match(/batch_items-(\d+)/);
    if (!nameMatch) return;
    
    const idx = nameMatch[1];
    
    setTimeout(function() {
      const $productSelect = $('select[name="batch_items-' + idx + '-product"]');
      console.log('[SKU] Product select:', $productSelect.length, 'Value:', $productSelect.val());
      
      if ($productSelect.length > 0 && $productSelect.val()) {
        populateSkuFromProduct($productSelect[0]);
      }
    }, 300);
  });
  
  // Listen for SKU select changes to update size when user selects a SKU
  $(document).on('change', 'select[name*="-sku"]', function() {
    const name = $(this).attr('name');
    const nameMatch = name.match(/batch_items-(\d+)/);
    
    if (!nameMatch) return;
    
    const idx = nameMatch[1];
    const selectedSize = $(this).find('option:selected').attr('data-size');
    
    console.log('[SKU] SKU selected for row', idx, 'Size:', selectedSize);
    
    if (selectedSize) {
      updateSizeForRow(idx, selectedSize);
    }
  });
  
  console.log('[SKU] Ready - Setting up product change monitoring');
  
  // ✅ ROBUST: Monitor all product selects for value changes (handles smart-selects)
  // Smart-selects may not fire standard 'change' events, so we actively check for changes
  
  const productSelectState = {};  // Track state of each product select
  
  // Function to set up monitoring for a specific select
  function monitorProductSelect($select) {
    const name = $select.attr('name');
    if (!name || productSelectState[name]) {
      return;  // Already monitoring or no name
    }
    
    productSelectState[name] = {
      lastValue: $select.val(),
      monitoring: true
    };
    
    console.log('[SKU] Started monitoring product select:', name, 'Value:', $select.val());
  }
  
  // Monitor all current product selects
  $('select[name*="-product"]').each(function() {
    monitorProductSelect($(this));
  });
  
  // Also listen for standard change events and update monitoring
  $(document).on('change', 'select[name*="-product"]', function() {
    monitorProductSelect($(this));
    console.log('[SKU] Product select fired change event:',$(this).attr('name'));
    populateSkuFromProduct(this);
  });
  
  // Check every 300ms if any monitored product select values changed
  setInterval(function() {
    $.each(productSelectState, function(selectName, state) {
      if (!state.monitoring) return;
      
      const $select = $('select[name="' + selectName + '"]');
      if ($select.length === 0) return;
      
      const currentValue = $select.val();
      if (currentValue && currentValue !== state.lastValue) {
        console.log('[SKU] ✓ Product select value changed (smart-selects detected):', selectName, 'From:', state.lastValue, 'To:', currentValue);
        state.lastValue = currentValue;
        populateSkuFromProduct($select[0]);
      }
    });
  }, 300);
  
  // On page load, populate SKU options for any rows that already have a product selected
  $('select[name*="-product"]').each(function() {
    const $productSelect = $(this);
    const productId = $productSelect.val();
    
    if (productId) {
      console.log('[SKU] Page load: Found existing product:', productId);
      populateSkuFromProduct(this);
    }
  });
  
})(jQuery);













