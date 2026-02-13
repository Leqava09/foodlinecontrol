(function($) {
  console.log('[BATCH DELETE AJAX] Script loaded');
  
  // Setup delete handlers on page load and when new rows added
  $(document).ready(function() {
    console.log('[DELETE] Document ready, setting up handlers...');
    
    // Debug: log what we find
    console.log('[DELETE] Page contains:', $('body').length, 'body elements');
    console.log('[DELETE] Looking for .grp-tbody:', $('.grp-tbody').length);
    console.log('[DELETE] Looking for .grp-row:', $('.grp-row').length);
    console.log('[DELETE] Looking for .inline-group:', $('.inline-group').length);
    console.log('[DELETE] Looking for tbody:', $('tbody').length);
    console.log('[DELETE] Looking for tr:', $('tr').length);
    
    // Try finding batch rows with different selectors
    const selectors = [
      '.grp-tbody .grp-row',
      'tbody .grp-row',
      '.grp-row',
      'tr.grp-row',
      'table tbody tr',
      '.inline-group tr',
      '.inline-group tbody tr'
    ];
    
    for (const selector of selectors) {
      const count = $(selector).length;
      if (count > 0) {
        console.log('[DELETE] Found', count, 'elements with selector:', selector);
      }
    }
    
    setupDeleteHandlers();
  });
  
  function setupDeleteHandlers() {
    console.log('[DELETE] Looking for batch_items form fields...');
    
    // Find all batch_number inputs (these identify batch rows)
    const $batchNumberInputs = $('input[name*="batch_items-"][name*="-batch_number"]');
    console.log('[DELETE] Found', $batchNumberInputs.length, 'batch_number inputs');
    
    let setupCount = 0;
    
    $batchNumberInputs.each(function() {
      const $batchNumberInput = $(this);
      const batchNumber = $batchNumberInput.val();
      
      if (!batchNumber) {
        console.log('[DELETE] Skipping empty batch_number');
        return;
      }
      
      // Extract form index from the name (e.g., batch_items-0-batch_number -> 0)
      const nameAttr = $batchNumberInput.attr('name');
      const match = nameAttr.match(/batch_items-(\d+)-/);
      if (!match) {
        console.log('[DELETE] Could not extract index from:', nameAttr);
        return;
      }
      
      const formIndex = match[1];
      console.log('[DELETE] Batch: ' + batchNumber + ' (form index: ' + formIndex + ')');
      
      // Find all inputs and elements for THIS form (using the extracted index)
      const $formElements = $('input[name*="batch_items-' + formIndex + '-"], a[name*="batch_items-' + formIndex + '-"]');
      console.log('[DELETE]   Found ' + $formElements.length + ' form elements for this batch');
      
      // Find the delete button - search in parent containers
      let $xButton = null;
      let $row = null;
      
      // Try to find a parent that contains a delete link
      let $current = $batchNumberInput.parent();
      for (let i = 0; i < 10 && $current.length > 0; i++) {
        const $deleteLink = $current.find('a[title*="delete"], a.grp-delete-handler').first();
        if ($deleteLink.length > 0) {
          $xButton = $deleteLink;
          $row = $current;
          console.log('[DELETE]   Found delete button at depth ' + i);
          break;
        }
        $current = $current.parent();
      }
      
      if (!$xButton || !$row) {
        console.log('[DELETE]   No delete button found');
        return;
      }
      
      // Find ID field (batch_id is the primary key, not batch_number)
      const $idField = $('input[name="batch_items-' + formIndex + '-id"]');
      const batchId = $idField.val();
      
      if (!batchId) {
        console.log('[DELETE]   No batch ID found, skipping');
        return;
      }
      
      console.log('[DELETE]   Using batch ID as identifier: ' + batchId + ' (batch_number: ' + batchNumber + ')');
      
      console.log('[DELETE]   ✓ Setup X button');
      setupCount++;
      
      // Override click handler
      $xButton.off('click').on('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        const confirmMsg = `Delete batch "${batchNumber}"? This cannot be undone.`;
        console.log('[DELETE] X clicked for: ' + batchNumber);
        
        if (!confirm(confirmMsg)) {
          return false;
        }
        
        // Delete via AJAX using batch ID (not batch_number, which is not globally unique)
        console.log('[DELETE] AJAX delete batch ID: ' + batchId + ' (batch_number: ' + batchNumber + ')');
        
        $row.css('opacity', '0.3');
        $xButton.html('Deleting...');
        
        $.ajax({
          url: '/manufacturing/api/delete-batch/' + batchId + '/',
          type: 'POST',
          headers: {
            'X-CSRFToken': getCookie('csrftoken')
          },
          success: function(response) {
            console.log('[DELETE] ✓ Success:', response);
            if (response.success) {
              $row.fadeOut(300, function() {
                $(this).remove();
                
                // After removing the row, renumber all remaining forms and update management form
                renumberForms();
              });
            } else {
              alert('Error: ' + (response.error || 'Unknown error'));
              $row.css('opacity', '1');
              $xButton.html('×');
            }
          },
          error: function(xhr, status, error) {
            console.error('[DELETE] ✗ Error:', status, error);
            let errorMsg = 'Failed to delete batch: ' + status;
            try {
              const response = JSON.parse(xhr.responseText);
              if (response.error) {
                errorMsg = response.error;
              }
            } catch (e) {}
            alert(errorMsg);
            $row.css('opacity', '1');
            $xButton.html('×');
          }
        });
        
        return false;
      });
    });
    
    console.log('[DELETE] Setup complete. Configured ' + setupCount + ' batch rows.');
  }
  
  function renumberForms() {
    console.log('[DELETE] Renumbering forms...');
    
    // Find all remaining batch forms by looking for batch_number inputs
    const $batchNumberInputs = $('input[name*="batch_items-"][name*="-batch_number"]');
    let newIndex = 0;
    let initialCount = 0;
    
    $batchNumberInputs.each(function() {
      const $input = $(this);
      const nameAttr = $input.attr('name');
      const match = nameAttr.match(/batch_items-(\d+)-/);
      
      if (!match) {
        return;
      }
      
      const oldIndex = match[1];
      
      // Only renumber if index changed
      if (oldIndex != newIndex) {
        console.log('[DELETE]   Renumbering form ' + oldIndex + ' to ' + newIndex);
        
        // Find all inputs/selects/textareas for this form and rename them
        const oldPrefix = 'batch_items-' + oldIndex + '-';
        const newPrefix = 'batch_items-' + newIndex + '-';
        
        $('input[name^="' + oldPrefix + '"], select[name^="' + oldPrefix + '"], textarea[name^="' + oldPrefix + '"]').each(function() {
          const $field = $(this);
          const oldName = $field.attr('name');
          const oldId = $field.attr('id');
          
          if (oldName) {
            const newName = oldName.replace(oldPrefix, newPrefix);
            $field.attr('name', newName);
          }
          
          if (oldId) {
            const newId = oldId.replace('id_' + oldPrefix, 'id_' + newPrefix);
            $field.attr('id', newId);
          }
        });
        
        // Update labels as well
        $('label[for^="id_' + oldPrefix + '"]').each(function() {
          const $label = $(this);
          const oldFor = $label.attr('for');
          if (oldFor) {
            const newFor = oldFor.replace('id_' + oldPrefix, 'id_' + newPrefix);
            $label.attr('for', newFor);
          }
        });
      }
      
      // Check if this form has an ID (existing record)
      const $idField = $('input[name="batch_items-' + newIndex + '-id"]');
      if ($idField.length > 0 && $idField.val()) {
        initialCount++;
      }
      
      newIndex++;
    });
    
    // Update management form
    const $totalForms = $('#id_batch_items-TOTAL_FORMS');
    const $initialForms = $('#id_batch_items-INITIAL_FORMS');
    
    if ($totalForms.length > 0) {
      $totalForms.val(newIndex);
      console.log('[DELETE] Set TOTAL_FORMS to ' + newIndex);
    }
    
    if ($initialForms.length > 0) {
      $initialForms.val(initialCount);
      console.log('[DELETE] Set INITIAL_FORMS to ' + initialCount);
    }
    
    console.log('[DELETE] Renumbering complete');
    
    // Re-setup delete handlers for renumbered forms
    setupDeleteHandlers();
  }
  
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
  
})(jQuery);
