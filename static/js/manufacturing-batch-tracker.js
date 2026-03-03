/* ============================================================ */
/* MANUFACTURING BATCH TRACKER - COMPLETE CLEAN JAVASCRIPT */
/* Renders ALL 7 tabs from window.BATCH_DATA */
/* AUTO-CALCULATES CERTIFICATION DATES */
/* ============================================================ */

// ========== CHANGE LOG TRACKING ==========
window.CHANGE_LOG = [];

document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('mainform');
  if (!form) {

    return;
  }


  // Log on BOTH 'input' (live) and 'change' (on blur)
  ['input', 'change'].forEach(eventType => {
    form.addEventListener(eventType, function (e) {
      // Skip if not an actual input/select/textarea
      if (!['INPUT', 'SELECT', 'TEXTAREA'].includes(e.target.tagName)) return;


      const fieldName = e.target.name || e.target.id || 'unknown';
      const oldValue  = e.target.dataset.oldValue || '';

      let newValue = '';
      if (e.target.type === 'file') {
        const files = Array.from(e.target.files || []);
        newValue = files.map(f => f.name).join(', ');
      } else if (e.target.type === 'checkbox' || e.target.type === 'radio') {
        newValue = e.target.checked ? 'checked' : 'unchecked';
      } else {
        newValue = e.target.value;
      }

      // Only log to CHANGE_LOG on 'change' (final), not 'input' (every keystroke)
      if (eventType === 'change') {
        window.CHANGE_LOG.push({
          field: fieldName,
          oldValue,
          newValue,
          timestamp: new Date().toLocaleString(),
          user: document.querySelector('[data-user]')?.dataset.user || 'Current User',
        });

        e.target.dataset.oldValue = newValue;
      }
    }, true); // capture
  });
});

// History modal
window.showHistory = function () {
  if (!window.CHANGE_LOG.length) {
    alert('No changes logged yet');
    return;
  }

  const modal = document.getElementById('history-modal');
  const body  = document.getElementById('history-body');
  if (!modal || !body) {

    return;
  }

  let html = '<h3>Change History</h3><table class="history-table" style="width:100%; border-collapse:collapse;">';
  html += '<tr style="background:#417690; color:white;"><th style="padding:8px;">Field</th><th style="padding:8px;">Old</th><th style="padding:8px;">New</th><th style="padding:8px;">When</th></tr>';

  window.CHANGE_LOG.forEach(log => {
    html += `<tr style="border-bottom:1px solid #ddd;">
      <td style="padding:8px;">${log.field}</td>
      <td style="padding:8px;">${log.oldValue}</td>
      <td style="padding:8px;">${log.newValue}</td>
      <td style="padding:8px;">${log.timestamp}</td>
    </tr>`;
  });
  html += '</table>';

  body.innerHTML = html;
  modal.style.display = 'block';
};

// ========== SAUCE USAGE CALCULATION (MUST BE BEFORE DOMContentLoaded) ==========
window.updateSauceItemUsage = function(input) {
  try {
    const card = input.closest('.packaging-card');
    if (!card) return;

    const openingEl = card.querySelector('input[name^="sauce_opening_"]');
    const bookedEl = card.querySelector('input[name^="sauce_booked_"]');
    const closingEl = input; // the input that changed
    const cancelCheckbox = card.querySelector('.sauce-cancel-checkbox');
    const usageEl = card.querySelector('input[name^="sauce_usage_"]');

    if (!usageEl) return;

    const opening = parseFloat(openingEl?.value || 0);
    const booked = parseFloat(bookedEl?.value || 0);
    const closing = parseFloat(closingEl.value || 0);
    const isCancelled = cancelCheckbox?.checked || false;

    let usage = 0;
    if (isCancelled) {
      usage = booked - closing;
    } else {
      usage = opening + booked - closing;
    }

    usageEl.value = Math.max(0, usage).toFixed(2);
    
    // Also update Recipe Summary
    if (typeof window.syncSauceSummaryFromCards === 'function') {
      window.syncSauceSummaryFromCards();
    }
  } catch (e) {

  }
};

window.syncSauceSummaryFromCards = function() {
  try {
    const openingInput = document.querySelector('input[name="opening_balance"]');
    const mixedInput = document.querySelector('input[name="sauce_mixed"]');
    const closingInput = document.querySelector('input[name="closing_balance"]');
    const cancelCheckbox = document.querySelector('input[name="cancel_opening_balance"]');
    const usageForDayInput = document.querySelector('input[name="usage_for_day"]');

    if (!openingInput || !mixedInput || !closingInput || !usageForDayInput) return;

    const opening = parseFloat(openingInput.value || 0);
    const mixed = parseFloat(mixedInput.value || 0);
    const closing = parseFloat(closingInput.value || 0);
    const isCancelled = cancelCheckbox?.checked || false;

    const usage = isCancelled 
      ? (mixed - closing).toFixed(2)
      : (opening + mixed - closing).toFixed(2);

    usageForDayInput.value = usage;
  } catch (e) {

  }
};

document.addEventListener('DOMContentLoaded', function() {
  
  if (!window.BATCH_DATA) {

    return;
  }
  // ✅ Add this flag to prevent multiple renders
  window.renderInProgress = false;
  
  // RENDER ALL TABS (with guard)
  if (!window.renderInProgress) {
    window.renderInProgress = true;
    window.renderInProgress = true;
	
	// RENDER ALL TABS
	renderCertificationTab();
	renderMeatTab();
	renderSauceTab();
	renderProcessingTab();
	renderPackagingTab();
	renderDowntimeTab();
	renderProductTab();
	renderSummaryTab();
	  
	window.renderInProgress = false;
  }
  
  
  // Remove active from ALL tabs first
  document.querySelectorAll('.tab-content').forEach(tab => {
    tab.classList.remove('active');
  });
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.remove('active');
  });
  
  // Initialize all tab functionality
  initializeTabs();
  initializeDateCalculations();
  initializeCalculations();
  initializeFileInputs();
  
  // LOAD SAVED DATA
  loadSavedData();

  // ===== RECALCULATE TOTALS FROM LOADED DATA =====
  setTimeout(() => {
    calculateMachineTotal();
    calculateRetortTotal();
  }, 50);

  
  // READ TAB FROM URL PARAMETER
  const urlParams = new URLSearchParams(window.location.search);
  const tabFromUrl = urlParams.get('tab');
  if (tabFromUrl) {
    const tabBtn = document.querySelector(`.tab-btn[onclick*="'${tabFromUrl}'"]`);
    if (tabBtn) {
      tabBtn.click();
    }
  }
  
  
  // ============= FINAL FIX - FORM SUBMISSION =============
  const mainForm = document.getElementById('mainform');

  if (mainForm) {
      let saveActionInput = mainForm.querySelector('input[name="save_action"]');
      if (!saveActionInput) {
          saveActionInput = document.createElement('input');
          saveActionInput.type = 'hidden';
          saveActionInput.name = 'save_action';
          saveActionInput.value = 'save';
          mainForm.appendChild(saveActionInput);
      }

      const btnSaveExit = document.querySelector('.btn-save-exit')
	  if (btnSaveExit) {
		  btnSaveExit.addEventListener('click', function(e) {
			  saveActionInput.value = 'saveexit'
			  // Submit via fetch instead of direct form.submit()
			  e.preventDefault()
			  const formData = new FormData(mainForm)
			  formData.set('saveaction', 'saveexit')
			
			  fetch(mainForm.action || window.location.href, {
				  method: 'POST',
				  body: formData
			  })
			  .then(response => {
			 	  if (response.ok) {
					  window.location.href = '/admin/manufacturing/production/'
				  }
			  })
			  .catch(error => {
				  // Handle error silently
			  })
		  })
	  }

	  const btnSave = document.querySelector('.btn-save')
	  if (btnSave) {
		  btnSave.addEventListener('click', function(e) {
			  saveActionInput.value = 'save'
			  mainForm.submit()  // ← Regular submit, stays on page
		  })
	  }

      mainForm.addEventListener('submit', function(e) {
          const submitter = e.submitter;
          const currentValue = saveActionInput.value;
        

          if (submitter && submitter.classList.contains('btn-save-exit')) {
              return;
          }

          if (submitter && submitter.classList.contains('btn-save')) {
              e.preventDefault();

              const activeTabBtn = document.querySelector('.tab-btn.active');
              let activeTab = 'cert';

              if (activeTabBtn) {
                  const onclick = activeTabBtn.getAttribute('onclick');
                  if (onclick) {
                      const match = onclick.match(/'([^']+)'/);
                      if (match) activeTab = match[1];
                  }
              }

              const activeTabInput = document.getElementById('active_tab_input');
              if (activeTabInput) {
                  activeTabInput.value = activeTab;
              }

              mainForm.submit();
              return;
          }
      });
  }
    // ============= FILE UPLOAD HANDLERS (NSI + DEFROST) =============
	document.addEventListener('click', function (e) {
	  
	  // ========== NSI CERTIFICATE ==========
	  if (e.target.classList.contains('nsi-add-row')) {
		const batchNumber = e.target.getAttribute('data-batch');
		const containerElem = document.querySelector(`.nsi-file-rows[data-batch="${batchNumber}"]`);
		const list = document.querySelector(`.nsi-doc-list[data-batch="${batchNumber}"]`);
		if (!containerElem || !list) return;

		const input = document.createElement('input');
		input.type = 'file';
		input.name = `nsi_certificate_${batchNumber}`;
		input.className = 'nsi-file-input';
		input.style.display = 'none';

		input.addEventListener('change', function () {
		  if (!input.files || !input.files[0]) {
			input.remove();
			return;
		  }
		  const file = input.files[0];

		  const li = document.createElement('li');
		  li.className = 'nsi-doc-item';
		  li.innerHTML = `
			<span>${file.name}</span>
			<button type="button"
					class="nsi-remove-row"
					style="margin-left:5px; border:none; background:none; color:#d32f2f; font-weight:bold; cursor:pointer;">×</button>
		  `;
		  li._fileInput = input;
		  list.appendChild(li);
		});

		containerElem.appendChild(input);
		input.click();
	  }

	  if (e.target.classList.contains('nsi-remove-row')) {
		const li = e.target.closest('.nsi-doc-item');
		const existingId = e.target.getAttribute('data-doc-id');

		if (existingId) {
		  const form = document.getElementById('mainform');
		  if (form) {
			const hidden = document.createElement('input');
			hidden.type = 'hidden';
			hidden.name = 'delete_nsi_ids[]';
			hidden.value = existingId;
			form.appendChild(hidden);
		  }
		}

		if (li && li._fileInput) {
		  li._fileInput.remove();
		}
		if (li) li.remove();
	  }

	  // ========== DEFROST SHEET ==========
	  if (e.target.classList.contains('defrost-add-row')) {
	    const card = e.target.closest('.container-card');
	    if (!card) return;
	  
	    // ✅ Get container index
	    const cards = document.querySelectorAll('.container-card');
	    const cardIndex = Array.from(cards).indexOf(card);
	  
	    const containerElem = card.querySelector('.defrost-file-rows');
	    const list = card.querySelector('.defrost-doc-list');
	    if (!containerElem || !list) return;

	    const input = document.createElement('input');
	    input.type = 'file';
	    input.name = `defrost_sheet_${cardIndex}[]`;  // ← unique per container
	    input.className = 'defrost-file-input';
	    input.style.display = 'none';
	    input.accept = '.pdf,.doc,.docx';

	    input.addEventListener('change', function () {
		  if (!input.files || !input.files[0]) {
		    input.remove();
		    return;
		  }
		  const file = input.files[0];

		  const li = document.createElement('li');
		  li.className = 'defrost-doc-item';
		  li.innerHTML = `
		    <span>${file.name}</span>
		    <button type="button"
				    class="defrost-remove-row"
				    style="margin-left:5px; border:none; background:none; color:#d32f2f; font-weight:bold; cursor:pointer;">×</button>
		  `;
		  li._fileInput = input;
		  list.appendChild(li);
	    });

	    containerElem.appendChild(input);
	    input.click();
	  }


	  if (e.target.classList.contains('defrost-remove-row')) {
		const li = e.target.closest('.defrost-doc-item');
		const existingId = e.target.getAttribute('data-doc-id');

		if (existingId) {
		  const form = document.getElementById('mainform');
		  if (form) {
			const hidden = document.createElement('input');
			hidden.type = 'hidden';
			hidden.name = 'delete_defrost_ids[]';
			hidden.value = existingId;
			form.appendChild(hidden);
		  }
		}

		if (li && li._fileInput) {
		  li._fileInput.remove();
		}
		if (li) li.remove();
	  }
	  
	  // ========== RECIPE DOCUMENTS ==========
	  if (e.target.classList.contains('recipe-add-row')) {
		const containerElem = document.querySelector('.recipe-file-rows');
		const list = document.querySelector('.recipe-doc-list');
		if (!containerElem || !list) return;

		const input = document.createElement('input');
		input.type = 'file';
		input.name = 'recipe_documents[]';
		input.className = 'recipe-file-input';
		input.style.display = 'none';
		input.accept = '.pdf,.doc,.docx';

		input.addEventListener('change', function() {
		  if (!input.files || !input.files[0]) {
			input.remove();
			return;
		  }
		  const file = input.files[0];

		  const li = document.createElement('li');
		  li.className = 'recipe-doc-item';
		  li.innerHTML = `
			<span>${file.name}</span>
			<button type="button"
					class="recipe-remove-row"
					style="margin-left:5px; border:none; background:none; color:#d32f2f; font-weight:bold; cursor:pointer;">×</button>
		  `;
		  li._fileInput = input;
		  list.appendChild(li);
		});

		containerElem.appendChild(input);
		input.click();
	  }

	  if (e.target.classList.contains('recipe-remove-row')) {
		const li = e.target.closest('.recipe-doc-item');
		const existingId = e.target.getAttribute('data-doc-id');

		if (existingId) {
		  const form = document.getElementById('mainform');
		  if (form) {
			const hidden = document.createElement('input');
			hidden.type = 'hidden';
			hidden.name = 'delete_recipe_ids[]';
			hidden.value = existingId;
			form.appendChild(hidden);
		  }
		}

		if (li && li._fileInput) {
		  li._fileInput.remove();
		}
		if (li) li.remove();
	  }
	  
	  // ========== NSI SAMPLE LOG ==========
	  if (e.target.classList.contains('nsi-sample-log-add-row')) {
	    const containerElem = document.querySelector('.nsi-sample-log-file-rows');
	    const list = document.querySelector('.nsi-sample-log-doc-list');
	    if (!containerElem || !list) return;

	    const input = document.createElement('input');
	    input.type = 'file';
	    input.name = 'nsi_sample_log_documents[]';
	    input.className = 'nsi-sample-log-file-input';
	    input.style.display = 'none';
	    input.accept = '.pdf,.doc,.docx';

	    input.addEventListener('change', function() {
		  if (!input.files || !input.files[0]) {
		    input.remove();
		    return;
		  }
		  const file = input.files[0];

		  const li = document.createElement('li');
		  li.className = 'nsi-sample-log-doc-item';
		  li.innerHTML = `
		    <span>${file.name}</span>
		    <button type="button"
				    class="nsi-sample-log-remove-row"
				    style="margin-left:5px; border:none; background:none; color:#d32f2f; font-weight:bold; cursor:pointer;">×</button>
		  `;
		  li._fileInput = input;
		  list.appendChild(li);
	    });

	    containerElem.appendChild(input);
	    input.click();
	  }

	  if (e.target.classList.contains('nsi-sample-log-remove-row')) {
	    const li = e.target.closest('.nsi-sample-log-doc-item');
	    const existingId = e.target.getAttribute('data-doc-id');

	    if (existingId) {
		  const form = document.getElementById('mainform');
		  if (form) {
		    const hidden = document.createElement('input');
		    hidden.type = 'hidden';
		    hidden.name = 'delete_nsi_sample_log_ids[]';
		    hidden.value = existingId;
		    form.appendChild(hidden);
		  }
	    }

	    if (li && li._fileInput) {
		  li._fileInput.remove();
	    }
	    if (li) li.remove();
	  }
	  // ========== MACHINE PRODUCTION DOCUMENT ==========
	  if (e.target.classList.contains('machine-production-add-row')) {
	    const containerElem = document.querySelector('.machine-production-file-rows');
	    const list = document.querySelector('.machine-production-doc-list');
	    if (!containerElem || !list) return;

	    const input = document.createElement('input');
	    input.type = 'file';
	    input.name = 'machine_production_documents[]';
	    input.className = 'machine-production-file-input';
	    input.style.display = 'none';
	    input.accept = '.pdf,.doc,.docx';

	    input.addEventListener('change', function() {
		  if (!input.files || !input.files[0]) {
		    input.remove();
		    return;
		  }
		  const file = input.files[0];

		  const li = document.createElement('li');
		  li.className = 'machine-production-doc-item';
		  li.innerHTML = `
		    <span>${file.name}</span>
		    <button type="button"
				    class="machine-production-remove-row"
				    style="margin-left:5px; border:none; background:none; color:#d32f2f; font-weight:bold; cursor:pointer;">×</button>
		  `;
		  li._fileInput = input;
		  list.appendChild(li);
	    });

	    containerElem.appendChild(input);
	    input.click();
	  }

	  if (e.target.classList.contains('machine-production-remove-row')) {
	    const li = e.target.closest('.machine-production-doc-item');
	    const existingId = e.target.getAttribute('data-doc-id');

	    if (existingId) {
		  const form = document.getElementById('mainform');
		  if (form) {
		    const hidden = document.createElement('input');
		    hidden.type = 'hidden';
		    hidden.name = 'delete_machine_production_ids[]';
		    hidden.value = existingId;
		    form.appendChild(hidden);
		  }
	    }

	    if (li && li._fileInput) li._fileInput.remove();
	    if (li) li.remove();
	  }

	  // ========== RETORT CONTROL SHEET ==========
	  if (e.target.classList.contains('retort-control-add-row')) {
	    const containerElem = document.querySelector('.retort-control-file-rows');
	    const list = document.querySelector('.retort-control-doc-list');
	    if (!containerElem || !list) return;

	    const input = document.createElement('input');
	    input.type = 'file';
	    input.name = 'retort_control_documents[]';
	    input.className = 'retort-control-file-input';
	    input.style.display = 'none';
	    input.accept = '.pdf,.doc,.docx';

	    input.addEventListener('change', function() {
		  if (!input.files || !input.files[0]) {
		    input.remove();
		    return;
		  }
		  const file = input.files[0];

		  const li = document.createElement('li');
		  li.className = 'retort-control-doc-item';
		  li.innerHTML = `
		    <span>${file.name}</span>
		    <button type="button"
				    class="retort-control-remove-row"
				    style="margin-left:5px; border:none; background:none; color:#d32f2f; font-weight:bold; cursor:pointer;">×</button>
		  `;
		  li._fileInput = input;
		  list.appendChild(li);
	    });

	    containerElem.appendChild(input);
	    input.click();
	  }

	  if (e.target.classList.contains('retort-control-remove-row')) {
	    const li = e.target.closest('.retort-control-doc-item');
	    const existingId = e.target.getAttribute('data-doc-id');

	    if (existingId) {
		  const form = document.getElementById('mainform');
		  if (form) {
		    const hidden = document.createElement('input');
		    hidden.type = 'hidden';
		    hidden.name = 'delete_retort_control_ids[]';
		    hidden.value = existingId;
		    form.appendChild(hidden);
		  }
	    }

	    if (li && li._fileInput) li._fileInput.remove();
	    if (li) li.remove();
	  }
    // ========== FINAL PRODUCT PACKAGING ==========
    if (e.target.classList.contains('final-packaging-add-row')) {
      const containerElem = document.querySelector('.final-packaging-file-rows');
      const list = document.querySelector('.final-packaging-doc-list');
      if (!containerElem || !list) return;

      const input = document.createElement('input');
      input.type = 'file';
      input.name = 'final_packaging_documents[]';
      input.style.display = 'none';
      input.accept = '.pdf,.doc,.docx';

      input.addEventListener('change', function() {
        if (!input.files || !input.files[0]) {
          input.remove();
          return;
        }
        const file = input.files[0];

        const li = document.createElement('li');
        li.className = 'final-packaging-doc-item';
        li.innerHTML = `
          <span>${file.name}</span>
          <button type="button"
                  class="final-packaging-remove-row"
                  style="margin-left:5px; border:none; background:none; color:#d32f2f; font-weight:bold; cursor:pointer;">×</button>
        `;
        li._fileInput = input;
        list.appendChild(li);
      });

      containerElem.appendChild(input);
      input.click();
    }

    if (e.target.classList.contains('final-packaging-remove-row')) {
      const li = e.target.closest('.final-packaging-doc-item');
      const existingId = e.target.getAttribute('data-doc-id');

      if (existingId) {
        const form = document.getElementById('mainform');
        if (form) {
          const hidden = document.createElement('input');
          hidden.type = 'hidden';
          hidden.name = 'delete_final_packaging_ids[]';
          hidden.value = existingId;
          form.appendChild(hidden);
        }
      }

      if (li && li._fileInput) li._fileInput.remove();
      if (li) li.remove();
    }
    // ========== INVENTORY BOOK OUT (SAUCE ITEMS) ==========
    if (e.target.classList.contains('sauce-item-bookout-add')) {
      const stockItemId = e.target.getAttribute('data-stock-item');
      const containerElem = document.querySelector(`.sauce-item-bookout-rows-${stockItemId}`);
      const list = document.querySelector(`.sauce-item-bookout-list-${stockItemId}`);
      if (!containerElem || !list) return;

      const input = document.createElement('input');
      input.type = 'file';
      input.name = `inventory_bookout_${stockItemId}[]`;
      input.style.display = 'none';
      input.accept = '.pdf,.doc,.docx';

      input.addEventListener('change', function() {
        if (!input.files || !input.files[0]) {
          input.remove();
          return;
        }
        const file = input.files[0];

        const li = document.createElement('li');
        li.className = 'sauce-item-bookout-item';
        li.innerHTML = `
          <span style="font-size: 11px;">${file.name}</span>
          <button type="button"
                  class="sauce-item-bookout-remove"
                  data-stock-item="${stockItemId}"
                  style="margin-left:5px; border:none; background:none; color:#d32f2f; font-weight:bold; cursor:pointer;">×</button>
        `;
        li._fileInput = input;
        list.appendChild(li);
      });

      containerElem.appendChild(input);
      input.click();
    }

    if (e.target.classList.contains('sauce-item-bookout-remove')) {
      const li = e.target.closest('.sauce-item-bookout-item');
      const stockItemId = e.target.getAttribute('data-stock-item');
      const existingId = e.target.getAttribute('data-doc-id');

      if (existingId) {
        const form = document.getElementById('mainform');
        if (form) {
          const hidden = document.createElement('input');
          hidden.type = 'hidden';
          hidden.name = `delete_inventory_bookout_${stockItemId}[]`;
          hidden.value = existingId;
          form.appendChild(hidden);
        }
      }

      if (li && li._fileInput) li._fileInput.remove();
      if (li) li.remove();
    }

    // ========== INVENTORY BOOK OUT (PACKAGING ITEMS) ==========
    if (e.target.classList.contains('pkg-item-bookout-add')) {
      const stockItemId = e.target.getAttribute('data-stock-item');
      const containerElem = document.querySelector(`.pkg-item-bookout-rows-${stockItemId}`);
      const list = document.querySelector(`.pkg-item-bookout-list-${stockItemId}`);
      if (!containerElem || !list) return;

      const input = document.createElement('input');
      input.type = 'file';
      input.name = `inventory_bookout_${stockItemId}[]`;
      input.style.display = 'none';
      input.accept = '.pdf,.doc,.docx';

      input.addEventListener('change', function() {
        if (!input.files || !input.files[0]) {
          input.remove();
          return;
        }
        const file = input.files[0];

        const li = document.createElement('li');
        li.className = 'pkg-item-bookout-item';
        li.innerHTML = `
          <span style="font-size: 11px;">${file.name}</span>
          <button type="button"
                  class="pkg-item-bookout-remove"
                  data-stock-item="${stockItemId}"
                  style="margin-left:5px; border:none; background:none; color:#d32f2f; font-weight:bold; cursor:pointer;">×</button>
        `;
        li._fileInput = input;
        list.appendChild(li);
      });

      containerElem.appendChild(input);
      input.click();
    }

    if (e.target.classList.contains('pkg-item-bookout-remove')) {
      const li = e.target.closest('.pkg-item-bookout-item');
      const stockItemId = e.target.getAttribute('data-stock-item');
      const existingId = e.target.getAttribute('data-doc-id');

      if (existingId) {
        const form = document.getElementById('mainform');
        if (form) {
          const hidden = document.createElement('input');
          hidden.type = 'hidden';
          hidden.name = `delete_inventory_bookout_${stockItemId}[]`;
          hidden.value = existingId;
          form.appendChild(hidden);
        }
      }

      if (li && li._fileInput) li._fileInput.remove();
      if (li) li.remove();
    }
	});
});
/* ============================================================ */
/* RENDER FUNCTIONS - BUILD TAB CONTENT */
/* ============================================================ */

function renderCertificationTab() {
  const certTab = document.getElementById('cert');
  if (!certTab) return;
  
  let html = `<div class="batch-cards" style="justify-content: center;">`;
  
  if (window.BATCH_DATA.all_batches) {
    window.BATCH_DATA.all_batches.forEach(batch => {
      html += `
        <div class="batch-card">
          <h4>${batch.batch_number} - ${batch.a_no}</h4>
          <div style="text-align: center; font-size: 12px; color: #666; margin-bottom: 10px;">
            Qty: <strong style="color: #0066cc;">${batch.shift_total}</strong>
          </div>
          <div class="form-group">
            <label>Status</label>
            <select name="status_${batch.batch_number}">
              <option value="">--select--</option>
              <option value="manufactured">Manufactured</option>
              <option value="in_incubation">In Incubation</option>
              <option value="awaiting_certification">Awaiting Certification</option>
              <option value="certified">Certified</option>
              <option value="ready_for_dispatch">Ready for Dispatch</option>
              <option value="dispatched">Dispatched</option>
              <option value="failed_drainmass">Failed Drainmass</option>
              <option value="failed_37c">Failed 37°C Micro Test</option>
              <option value="failed_55c">Failed 55°C Micro Test</option>
            </select>
          </div>
          <div class="form-group">
            <label>Incubation Start</label>
            <input type="date" name="incubation_start_${batch.batch_number}" class="cert-date-field">
          </div>
          <div class="form-group">
            <label>Incubation End</label>
            <input type="date" name="incubation_end_${batch.batch_number}" class="cert-date-field">
          </div>
          <div class="form-group">
            <label>NSI Submission</label>
            <input type="date" name="nsi_submission_date_${batch.batch_number}" class="cert-date-field">
          </div>
          <div class="form-group">
            <label>Certification Date</label>
            <input type="date" name="certification_date_${batch.batch_number}" class="cert-date-field">
          </div>
          <div class="form-group" style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #ccc;">
			<label>NSI Certificates</label>

			<ul class="nsi-doc-list" data-batch="${batch.batch_number}">
			</ul>

			<div class="nsi-file-rows" data-batch="${batch.batch_number}" style="display:none;"></div>

			<button type="button"
			        class="nsi-add-row"
					data-batch="${batch.batch_number}"
					style="margin-top:5px;">+ Add</button>

			<small style="color: #999; font-size: 10px;">PDF, DOC, DOCX</small>
		  </div>
        </div>
      `;
    });
  }

  html += `</div>`;
  certTab.innerHTML = html;
  
  // After rendering, populate existing NSI documents into the lists
  if (window.BATCH_DATA && window.BATCH_DATA.all_batches) {
    window.BATCH_DATA.all_batches.forEach(batch => {
      const docs = batch.nsi_documents || [];
      if (!docs.length) return;

      const list = document.querySelector(`.nsi-doc-list[data-batch="${batch.batch_number}"]`);
      if (!list) return;

      docs.forEach(doc => {
        const li = document.createElement('li');
        li.className = 'nsi-doc-item';
        li.innerHTML = `
		  <a href="${doc.url}" target="_blank">${doc.filename}</a>
		  <button type="button"
				  class="nsi-remove-row"
				  data-doc-id="${doc.id}"
				  style="margin-left:5px; border:none; background:none; color:#d32f2f; font-weight:bold; cursor:pointer;">×</button>
		`;
        list.appendChild(li);
      });
    });
  }
  
}

function loadMeatContainers() {
  const containersData = window.BATCH_DATA?.saved_batch_containers || [];
  
  if (containersData.length === 0) {
    return;
  }
  
  
  containersData.forEach((container, idx) => {
    // ✅ Use addContainerCard instead of addMeatRow
    const prevSource = window.currentMeatSource;
    window.currentMeatSource = container.source_type || 'import';
    addContainerCard();
    window.currentMeatSource = prevSource;
    
    // After card is created, populate its select and values
    const cards = document.querySelectorAll('.container-card');
    const card = cards[cards.length - 1];  // the one we just added
    
    const select = card.querySelector('select[name="container_id[]"]');
    if (select) {
      select.value = container.container_id;
      populateBookOutQty(select);
      updateBalanceFromPrevShift(select);
    }
    
    const bookOutInput = card.querySelector('input[name="book_out_qty[]"]');
    if (bookOutInput) {
      bookOutInput.value = container.book_out_qty || 0;
    }
    
    const stockLeftInput = card.querySelector('input[name="stock_left[]"]');
    if (stockLeftInput) {
      stockLeftInput.value = container.stock_left || 0;
    }
    
    setTimeout(() => {
      calculateDefrostedFresh(stockLeftInput);
    }, 50);
  });
  
  // Load defrost docs after ALL cards are created
  setTimeout(() => {
    const cards = document.querySelectorAll('.container-card');
    
    cards.forEach((card, idx) => {
      const containerData = containersData[idx];
      if (!containerData) return;

      const list = card.querySelector('.defrost-doc-list');
      if (!list) {

        return;
      }

      const docs = containerData.defrost_documents || [];
      
      docs.forEach(doc => {
        const li = document.createElement('li');
        li.className = 'defrost-doc-item';
        li.innerHTML = `
          <a href="${doc.url}" target="_blank">${doc.filename}</a>
          <button type="button"
                  class="defrost-remove-row"
                  data-doc-id="${doc.id}"
                  style="margin-left:5px; border:none; background:none; color:#d32f2f; font-weight:bold; cursor:pointer;">×</button>
        `;
        list.appendChild(li);
      });
    });
  }, 200);
}


// Then in loadSavedData(), call:
loadMeatContainers();

function renderMeatTab() {
  const meatTab = document.getElementById('meat');
  if (!meatTab) return;
  
  let html = `
    <div class="meat-tab-wrapper">
      <div class="meat-tab-content">
        <div class="container-section">
          <!-- Local/Import Toggle Buttons -->
          <div style="margin-bottom: 15px; display: flex; gap: 10px;">
            <button type="button" class="btn-source-toggle active"
                    onclick="switchMeatSourceAndAdd(event, 'import')" data-source="import">
              📦 Import
            </button>
            <button type="button" class="btn-source-toggle"
                    onclick="switchMeatSourceAndAdd(event, 'local')" data-source="local">
              🏭 Local
            </button>
          </div>

          <!-- Hidden template selects -->
          <select id="container-options-template-import" style="display: none;">
  `;
  
  // IMPORT OPTIONS
  if (window.BATCH_DATA.available_containers) {
    html += `<option value="">--select--</option>`;
    window.BATCH_DATA.available_containers.forEach(container => {
      html += `
        <option value="${container.pk}" 
                data-source="import">
          ${container.container_number}
        </option>
      `;
    });
  }
  
  html += `</select>
        
      <select id="container-options-template-local" style="display: none;">
  `;
  
  // LOCAL OPTIONS
  if (window.BATCH_DATA.available_stock_transactions) {
    html += `<option value="">--select--</option>`;
    window.BATCH_DATA.available_stock_transactions.forEach(trans => {
      html += `
        <option value="${trans.batch_ref}" 
                data-startingkg="${trans.net_weight}" 
                data-availablekg="${trans.available_stock}"
                data-source="local"
                data-reference="${trans.reference}">
          ${trans.reference}
        </option>
      `;
    });
  }
  
    html += `</select>

          <!-- Container cards go here -->
          <div class="container-row"></div>
        </div> <!-- /.container-section -->
      </div>   <!-- /.meat-tab-content -->

      <div class="meat-production-sidebar">
        <h4>📊 Meat Production Summary</h4>
        <div class="summary-item">
          <label>Total Meat Filled (kg)</label>
          <input type="number" name="total_meat_filled"
                 onchange="calculateWasteDefrostFilling();">
        </div>
        <div class="summary-item">
          <label>Filling Weight per Pouch (kg)</label>
          <input type="number" name="filling_weight_per_pouch"
                 value="0.277" step="0.001"
                 onchange="calculateWasteDefrostPouch();">
        </div>
        <div class="summary-item">
          <label>Total Waste (kg)</label>
          <input type="number" name="total_waste"
                 value="0" step="0.01"
                 onchange="calculateWasteDefrostPouch();">
        </div>
      </div> <!-- /.meat-production-sidebar -->
    </div>   <!-- /.meat-tab-wrapper -->
  `;
  
  meatTab.innerHTML = html;
  window.currentMeatSource = 'import';
  
  // ✅ LOAD ALL SAVED BALANCES AFTER CARDS ARE RENDERED
  setTimeout(() => {
    const selects = document.querySelectorAll('select[name="container_id[]"]');
    selects.forEach(select => {
      if (select.value) {
        updateBalanceFromPrevShift(select);
		calculateDefrostedFresh(select);  
      }
    });
  }, 100);
}

// ✅ ADD THIS FUNCTION to handle balance display in each card
function updateCardBalanceField(containerRef, fieldElement) {
  const balance = window.getBalanceFromPrevShift(containerRef);
  fieldElement.value = balance.toFixed(0);
}

function toggleAmendedOpening() {
  const checkbox = document.querySelector('input[name="cancel_opening_balance"]');
  const amendedInput = document.getElementById('amended_opening_input');

  if (!checkbox || !amendedInput) return;

  if (checkbox.checked) {
    amendedInput.disabled = false;
    amendedInput.focus();
  } else {
    amendedInput.disabled = true;
    amendedInput.value = '';
    calculateUsageForDay();
  }
}

function renderSauceTab() {
  const sauceTab = document.getElementById('sauce');
  if (!sauceTab) return;

  const recipes = window.BATCH_DATA.recipes || {};
  const sauceData = window.BATCH_DATA.saved_sauce_data || {};  
  const sauceOpenings = window.BATCH_DATA.sauce_recipe_openings || {};
  const savedRecipeItems = window.BATCH_DATA.saved_sauce_recipe_items || {};
  
  const currentProdDate = window.BATCH_DATA.production_date;
  const normalizedCurrent = normalizeDate(currentProdDate);
  
  let recipeItemsHTML = '';

  for (const recipeId in recipes) {
    const recipe = recipes[recipeId];
    const recipeItems = recipe.recipe_items || {};

    for (const recipeItemId in recipeItems) {
      const item = recipeItems[recipeItemId];
      const stock_item_id = item.stock_item_id || recipeItemId;
      const key = String(stock_item_id);
      
      const itemName = item.stock_item_name || `Item ${key}`;
      const unit = item.unit_of_measure_name || 'Litre';
      
      // ✅ Get sauce bookout data
	  const sauceItemData = window.BATCH_DATA?.sauce_recipe_bookouts?.[key] || {};

      // ✅ Calculate booked using getBookedQtyForItem with the STOCK ITEM 
      const booked = window.recipe_bookouts[String(item.stock_item_id)]?.booked_out_stock || 0;
      
      const opening = sauceOpenings[key]?.opening_balance || 0;
      
      // ✅ LOAD SAVED CHECKBOX STATE FROM DATABASE
      const savedItem = window.BATCH_DATA?.saved_sauce_recipe_items?.[key] || {};
      const isCancelChecked = savedItem.cancel_opening_use_bookout || false;
      
	  // Store both refs separately for dynamic switching
	  const batchRefBalance = sauceItemData.batch_ref_balance || '';
	  const batchRefBooked = sauceItemData.batch_ref_booked || '';
	  
	  // Calculate combined ref for display
	  let batchRefCombined = '';
	  if (batchRefBalance && batchRefBooked && batchRefBalance !== batchRefBooked) {
	    batchRefCombined = `${batchRefBalance} / ${batchRefBooked}`;
	  } else if (batchRefBooked) {
	    batchRefCombined = batchRefBooked;
	  } else if (batchRefBalance) {
	    batchRefCombined = batchRefBalance;
	  }
	  
	  // Display based on cancel checkbox state
	  const batchRefDisplay = isCancelChecked ? batchRefBooked : batchRefCombined;
	
     
	 recipeItemsHTML += `
        <div class="packaging-card" data-batch-ref-balance="${batchRefBalance}" data-batch-ref-booked="${batchRefBooked}" data-batch-ref-combined="${batchRefCombined}">
          <h4>${itemName}</h4>

          <div style="margin-bottom: 10px;">
            <label style="font-size: 11px; font-weight: bold;">Balance stock last production (${unit})</label>
            <input type="number"
				   name="sauce_opening_${item.stock_item_id}"
				   value="${opening}"
                   readonly
                   style="width: 100%; padding: 6px; background: #f5f5f5; font-weight: bold; border: 1px solid #ccc; border-radius: 3px;">
          </div>

          <div style="margin-bottom: 10px; padding: 8px; background: #fff3cd; border: 1px solid #ffc107; border-radius: 3px;">
            <label style="display: flex; align-items: center; margin: 0; font-weight: normal; font-size: 11px;">
              <input type="checkbox"
                     name="sauce_cancel_${item.stock_item_id}" 
                     class="sauce-cancel-checkbox"
                     data-stock-item="${item.stock_item_id}"
                     ${isCancelChecked ? 'checked' : ''}
                     style="margin-right: 8px; width: auto;">
              Cancel Opening use Book out
            </label>
          </div>

          <div style="margin-bottom: 10px;">
            <label style="font-size: 11px; font-weight: bold;">Reason</label>
            <textarea name="sauce_reason_${item.stock_item_id}" 
                      style="width: 100%; height: 50px; padding: 6px; font-size: 11px; border: 1px solid #ccc; border-radius: 3px; resize: vertical;">${savedItem.amended_reason || ''}</textarea>
          </div>

          <div style="margin-bottom: 10px;">
		    <label style="font-size: 11px; font-weight: bold;">Batch Ref Number</label>
		    <input type="text"
			   	   name="sauce_batch_ref_${item.stock_item_id}"
				   class="sauce-batch-ref-input"
				   value="${batchRefDisplay}"
				   readonly
				   style="width: 100%; min-width: 200px; padding: 6px; background: #ffffcc; font-weight: bold; text-align: center; border: 1px solid #ccc; border-radius: 3px; font-size: 12px !important;">
		  </div>

          <div style="margin-bottom: 10px;">
            <label style="font-size: 11px; font-weight: bold;">Booked out stock (${unit})</label>
            <input type="number"
				   name="sauce_booked_${item.stock_item_id}"
				   value="${booked}"
                   step="0.01"
                   class="sauce-booked-input"
                   readonly
                   style="width: 100%; padding: 6px; background-color: white !important; font-weight: bold; text-align: center; border: 1px solid #ccc; border-radius: 3px; color: #000 !important; font-size: 14px !important;">
          </div>

          <div style="margin-bottom: 10px;">
            <label style="font-size: 11px; font-weight: bold;">Stock balance unused (${unit})</label>
            <input type="number"
				   name="sauce_closing_${item.stock_item_id}"
				   value="${savedItem.closing_balance || 0}"             
				   step="0.01"
				   class="sauce-closing-input"
				   onchange="updateSauceItemUsage(this)"
				   style="width: 100%; padding: 6px; text-align: center; font-weight: bold; border: 1px solid #ccc; border-radius: 3px;">
          </div>

          <div style="background: #e8f4f8; border: 2px solid #417690; padding: 10px; border-radius: 3px;">
            <label style="font-size: 11px; font-weight: bold; color: #417690; display: block; margin-bottom: 6px;">Usage for Day (${unit})</label>
            <input type="text"
                   name="sauce_usage_${item.stock_item_id}" 
                   value="0.00"
                   readonly
                   style="width: 100%; padding: 6px; font-weight: bold; color: #417690; text-align: center; background: white; border: 1px solid #417690; border-radius: 3px; box-sizing: border-box;">
            <small style="display: block; font-size: 10px; color: #666; margin-top: 4px; text-align: center;">= Booked − Balance</small>
          </div>
          <div class="form-group" style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #ccc;">
            <label style="font-size: 11px; font-weight: bold;">Book Out Sheet</label>
            <ul class="sauce-item-bookout-list-${item.stock_item_id}" style="list-style: none; padding: 0 0 0 20px; margin: 5px 0;"></ul>
            <div class="sauce-item-bookout-rows-${item.stock_item_id}" style="display:none;"></div>
            <button type="button"
                    class="sauce-item-bookout-add"
                    data-stock-item="${item.stock_item_id}"
                    style="margin-top:5px; background: #417690; color: white; border: none; padding: 5px 10px; cursor: pointer; border-radius: 3px; font-size: 11px;">+ Add</button>
            <small style="color: #999; font-size: 10px; display: block; margin-top: 3px;">PDF, DOC, DOCX</small>
          </div>
        </div>
      `;
    }
  }

  if (!recipeItemsHTML) {
    recipeItemsHTML = `
      <div style="padding: 20px; text-align: center; color: #999; width: 100%;">
        <p>No recipe items configured.</p>
      </div>
    `;
  }

  // RIGHT: global Sauce Summary card (REAL persisted fields)
  const opening = sauceData.opening_balance || 0;
  const amendedOpening = sauceData.amended_opening_balance || 0;
  const cancelOpening = !!sauceData.cancel_opening_balance;
  const reason = sauceData.amended_reason || '';
  const mixed = sauceData.sauce_mixed || 0;
  const closing = sauceData.closing_balance || 0;

  const summaryCardHTML = `
    <div class="packaging-card" style="background: #fff5f7; border: 2px solid #e91e63;">
      <h4 style="color: #e91e63; text-align: center;">Recipe Summary</h4>

      <div style="margin-bottom: 10px;">
        <label style="font-size: 11px; font-weight: bold;">Opening Balance (L)</label>
        <label style="font-size: 10px; color: #999; display: block; margin-bottom: 4px;">From last recorded closing balance</label>
        <input type="number"
               name="opening_balance"
               value="${opening}"
               step="0.01"
               readonly
               style="width: 100%; padding: 8px; background: #f5f5f5; border: 1px solid #ccc; border-radius: 3px; font-size: 13px; box-sizing: border-box; text-align: center; font-weight: bold;">
      </div>

      <div style="margin-bottom: 10px; padding: 8px; background: #fff0f5; border: 1px solid #f0a0c0; border-radius: 3px;">
        <label style="display: flex; align-items: center; margin: 0; font-weight: normal; font-size: 11px;">
          <input type="checkbox"
                 name="cancel_opening_balance"
                 ${cancelOpening ? 'checked' : ''}
                 style="margin-right: 8px; width: auto;">
          Cancel Opening use Book out
        </label>
      </div>

      <div style="margin-bottom: 10px;">
        <label style="font-size: 11px; font-weight: bold;">Reason</label>
        <textarea name="amended_reason"
                  style="width: 100%; height: 50px; padding: 6px; border: 1px solid #ccc; border-radius: 3px; font-size: 11px; box-sizing: border-box; resize: vertical;">${reason}</textarea>
      </div>

      <div style="margin-bottom: 10px;">
        <label style="font-size: 11px; font-weight: bold;">Sauce Mixed (L)</label>
        <input type="number"
               name="sauce_mixed"
               value="${mixed}"
               step="0.01"
               onchange="syncSauceSummaryFromCards()"
               style="width: 100%; padding: 6px; text-align: center; border: 1px solid #ccc; border-radius: 3px; box-sizing: border-box;">
      </div>

      <div style="margin-bottom: 10px;">
        <label style="font-size: 11px; font-weight: bold;">Stock balance unused (L)</label>
        <input type="number"
               name="closing_balance"
               value="${closing}"
               step="0.01"
               onchange="syncSauceSummaryFromCards()"
               style="width: 100%; padding: 6px; text-align: center; font-weight: bold; border: 1px solid #ccc; border-radius: 3px; box-sizing: border-box;">
      </div>

      <div style="background: #e8f4f8; border: 2px solid #417690; padding: 10px; border-radius: 3px; margin-bottom: 10px;">
        <label style="font-size: 11px; font-weight: bold; color: #417690; display: block; margin-bottom: 6px;">Usage for Day (L)</label>
        <input type="text"
               name="usage_for_day"
               value="0.00"
               readonly
               style="width: 100%; padding: 6px; font-weight: bold; color: #417690; text-align: center; background: white; border: 1px solid #417690; border-radius: 3px; box-sizing: border-box;">
        <small style="display: block; font-size: 10px; color: #666; margin-top: 4px; text-align: center;">= Booked − Balance</small>
      </div>

      <!-- ✅ NEW: Recipe Documents Upload Section -->
      <div class="form-group" style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #e91e63;">
        <label style="font-size: 11px; font-weight: bold;">Recipe Documents</label>
        <ul class="recipe-doc-list"></ul>
        <div class="recipe-file-rows" style="display:none;"></div>
        <button type="button"
                class="recipe-add-row"
                style="margin-top:5px; background: #e91e63; color: white; border: none; padding: 6px 12px; cursor: pointer; border-radius: 3px;">+ Add</button>
        <small style="color: #999; font-size: 10px; display: block; margin-top: 4px;">PDF, DOC, DOCX</small>
      </div>
    </div>
  `;
  
  // Load existing recipe documents
  setTimeout(() => {
    const recipeDocs = window.BATCH_DATA?.saved_recipe_documents || [];
    const list = document.querySelector('.recipe-doc-list');
  
    if (list && recipeDocs.length > 0) {
      recipeDocs.forEach(doc => {
        const li = document.createElement('li');
        li.className = 'recipe-doc-item';
        li.innerHTML = `
          <a href="${doc.url}" target="_blank">${doc.filename}</a>
          <button type="button"
                  class="recipe-remove-row"
                  data-doc-id="${doc.id}"
                  style="margin-left:5px; border:none; background:none; color:#d32f2f; font-weight:bold; cursor:pointer;">×</button>
        `;
        list.appendChild(li);
      });
    }
  }, 100);


  // Full layout: left cards + right summary
  const html = `
    <div class="packaging-cards-container">
      ${recipeItemsHTML}
      ${summaryCardHTML}
    </div>
  `;

  sauceTab.innerHTML = html;
  attachSauceCardHandlers();

  // ✅ Load existing inventory book-out docs for sauce items
  setTimeout(() => {
    const inventoryDocs = window.BATCH_DATA?.saved_inventory_bookout_documents || {};
    
    for (const stockItemId in inventoryDocs) {
      const docs = inventoryDocs[stockItemId] || [];
      const list = document.querySelector(`.sauce-item-bookout-list-${stockItemId}`);
      
      if (list && docs.length > 0) {
        docs.forEach(doc => {
          const li = document.createElement('li');
          li.className = 'sauce-item-bookout-item';
          li.innerHTML = `
            <a href="${doc.url}" target="_blank" style="font-size: 11px;">${doc.filename}</a>
            <button type="button"
                    class="sauce-item-bookout-remove"
                    data-stock-item="${stockItemId}"
                    data-doc-id="${doc.id}"
                    style="margin-left:5px; border:none; background:none; color:#d32f2f; font-weight:bold; cursor:pointer;">×</button>
          `;
          list.appendChild(li);
        });
      }
    }
  }, 100);

  // ✅ AFTER rendering, manually set ALL booked values
  setTimeout(() => {
    const recipes = window.BATCH_DATA.recipes || {};
    
    for (const recipeId in recipes) {
      const recipe = recipes[recipeId];
      const recipeItems = recipe.recipe_items || {};

      for (const recipeItemId in recipeItems) {
        const item = recipeItems[recipeItemId];
        const stock_item_id = item.stock_item_id || recipeItemId;
        const key = String(stock_item_id);
        
        const sauceItemData = window.BATCH_DATA?.sauce_recipe_bookouts?.[key] || {};
        const batchRef = (sauceItemData.batch_ref && typeof sauceItemData.batch_ref === 'string')
          ? sauceItemData.batch_ref
          : (Array.isArray(sauceItemData.batch_ref) ? sauceItemData.batch_ref[0] : '');
        
        const booked = window.recipe_bookouts[String(item.stock_item_id)]?.booked_out_stock || 0;
        
        const input = document.querySelector(`input[name="sauce_booked_${item.stock_item_id}"]`);
        if (input) {
          input.value = booked;
        }
      }
    }
    
    updateAllSauceItemUsages();
    syncSauceSummaryFromCards();
  }, 50);
}

function attachSauceCardHandlers() {
  // Listen to closing input AND cancel checkbox
  document.querySelectorAll('.sauce-closing-input, .sauce-cancel-checkbox').forEach(input => {
    input.addEventListener('change', () => {
      updateAllSauceItemUsages();
      syncSauceSummaryFromCards();
    });
  });
  
  // ✅ ADD: Dynamic batch_ref update when cancel checkbox is toggled (SAUCE)
  document.querySelectorAll('.sauce-cancel-checkbox').forEach(checkbox => {
    checkbox.addEventListener('change', function() {
      const card = this.closest('.packaging-card');
      if (!card) return;
      
      const batchRefInput = card.querySelector('.sauce-batch-ref-input');
      if (!batchRefInput) return;
      
      const batchRefBalance = card.dataset.batchRefBalance || '';
      const batchRefBooked = card.dataset.batchRefBooked || '';
      const batchRefCombined = card.dataset.batchRefCombined || '';
      
      if (this.checked) {
        // Cancel checked: show ONLY booked ref
        batchRefInput.value = batchRefBooked;
      } else {
        // Cancel unchecked: show combined (or single)
        batchRefInput.value = batchRefCombined;
      }
    });
  });
  
  // Also listen to the global cancel checkbox
  const globalCancelCheckbox = document.querySelector('input[name="cancel_opening_balance"]');
  if (globalCancelCheckbox) {
    globalCancelCheckbox.addEventListener('change', () => {
      syncSauceSummaryFromCards();
    });
  }
  
  // Listen to sauce_mixed for real-time updates
  const mixedInput = document.querySelector('input[name="sauce_mixed"]');
  if (mixedInput) {
    mixedInput.addEventListener('change', () => {
      syncSauceSummaryFromCards();
    });
  }
}

function updateAllSauceItemUsages() {
  document.querySelectorAll('.packaging-card').forEach(card => {
    const openingEl = card.querySelector('input[name^="sauce_opening_"]');
    const bookedEl = card.querySelector('input[name^="sauce_booked_"]');
    const closingEl = card.querySelector('.sauce-closing-input');
    const cancelCheckbox = card.querySelector('.sauce-cancel-checkbox');
    const usageEl = card.querySelector('input[name^="sauce_usage_"]');
    
    if (!closingEl || !usageEl) return;
    
    const opening = parseFloat(openingEl?.value) || 0;
    const booked = parseFloat(bookedEl?.value) || 0;
    const closing = parseFloat(closingEl.value) || 0;
    const isCancelled = cancelCheckbox?.checked || false;
    
    let usage = 0;
    
    if (isCancelled) {
      // Cancel checked: skip opening, use booked if available
      if (booked > 0) {
        usage = booked - closing;
      } else {
        usage = 0 - closing;
      }
    } else {
      // Cancel NOT checked: use opening + booked if both available, else whichever is available
      if (opening > 0 && booked > 0) {
        usage = opening + booked - closing;
      } else if (opening > 0) {
        usage = opening - closing;
      } else if (booked > 0) {
        usage = booked - closing;
      } else {
        usage = 0 - closing;
      }
    }
    
    usageEl.value = usage.toFixed(2);
  });
}

function syncSauceSummaryFromCards() {
  const openingInput = document.querySelector('input[name="opening_balance"]');
  const mixedInput = document.querySelector('input[name="sauce_mixed"]');
  const closingInput = document.querySelector('input[name="closing_balance"]');
  const cancelCheckbox = document.querySelector('input[name="cancel_opening_balance"]');
  const usageForDayInput = document.getElementById('usage_for_day');

  if (!openingInput || !mixedInput || !closingInput || !usageForDayInput) return;

  const opening = parseFloat(openingInput.value) || 0;
  const mixed = parseFloat(mixedInput.value) || 0;
  const closing = parseFloat(closingInput.value) || 0;
  const isCancelled = cancelCheckbox?.checked || false;

  // If cancel is checked: usage = mixed - closing
  // Otherwise: usage = opening + mixed - closing
  const usage = isCancelled 
    ? (mixed - closing).toFixed(2)
    : (opening + mixed - closing).toFixed(2);

  usageForDayInput.value = usage;
}

function renderProcessingTab() {
  const processingTab = document.getElementById('processing');
  if (!processingTab) return;
  
  let batchRows = '';
  if (window.BATCH_DATA.all_batches) {
    window.BATCH_DATA.all_batches.forEach(batch => {
      batchRows += `
        <div style="border: 1px solid #ddd; padding: 12px; border-radius: 4px; background-color: #f9f9f9;">
          <h5 style="text-align: center; margin: 0 0 10px 0; font-size: 11px; color: #4a7c8c; font-weight: bold;">
            ${batch.batch_number}
          </h5>
          <div class="form-group" style="margin-bottom: 10px;">
            <label style="font-size: 11px;">NSI Sample Pouches</label>
            <input type="number" name="nsi_sample_pouches_${batch.batch_number}" placeholder="0" value="0" style="width: 100%; padding: 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 11px;">
          </div>
          <div class="form-group">
            <label style="font-size: 11px;">Retention Sample QTY</label>
            <input type="number" name="retention_sample_qty_${batch.batch_number}" placeholder="0" value="0" style="width: 100%; padding: 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 11px;">
          </div>
          <div class="form-group">
            <label style="font-size: 11px;">Unclear Coding</label>
            <input type="number" name="unclear_coding_${batch.batch_number}" placeholder="0" value="0" style="width: 100%; padding: 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 11px;">
          </div>
        </div>
      `;
    });
  }
  
  let html = `
    <div class="pouch-columns" style="display: flex; gap: 20px;">
	  <!-- MACHINE WASTE (LEFT) -->
	  <div class="pouch-column" style="flex: 1; min-width: 220px;">
		<h4>Machine Waste</h4>
		<div class="form-group">
		  <label>Machine Count</label>
		  <input type="number" name="machine_count" value="0">
		</div>
		<div class="form-group">
		  <label>Seal Creeps</label>
		  <input type="number" name="seal_creeps" value="0" onchange="calculateMachineTotal()">
		</div>
		<div class="form-group">
		  <label>Unsealed/Poor Seal</label>
		  <input type="number" name="unsealed_poor_seal" value="0" onchange="calculateMachineTotal()">
		</div>
		<div class="form-group">
		  <label>Screwed/Undated</label>
		  <input type="number" name="screwed_and_undated" value="0" onchange="calculateMachineTotal()">
		</div>
		<div class="form-group">
		  <label>Over Weight</label>
		  <input type="number" name="over_weight" value="0" onchange="calculateMachineTotal()">
		</div>
		<div class="form-group">
		  <label>Under Weight</label>
		  <input type="number" name="under_weight" value="0" onchange="calculateMachineTotal()">
		</div>
		<div class="form-group">
		  <label>Empty Pouches</label>
		  <input type="number" name="empty_pouches" value="0" onchange="calculateMachineTotal()">
		</div>
		<div class="form-group">
		  <label>Metal Detection</label>
		  <input type="number" name="metal_detection" value="0" onchange="calculateMachineTotal()">
		</div>
		<div class="total-box">
		  <label>Total Machine Waste</label>
		  <input type="text" id="machine_total" readonly style="font-weight:bold; color:#417690;">
		</div>
      <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd;">
        <label style="font-size: 12px; font-weight: bold; color: #417690;">📄 Machine Production Documents</label>
        <ul class="machine-production-doc-list" style="list-style: none; padding: 0 0 0 20px; margin: 10px 0;"></ul>
        <div class="machine-production-file-rows" style="display:none;"></div>
        <button type="button"
                class="machine-production-add-row"
                style="margin-top:5px; background: #417690; color: white; border: none; padding: 6px 12px; cursor: pointer; border-radius: 3px;">+ Add</button>
        <small style="color: #999; font-size: 10px; display: block; margin-top: 4px;">PDF, DOC, DOCX</small>
      </div>
	  </div>

	  <!-- RETORT WASTE (CENTER) - WITH YELLOW BOX ON TOP -->
	  <div class="pouch-column" style="flex: 1; min-width: 220px;">
		<!-- YELLOW RETORT READY BOX (TOP) -->
		<div style="background-color: #fff9e6; border: 2px solid #ffc107; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
		  <h4 style="color: #ff6f00; margin-top: 0; text-align: center;">Retort Ready</h4>
		  <div style="display: flex; gap: 10px; align-items: center; margin-bottom: 10px; font-size: 13px;">
			<span style="flex: 1;">Machine Count:</span>
			<span style="font-weight: bold; min-width: 80px; text-align: right;" id="display_machine_count">0</span>
		  </div>
		  <div style="display: flex; gap: 10px; align-items: center; margin-bottom: 10px; font-size: 13px; border-bottom: 1px solid #ffc107; padding-bottom: 10px;">
			<span style="flex: 1;">- Total Machine Waste:</span>
			<span style="font-weight: bold; min-width: 80px; text-align: right;" id="display_machine_waste">0</span>
		  </div>
		  <div style="display: flex; gap: 10px; align-items: center; font-size: 14px; font-weight: bold; color: #ff6f00;">
			<span style="flex: 1;">=  Ready for Retort:</span>
			<span style="min-width: 80px; text-align: right;" id="display_retort_ready">0</span>
		  </div>
		</div>

		<!-- RETORT WASTE FIELDS (BELOW) -->
		<h4>Retort Waste</h4>
		<div class="form-group">
		  <label>Retort Count</label>
		  <input type="number" name="retort_count" value="0">
		</div>
		<div class="form-group">
		  <label>Unclear Coding (Total from Retort)</label>
		  <input type="number" name="total_unclear_coding" value="0" onchange="calculateRetortTotal()">
		</div>
		<div class="form-group">
		  <label>Seal Creap</label>
		  <input type="number" name="retort_seal_creap" value="0" onchange="calculateRetortTotal()">
		</div>
		<div class="form-group">
		  <label>Under Weight</label>
		  <input type="number" name="retort_under_weight" value="0" onchange="calculateRetortTotal()">
		</div>
		<div class="form-group">
		  <label>Poor Ceiling Destroyed</label>
		  <input type="number" name="poor_ceiling_destroyed" value="0" onchange="calculateRetortTotal()">
		</div>
		<div class="total-box">
		  <label>Total Retort Waste</label>
		  <input type="text" id="retort_total" readonly style="font-weight:bold; color:#417690;">
		</div>
      <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd;">
        <label style="font-size: 12px; font-weight: bold; color: #417690;">📄 Retort Control Sheet Documents</label>
        <ul class="retort-control-doc-list" style="list-style: none; padding: 0 0 0 20px; margin: 10px 0;"></ul>
        <div class="retort-control-file-rows" style="display:none;"></div>
        <button type="button"
                class="retort-control-add-row"
                style="margin-top:5px; background: #417690; color: white; border: none; padding: 6px 12px; cursor: pointer; border-radius: 3px;">+ Add</button>
        <small style="color: #999; font-size: 10px; display: block; margin-top: 4px;">PDF, DOC, DOCX</small>
      </div>
	  </div>

	  <!-- SAMPLES (RIGHT) -->
	  <div class="pouch-column" style="flex: 1; min-width: 220px;">
		<h4 style="color: #357eab;">Samples</h4>
		<div style="display: flex; flex-direction: column; gap: 12px; margin-bottom: 16px;">
		  ${batchRows}
		</div>
		
		<!-- ✅ DYNAMIC NSI SAMPLE LOG UPLOADS - Better positioned -->
		<div style="padding: 15px 15px 15px 25px; background-color: #f0f8ff; border: 2px solid #0277bd; border-radius: 6px; margin-top: 20px; margin-right: 20px;">
		  <label style="font-size: 12px; font-weight: bold; color: #0277bd; display: block; text-align: center; margin-bottom: 10px;">📄 NSI Sample Log Documents</label>
		  <small style="display: block; font-size: 10px; color: #666; text-align: center; margin-bottom: 10px;">Combined Documents for All Batches</small>
		  
		  <ul class="nsi-sample-log-doc-list" style="list-style: none; padding: 0 0 0 10px; margin: 0 0 10px 0;"></ul>
		  <div class="nsi-sample-log-file-rows" style="display:none;"></div>
		  
		  <div style="text-align: center;">
			<button type="button"
					class="nsi-sample-log-add-row"
					style="background: #0277bd; color: white; border: none; padding: 8px 16px; cursor: pointer; border-radius: 4px; font-size: 12px; font-weight: 500;">+ Add</button>
		  </div>
		  <small style="color: #999; font-size: 10px; display: block; text-align: center; margin-top: 8px;">PDF, DOC, DOCX</small>
		</div>
	  </div>
	</div>

  `;
  
  processingTab.innerHTML = html;
  
  // ✅ Load NSI sample log documents IMMEDIATELY after innerHTML (not in setTimeout)
  const sampleLogDocs = window.BATCH_DATA?.saved_nsi_sample_log_documents || [];
  const list = document.querySelector('.nsi-sample-log-doc-list');
  
  if (list && sampleLogDocs.length > 0) {
    sampleLogDocs.forEach(doc => {
      const li = document.createElement('li');
      li.className = 'nsi-sample-log-doc-item';
      li.innerHTML = `
        <a href="${doc.url}" target="_blank">${doc.filename}</a>
        <button type="button"
                class="nsi-sample-log-remove-row"
                data-doc-id="${doc.id}"
                style="margin-left:5px; border:none; background:none; color:#d32f2f; font-weight:bold; cursor:pointer;">×</button>
      `;
      list.appendChild(li);
    });
  }
  
  // Load existing machine production documents
  const machineDocs = window.BATCH_DATA?.saved_machine_production_documents || [];
  const machineList = document.querySelector('.machine-production-doc-list');

  if (machineList && machineDocs.length > 0) {
    machineDocs.forEach(doc => {
      const li = document.createElement('li');
      li.className = 'machine-production-doc-item';
      li.innerHTML = `
        <a href="${doc.url}" target="_blank">${doc.filename}</a>
        <button type="button"
                class="machine-production-remove-row"
                data-doc-id="${doc.id}"
                style="margin-left:5px; border:none; background:none; color:#d32f2f; font-weight:bold; cursor:pointer;">×</button>
      `;
      machineList.appendChild(li);
    });
  }

  // Load existing retort control documents
  const retortDocs = window.BATCH_DATA?.saved_retort_control_documents || [];
  const retortList = document.querySelector('.retort-control-doc-list');

  if (retortList && retortDocs.length > 0) {
    retortDocs.forEach(doc => {
      const li = document.createElement('li');
      li.className = 'retort-control-doc-item';
      li.innerHTML = `
        <a href="${doc.url}" target="_blank">${doc.filename}</a>
        <button type="button"
                class="retort-control-remove-row"
                data-doc-id="${doc.id}"
                style="margin-left:5px; border:none; background:none; color:#d32f2f; font-weight:bold; cursor:pointer;">×</button>
      `;
      retortList.appendChild(li);
    });
  }
}

// ✅ CONVERT DATE FORMAT - handle both MM/DD/YYYY and YYYY-MM-DD
function normalizeDate(dateStr) {
    if (!dateStr) return null;
    dateStr = String(dateStr).trim();
    
    // Already YYYY-MM-DD format
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
        return dateStr;
    }
    
    // MM/DD/YYYY format - convert to YYYY-MM-DD
    if (/^\d{1,2}\/\d{1,2}\/\d{4}$/.test(dateStr)) {
        const parts = dateStr.split('/');
        const month = parts[0].padStart(2, '0');
        const day = parts[1].padStart(2, '0');
        const year = parts[2];
        return `${year}-${month}-${day}`;
    }
    
    // Try parsing as date
    const date = new Date(dateStr);
    if (!isNaN(date.getTime())) {
        return date.toISOString().split('T')[0];
    }
    
    return null;
}

// ✅ GET PREVIOUS PRODUCTION DATE (FIXED FORMAT)
function getPreviousProductionDate(currentProductionDate) {
    if (!window.BATCH_DATA?.all_batches) return null;
    
    const normalizedCurrent = normalizeDate(currentProductionDate);
    
    const allDates = [...new Set(
        window.BATCH_DATA.all_batches
            .map(b => normalizeDate(b.production_date))
            .filter(d => d !== null)
    )].sort().reverse();
    
    
    for (const date of allDates) {
        if (date < normalizedCurrent) {
            return date;
        }
    }
    return null;
}

// ✅ GET BATCH REFS - STORED + NEW ONES FROM TRANSACTIONS (DATE FILTERED)
function getBatchRefsForItem(itemId, currentProdDate, previousProdDate) {
    const packageData = window.BATCH_DATA?.packaging_data || {};
    const transactions = window.BATCH_DATA?.stock_transactions || [];
    
    const pkgItem = packageData[String(itemId)];
    if (!pkgItem) return '';
    
    const normalizedCurrent = normalizeDate(currentProdDate);
    const normalizedPrevious = previousProdDate ? normalizeDate(previousProdDate) : null;
    
    // Start with stored batch_ref
    const batchRefs = new Set();
    const storedBatchRef = pkgItem.batch_ref_balance || pkgItem.batch_ref || '';
    
    if (storedBatchRef) {
        batchRefs.add(storedBatchRef);
    }
    
    // Find DIFFERENT batch_refs in OUT transactions BETWEEN dates
    for (const txn of transactions) {
        if (txn.transaction_type === 'OUT' && txn.batch_ref) {
            const txnDate = txn.transaction_date ? normalizeDate(txn.transaction_date) : null;
            
            if (!txnDate) continue;
            
            // Check if transaction is in the date range
            const isInRange = 
                (!normalizedPrevious || txnDate > normalizedPrevious) &&
                (txnDate <= normalizedCurrent);
            
            // Only add if DIFFERENT from stored AND in date range
            if (isInRange && txn.batch_ref !== storedBatchRef) {
                batchRefs.add(txn.batch_ref);
            }
        }
    }
    
    const result = Array.from(batchRefs).join(', ');
    return result;
}


// ✅ NEW HELPER FUNCTION - Calculate booked for specific batch_ref
function getBookedQtyForItem(stockItemId, batchRef, normalizedCurrent) {
    if (!batchRef) return 0;  // If no batch ref, no booked qty
    
    const txns = window.BATCH_DATA?.stock_transactions || [];
    
    // Find all OUT transactions matching:
    // - This stock_item_id
    // - This batch_ref  
    // - Before or on current prod date
    const matching = txns.filter(t => {
        if (t.transaction_type !== 'OUT') return false;
        if (String(t.stock_item_id) !== String(stockItemId)) return false;
        if (t.batch_ref !== batchRef) return false;
        
        const txnDate = normalizeDate(t.transaction_date);
        return txnDate && txnDate <= normalizedCurrent;
    });
    
    const total = matching.reduce((sum, t) => sum + (parseFloat(t.quantity) || 0), 0);
    return total;
}

// ✅ CORRECTED - Match by batch_ref (NOT stock_item_id)
function getBookedQtyForItem(stockItemId, batchRef, normalizedCurrent) {
    if (!batchRef) return 0;
    
    const txns = window.BATCH_DATA?.stock_transactions || [];
    
    // ✅ Split batch ref by "/" and try each part
    const batchRefParts = batchRef.split('/').map(b => b.trim());
    
    const matching = txns.filter(t => {
        if (t.transaction_type !== 'OUT') return false;
        
        // ✅ Check if transaction batch_ref matches ANY part of the saved batch_ref
        const isMatch = batchRefParts.some(part => t.batch_ref.trim() === part);
        if (!isMatch) return false;
        
        const txnDate = normalizeDate(t.transaction_date);
        if (!txnDate) return false;
        
        const currentDate = normalizeDate(normalizedCurrent);
        return txnDate <= currentDate;
    });
    
    if (matching.length === 0) return 0;
    
    matching.sort((a, b) => {
        const dateA = normalizeDate(a.transaction_date);
        const dateB = normalizeDate(b.transaction_date);
        return dateB.localeCompare(dateA);
    });
    
    const latest = matching[0];
    const qty = parseFloat(latest.quantity) || 0;
    
    return qty;
}

function renderPackagingTab() {
  const packagingTab = document.getElementById('packaging');
  if (!packagingTab) return;
  
  const packagingItems = window.BATCH_DATA?.saved_packaging_data || {};
  const currentProdDate = window.BATCH_DATA.production_date;
  const normalizedCurrent = normalizeDate(currentProdDate);
  
  let html = `<div class="packaging-cards-container">`;
  
  if (Object.keys(packagingItems).length === 0) {
    html += `<div>No packaging items configured.</div>`;
  } else {
    for (const stockItemId in packagingItems) {
      const data = packagingItems[stockItemId];
      const itemName = data.stock_item_name || `Item ${stockItemId}`;
      
      const opening = data.opening_balance || 0;
      const closingBalance = data.closing_balance || 0;
      const savedReason = data.amended_reason || '';
      
      // ✅ Get both batch refs separately for dynamic switching
      const batchRefBalance = data.batch_ref_balance || '';
      const batchRefBooked = data.batch_ref_booked || '';
      const isCancelChecked = data.cancel_opening_use_bookout || false;
      
      // Calculate combined ref
      let batchRefCombined = '';
      if (batchRefBalance && batchRefBooked && batchRefBalance !== batchRefBooked) {
        batchRefCombined = `${batchRefBalance} / ${batchRefBooked}`;
      } else if (batchRefBooked) {
        batchRefCombined = batchRefBooked;
      } else if (batchRefBalance) {
        batchRefCombined = batchRefBalance;
      }
      
      // Display based on cancel checkbox state
      const batchRef = isCancelChecked ? batchRefBooked : batchRefCombined;
      
      // ✅ Calculate booked
      const booked = window.complete_packaging_data[stockItemId]?.booked_out_stock || 0;
     
      
      html += `
        <div class="packaging-card" data-batch-ref-balance="${batchRefBalance}" data-batch-ref-booked="${batchRefBooked}" data-batch-ref-combined="${batchRefCombined}">
          <h4>${itemName}</h4>
          
          <div style="margin-bottom: 10px; text-align: center;">
            <label style="font-size: 11px; font-weight: bold; display: block; margin-bottom: 4px;">Balance stock last production (Unit)</label>
            <input type="number" name="pkg_opening_${stockItemId}" value="${opening}" readonly style="width: 100%; padding: 6px; background: #f5f5f5; font-weight: bold; text-align: center; border: 1px solid #ccc; border-radius: 3px;">
          </div>
          
          <div style="margin-bottom: 10px; padding: 8px; background: #fff3cd; border: 1px solid #ffc107; border-radius: 3px;">
            <label style="display: flex; align-items: center; margin: 0; font-weight: normal; font-size: 11px;">
              <input type="checkbox" name="pkg_cancel_${stockItemId}" class="pkg-cancel-checkbox" data-stock-item="${stockItemId}" ${isCancelChecked ? 'checked' : ''} style="margin-right: 8px; width: auto;">
              Cancel Opening use Book out
            </label>
          </div>
          
          <div style="margin-bottom: 10px;">
            <label style="font-size: 11px; font-weight: bold;">Reason</label>
            <textarea name="pkg_reason_${stockItemId}" style="width: 100%; height: 50px; padding: 6px; font-size: 11px; border: 1px solid #ccc; border-radius: 3px; resize: vertical;">${savedReason}</textarea>
          </div>

          <div style="margin-bottom: 10px;">
            <label style="font-size: 11px; font-weight: bold;">Batch Ref Number</label>
            <input type="text" name="pkg_batch_ref_${stockItemId}" class="pkg-batch-ref-input" value="${batchRef}" readonly style="width: 100%; padding: 6px; background: #ffffcc; font-weight: bold; text-align: center; border: 1px solid #ccc; border-radius: 3px;">
          </div>
          
          <div style="margin-bottom: 10px;">
	 	    <label style="font-size: 11px; font-weight: bold;">Booked out stock (Unit)</label>
            <input type="number" name="pkg_booked_${stockItemId}" value="${booked}" readonly class="pkg-booked-input" style="width: 100%; padding: 6px; background-color: white !important; font-weight: bold; text-align: center; border: 1px solid #ccc; border-radius: 3px; color: #000 !important; font-size: 14px !important;">
		  </div>
				  
          <div style="margin-bottom: 10px;">
            <label style="font-size: 11px; font-weight: bold;">Stock balance unused (Unit)</label>
            <input type="number" name="pkg_closing_${stockItemId}" value="${closingBalance}" step="0.01" class="pkg-closing-input" style="width: 100%; padding: 6px; text-align: center; font-weight: bold; border: 1px solid #ccc; border-radius: 3px;">
          </div>
          
          <div style="background: #e8f4f8; border: 2px solid #417690; padding: 10px; border-radius: 3px;">
            <label style="font-size: 11px; font-weight: bold; color: #417690; display: block; margin-bottom: 6px;">Usage for Day (Unit)</label>
            <input type="text" name="pkg_usage_${stockItemId}" value="0.00" readonly style="width: 100%; padding: 6px; font-weight: bold; color: #417690; text-align: center; background: white; border: 1px solid #417690; border-radius: 3px; box-sizing: border-box;">
            <small style="display: block; font-size: 10px; color: #666; margin-top: 4px; text-align: center;">= Booked - Balance</small>
          </div>
          <div class="form-group" style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #ccc;">
            <label style="font-size: 11px; font-weight: bold;">Book Out Sheet</label>
            <ul class="pkg-item-bookout-list-${stockItemId}" style="list-style: none; padding: 0 0 0 20px; margin: 5px 0;"></ul>
            <div class="pkg-item-bookout-rows-${stockItemId}" style="display:none;"></div>
            <button type="button"
                    class="pkg-item-bookout-add"
                    data-stock-item="${stockItemId}"
                    style="margin-top:5px; background: #417690; color: white; border: none; padding: 5px 10px; cursor: pointer; border-radius: 3px; font-size: 11px;">+ Add</button>
            <small style="color: #999; font-size: 10px; display: block; margin-top: 3px;">PDF, DOC, DOCX</small>
          </div>
        </div>
      `;
    }
  }
  
  html += `</div>`;
  
  html += `
    <div class="packaging-upload-wrapper" style="margin-top: 30px; padding: 20px; background: #f0f8ff; border: 2px solid #0277bd; border-radius: 6px;">
      <label style="font-size: 13px; font-weight: bold; color: #0277bd; display: block; text-align: center; margin-bottom: 10px;">📦 Final Product Packaging Documents</label>
      <small style="display: block; font-size: 10px; color: #666; text-align: center; margin-bottom: 15px;">Combined Documents for All Batches</small>
      
      <ul class="final-packaging-doc-list" style="list-style: none; padding: 0 0 0 10px; margin: 0 auto 10px auto; max-width: 350px;"></ul>
      <div class="final-packaging-file-rows" style="display:none;"></div>
      
      <div style="text-align: center;">
        <button type="button"
                class="final-packaging-add-row"
                style="background: #0277bd; color: white; border: none; padding: 8px 16px; cursor: pointer; border-radius: 4px; font-size: 12px; font-weight: 500;">+ Add</button>
      </div>
      <small style="color: #999; font-size: 10px; display: block; text-align: center; margin-top: 8px;">PDF, DOC, DOCX</small>
    </div>
  `;
  
  packagingTab.innerHTML = html;
  attachPackagingCardHandlers();
  
  // ✅ Load existing inventory book-out docs for packaging items
  const inventoryDocs = window.BATCH_DATA?.saved_inventory_bookout_documents || {};

  for (const stockItemId in inventoryDocs) {
    const docs = inventoryDocs[stockItemId] || [];
    const list = document.querySelector(`.pkg-item-bookout-list-${stockItemId}`);
    
    if (list && docs.length > 0) {
      docs.forEach(doc => {
        const li = document.createElement('li');
        li.className = 'pkg-item-bookout-item';
        li.innerHTML = `
          <a href="${doc.url}" target="_blank" style="font-size: 11px;">${doc.filename}</a>
          <button type="button"
                  class="pkg-item-bookout-remove"
                  data-stock-item="${stockItemId}"
                  data-doc-id="${doc.id}"
                  style="margin-left:5px; border:none; background:none; color:#d32f2f; font-weight:bold; cursor:pointer;">×</button>
        `;
        list.appendChild(li);
      });
    }
  }

  // Load existing final product packaging documents
  const finalPackagingDocs = window.BATCH_DATA?.saved_final_packaging_documents || [];
  const finalPackagingList = document.querySelector('.final-packaging-doc-list');

  if (finalPackagingList && finalPackagingDocs.length > 0) {
    finalPackagingDocs.forEach(doc => {
      const li = document.createElement('li');
      li.className = 'final-packaging-doc-item';
      li.innerHTML = `
        <a href="${doc.url}" target="_blank">${doc.filename}</a>
        <button type="button"
                class="final-packaging-remove-row"
                data-doc-id="${doc.id}"
                style="margin-left:5px; border:none; background:none; color:#d32f2f; font-weight:bold; cursor:pointer;">×</button>
      `;
      finalPackagingList.appendChild(li);
    });
  }

  // ✅ AFTER rendering, manually set ALL booked values
  setTimeout(() => {
    const currentProdDate = window.BATCH_DATA.production_date;
    const normalizedCurrent = normalizeDate(currentProdDate);
    const packagingItems = window.BATCH_DATA?.saved_packaging_data || {};
  
    for (const stockItemId in packagingItems) {
      const data = packagingItems[stockItemId];
      const batchRef = data.batch_ref || '';
      const booked = window.complete_packaging_data[stockItemId]?.booked_out_stock || 0;
    
      const input = document.querySelector(`input[name="pkg_booked_${stockItemId}"]`);
      if (input) {
        input.value = booked;
      }
    }
  
    updateAllPackagingItemUsages();
  }, 50);
}

function attachPackagingCardHandlers() {
  document.querySelectorAll('.pkg-closing-input, .pkg-cancel-checkbox').forEach(input => {
    input.addEventListener('change', () => {
      updateAllPackagingItemUsages();
    });
  });
  
  // ✅ ADD: Dynamic batch_ref update when cancel checkbox is toggled (PACKAGING)
  document.querySelectorAll('.pkg-cancel-checkbox').forEach(checkbox => {
    checkbox.addEventListener('change', function() {
      const card = this.closest('.packaging-card');
      if (!card) return;
      
      const batchRefInput = card.querySelector('.pkg-batch-ref-input');
      if (!batchRefInput) return;
      
      const batchRefBalance = card.dataset.batchRefBalance || '';
      const batchRefBooked = card.dataset.batchRefBooked || '';
      const batchRefCombined = card.dataset.batchRefCombined || '';
      
      if (this.checked) {
        // Cancel checked: show ONLY booked ref
        batchRefInput.value = batchRefBooked;
      } else {
        // Cancel unchecked: show combined (or single)
        batchRefInput.value = batchRefCombined;
      }
    });
  });
}

function updateAllPackagingItemUsages() {
  document.querySelectorAll('.packaging-card').forEach(card => {
    const openingEl = card.querySelector('input[name^="pkg_opening_"]');
    const bookedEl = card.querySelector('.pkg-booked-input');
    const closingEl = card.querySelector('.pkg-closing-input');
    const cancelCheckbox = card.querySelector('.pkg-cancel-checkbox');
    const usageEl = card.querySelector('input[name^="pkg_usage_"]');
    
    if (!closingEl || !usageEl) return;
    
    const opening = parseFloat(openingEl?.value) || 0;
    const booked = parseFloat(bookedEl?.value) || 0;
    const closing = parseFloat(closingEl.value) || 0;
    const isCancelled = cancelCheckbox?.checked || false;
    
    let usage = 0;
    
    if (isCancelled) {
      // Cancel checked: skip opening, use booked if available
      if (booked > 0) {
        usage = booked - closing;
      } else {
        usage = 0 - closing;
      }
    } else {
      // Cancel NOT checked: use opening + booked if both available, else whichever is available
      if (opening > 0 && booked > 0) {
        usage = opening + booked - closing;
      } else if (opening > 0) {
        usage = opening - closing;
      } else if (booked > 0) {
        usage = booked - closing;
      } else {
        usage = 0 - closing;
      }
    }
    
    usageEl.value = usage.toFixed(2);
  });
}


function renderDowntimeTab() {
  const downTimeTab = document.getElementById('downtime');  
  if (!downTimeTab) return;
  
  let html = `
    <div style="max-width: 775px; margin: 0 auto;">
      <div class="form-group">
        <label>Total Down Time (Min)</label>
        <input type="number" name="total_down_time" placeholder="e.g., 25" value="0">
      </div>

      <div class="form-group">
        <label>Reasons for Down Time</label>
        <textarea name="reasons_for_down_time" style="width: 100%; height: 150px; padding: 8px; border: 1px solid #ccc; border-radius: 3px;"></textarea>
      </div>
    </div>
  `;
  
  downTimeTab.innerHTML = html;
}

function renderProductTab() {
  const productTab = document.getElementById('product');
  if (!productTab) return;
  
  let html = `
    <div style="max-width: 1050px; margin: 0 auto;">
      <table style="width: 100%; border-collapse: collapse; margin-bottom: 30px;">
        <tr>
          <th style="text-align: center; padding: 12px 15px; background-color: #4a7c8c; color: white; font-weight: bold;">Item</th>
          <th style="text-align: center; padding: 12px 15px; background-color: #4a7c8c; color: white; font-weight: bold;">Unit</th>
          <th style="text-align: center; padding: 12px 15px; background-color: #4a7c8c; color: white; font-weight: bold;">Ideal</th>
          <th style="text-align: center; padding: 12px 15px; background-color: #4a7c8c; color: white; font-weight: bold;">Used</th>
          <th style="text-align: center; padding: 12px 15px; background-color: #4a7c8c; color: white; font-weight: bold;">Batch Ref</th>
        </tr>
        <tr>
          <td colspan="5" style="text-align: center; padding: 20px; color: #999;">
            Product usage data will be displayed here. This is a summary tab.
          </td>
        </tr>
      </table>
    </div>
  `;
  
  productTab.innerHTML = html;
}

/* ============================================================ */
/* RENDER SUMMARY TAB */
/* ============================================================ */

function renderSummaryTab() {
  const summaryTab = document.getElementById('product');
  if (!summaryTab) return;
  
  // ✅ GET PACKAGING INFO (now available from window.BATCH_DATA)
  const packagingInfo = window.BATCH_DATA.packaging_info || {};
  
  // Combine ALL stock items from ALL sources
  const allItems = {};
  
  // 1. MAIN PRODUCT COMPONENTS
  const mainComponents = window.BATCH_DATA.main_product_components || {};
  for (const id in mainComponents) {
    const item = mainComponents[id];
    allItems[`main_${item.stock_item_id}`] = {
      stock_item_name: item.stock_item_name,
      unit: item.unit_of_measure_name || 'Unit',
      type: 'Main Component'
    };
  }
  
  // 2. PRODUCT COMPONENTS (ALL categories)
  const productComponents = window.BATCH_DATA.components || {};
  for (const id in productComponents) {
    const item = productComponents[id];
    const key = `comp_${item.stock_item_id}`;
    if (!(key in allItems)) {
      allItems[key] = {
        stock_item_name: item.stock_item_name,
        unit: item.unit_of_measure_name || 'Unit',
        type: 'Component'
      };
    }
  }
  
  // 3. RECIPE ITEMS (from ALL recipes)
  const recipes = window.BATCH_DATA.recipes || {};
  for (const recipeId in recipes) {
    const recipe = recipes[recipeId];
    const recipeItems = recipe.recipe_items || {};
    for (const itemId in recipeItems) {
      const item = recipeItems[itemId];
      const key = `recipe_${item.stock_item_id}`;
      if (!(key in allItems)) {
        allItems[key] = {
          stock_item_name: item.stock_item_name,
          unit: item.unit_of_measure_name || 'Unit',
          type: `Recipe (${recipe.recipe_name})`
        };
      }
    }
  }
  
  
  // Build table rows
  let tableRows = '';
  for (const itemKey in allItems) {
    const item = allItems[itemKey];
    tableRows += `
      <tr style="background: white;">
        <td style="padding: 8px; font-size: 11px; border: 1px solid #ccc;">${item.stock_item_name}</td>
        <td style="padding: 8px; font-size: 11px; text-align: center; border: 1px solid #ccc;">${item.unit}</td>
        <td style="padding: 8px; text-align: center; border: 1px solid #ccc;">
          <input type="number" name="summary_ideal_${itemKey}" value="0" step="0.01" readonly style="width: 90px; padding: 4px; text-align: center; border: 1px solid #ccc; border-radius: 2px; font-size: 11px; background: #f5f5f5;">
        </td>
        <td style="padding: 8px; text-align: center; border: 1px solid #ccc;">
          <input type="text" name="summary_used_${itemKey}" value="0" readonly style="width: 160px; padding: 4px; text-align: center; border: 1px solid #ccc; border-radius: 2px; font-size: 11px; background: #f5f5f5;">
        </td>
        <td style="padding: 8px; font-size: 11px; text-align: center; border: 1px solid #ccc; background: #f5f5f5; font-weight: bold; color: #333;">
          0.00
        </td>
        <td style="padding: 8px; border: 1px solid #ccc;">
          <input type="text" name="summary_batch_ref_${itemKey}" value="" readonly style="width: 100%; padding: 4px; border: 1px solid #ccc; border-radius: 2px; font-size: 11px; box-sizing: border-box; background: #f5f5f5;">
        </td>
      </tr>
    `;
  }
  
  // Build dispatch section (DYNAMIC - ALL BATCHES, NO TOTAL)
  const allBatches = window.BATCH_DATA.all_batches || [];
  let dispatchRows = '';
  for (const batch of allBatches) {
    dispatchRows += `
      <div style="margin-bottom: 12px; padding: 8px; background: white; border: 1px solid #ddd; border-radius: 3px;">
        <label style="font-weight: bold; font-size: 11px; display: block; margin-bottom: 3px;">${batch.batch_number}:</label>
        <input type="number" name="ready_dispatch_${batch.batch_number}" value="0" step="1" readonly style="width: 100%; padding: 6px; border: 1px solid #ccc; border-radius: 2px; font-size: 11px; box-sizing: border-box; background: #f9f9f9;">
      </div>
    `;
  }
  
  // Build complete HTML
  let html = `
    <div style="max-width: 1200px; margin: 0 auto; padding: 20px;">
      
      <!-- TOP TABLE -->
      <table style="width: 100%; border-collapse: collapse; margin-bottom: 30px; font-size: 12px;">
        <thead>
          <tr style="background: #417690; color: white; font-weight: bold;">
            <th style="padding: 10px; text-align: center; border: 1px solid #999;">ITEM</th>
            <th style="padding: 10px; text-align: center; border: 1px solid #999;">UNIT</th>
            <th style="padding: 10px; text-align: center; border: 1px solid #999;">IDEAL</th>
            <th style="padding: 10px; text-align: center; border: 1px solid #999;">USED</th>
            <th style="padding: 10px; text-align: center; border: 1px solid #999;">DIFFERENCE</th>
            <th style="padding: 10px; text-align: center; border: 1px solid #999;">BATCH REF</th>
          </tr>
        </thead>
        <tbody>
          ${tableRows}
        </tbody>
      </table>
      
      <!-- BOTTOM SECTION - 2 COLUMN LAYOUT -->
      <div style="display: grid; grid-template-columns: 600px 250px; gap: 20px; justify-items: center;">
      
        <!-- LEFT COLUMN - Packaging Summary (VERTICAL STACKED) -->
        <div style="background: #f0f8ff; border: 2px solid #417690; border-radius: 4px; padding: 15px;">
          <h3 style="margin: 0 0 15px 0; color: #417690; font-size: 13px; font-weight: bold; text-align: center; padding-bottom: 10px; border-bottom: 2px solid #417690;">Packaging Summary</h3>
          
          <div style="display: flex; flex-direction: column; gap: 15px;">
            <!-- 1. Items Manufactured -->
            <div>
              <label style="font-weight: bold; font-size: 11px; display: block; margin-bottom: 4px;">Items Manufactured</label>
              <input type="number" id="items_manufactured" name="items_manufactured" value="0" step="1" readonly style="width: 100%; padding: 8px; border: 1px solid #417690; border-radius: 2px; font-size: 12px; font-weight: bold; box-sizing: border-box; background: #e8f4f8;">
            </div>
            
            <!-- 2. Boxes Packed -->
            <div>
              <label style="font-weight: bold; font-size: 11px; display: block; margin-bottom: 4px;">Boxes Packed (÷6)</label>
              <input type="number" id="boxes_packed_calc" name="boxes_packed" value="0" step="0.01" readonly style="width: 100%; padding: 8px; border: 1px solid #417690; border-radius: 2px; font-size: 12px; font-weight: bold; box-sizing: border-box; background: #e8f4f8;">
            </div>
            
            <!-- 3. Pallets Packed -->
            <div>
              <label style="font-weight: bold; font-size: 11px; display: block; margin-bottom: 4px;">Pallets Packed</label>
              <input type="number" id="pallets_packed_calc" name="pallets_packed" value="0" step="0.01" readonly style="width: 100%; padding: 8px; border: 1px solid #417690; border-radius: 2px; font-size: 12px; font-weight: bold; box-sizing: border-box; background: #e8f4f8;">
            </div>
          </div>
        </div>
        
        <!-- RIGHT COLUMN - Ready for Dispatch Per Batch (NO TOTAL) -->
        <div style="background: white; border: 1px solid #999; border-radius: 4px; padding: 15px;">
          <h3 style="margin: 0 0 15px 0; color: #417690; font-size: 13px; font-weight: bold; text-align: center; padding-bottom: 10px; border-bottom: 1px solid #ccc;">Ready for Dispatch Per Batch</h3>
          
          <div style="max-height: 300px; overflow-y: auto;">
            ${dispatchRows}
          </div>
        </div>
      </div>
      
    </div>
  `;
  
  summaryTab.innerHTML = html;
  calculatePackagingSummary();  // ✅ Calculate initial values
  
  // ✅ SYNC DATA FROM TABS TO SUMMARY (MINIMAL CHANGE)
  setTimeout(() => {
      syncSummaryDataFromTabs();
      syncMeatDataToSummary();
	  calculateSummaryDifferences(); 
  }, 100);
  
}

function calculatePackagingSummary() {
    const allBatches = window.BATCH_DATA.all_batches || [];
    const pouchWasteData = window.BATCH_DATA.saved_pouch_waste_data || {};

    const packagingInfo = window.BATCH_DATA.packaging_info || {};

    let totalPouchesForIdeal = 0;    // 24000: main qty (shift_total)
    let totalPouchesForSummary = 0;  // 23916: ready-for-dispatch
    let batchDispatchData = {};

    // ✅ CALCULATE DISPATCH FOR EACH BATCH
    for (const batch of allBatches) {
        const batchNumber = batch.batch_number;
        const shiftTotal = parseFloat(batch.shift_total) || 0;

        const nsiSamples = pouchWasteData.nsi_sample_per_batch?.[batchNumber] || 0;
        const retentionSamples = pouchWasteData.retention_sample_per_batch?.[batchNumber] || 0;

        const readyForDispatch = shiftTotal - nsiSamples - retentionSamples;
        const safeReady = Math.max(0, readyForDispatch);

        batchDispatchData[batchNumber] = safeReady;

        const input = document.querySelector(`input[name="ready_dispatch_${batchNumber}"]`);
        if (input) {
            input.value = safeReady;
        }

        // ✅ For IDEAL (top table): use main qty
        totalPouchesForIdeal += shiftTotal;

        // ✅ For Packaging Summary (bottom card): use ready-for-dispatch
        totalPouchesForSummary += safeReady;
    }


    // ✅ CALCULATE IDEAL FOR MAIN PRODUCT COMPONENTS
    const mainComponents = window.BATCH_DATA.main_product_components || {};
    for (const mainKey in mainComponents) {
        const comp = mainComponents[mainKey];
        const stockItemId = comp.stock_item_id;
        const usagePerUnit = parseFloat(comp.standard_usage) || 0;

        const ideal = Math.floor(totalPouchesForIdeal * usagePerUnit);


        const idealInput = document.querySelector(`input[name="summary_ideal_main_${stockItemId}"]`);
        if (idealInput) {
            idealInput.value = ideal;
        }
    }

    // ✅ CALCULATE IDEAL FOR PRODUCT COMPONENTS (Packaging, etc)
    const components = window.BATCH_DATA.components || {};
    for (const compKey in components) {
        const comp = components[compKey];
        const stockItemId = comp.stock_item_id;
        const usagePerUnit = parseFloat(comp.standard_usage) || 0;

        const ideal = Math.floor(totalPouchesForIdeal * usagePerUnit);


        const idealInput = document.querySelector(`input[name="summary_ideal_comp_${stockItemId}"]`);
        if (idealInput) {
            idealInput.value = ideal;
        }
    }

    // ✅ CALCULATE IDEAL FOR RECIPE ITEMS
    const recipes = window.BATCH_DATA.recipes || {};
    for (const recipeId in recipes) {
        const recipe = recipes[recipeId];
        const recipeItems = recipe.recipe_items || {};

        for (const itemKey in recipeItems) {
            const item = recipeItems[itemKey];
            const stockItemId = item.stock_item_id;
            const usagePerUnit = parseFloat(item.standard_usage) || 0;

            const ideal = Math.floor(totalPouchesForIdeal * usagePerUnit);


            const idealInput = document.querySelector(`input[name="summary_ideal_recipe_${stockItemId}"]`);
            if (idealInput) {
                idealInput.value = ideal;
            }
        }
    }

    // ✅ PACKAGING SUMMARY (use ready-for-dispatch total)
    const primaryUsage = packagingInfo.primary?.usage_per_pallet || 990;
    const secondaryUsage = packagingInfo.secondary?.usage_per_pallet || 165;

    const itemsManufactured = document.getElementById('items_manufactured');
    const boxesField = document.getElementById('boxes_packed_calc');
    const palletsField = document.getElementById('pallets_packed_calc');

    if (itemsManufactured) {
        itemsManufactured.value = totalPouchesForSummary;
    }

    if (boxesField) {
        const boxDivisor = primaryUsage / secondaryUsage;
        const boxes = Math.floor(totalPouchesForSummary / boxDivisor);
        boxesField.value = boxes;
    }

    if (palletsField) {
        const pallets = Math.floor(totalPouchesForSummary / primaryUsage);
        palletsField.value = pallets;
    }

}


function syncSummaryDataFromTabs() {
    const tabData = {};
    
    // ✅ FIRST: Load SAVED PRODUCT USAGE DATA (from backend)
    const savedProductUsage = window.BATCH_DATA.saved_product_usage_data || {};
    const mainComponents = window.BATCH_DATA.main_product_components || {};
    const components = window.BATCH_DATA.components || {};
    const recipes = window.BATCH_DATA.recipes || {};
    
    // Load main product components from saved data
    for (const mainKey in mainComponents) {
        const comp = mainComponents[mainKey];
        const stockItemId = comp.stock_item_id;
        const saved = savedProductUsage[stockItemId];
        
        if (saved) {
            const key = `main_${stockItemId}`;
            tabData[key] = { 
                batchRef: saved.ref_number || '', 
                used: saved.qty_used || 0 
            };
        }
    }
    
    // Load product components from saved data
    for (const compKey in components) {
        const comp = components[compKey];
        const stockItemId = comp.stock_item_id;
        const saved = savedProductUsage[stockItemId];
        
        if (saved && !((`comp_${stockItemId}`) in tabData)) {
            const key = `comp_${stockItemId}`;
            tabData[key] = { 
                batchRef: saved.ref_number || '', 
                used: saved.qty_used || 0 
            };
        }
    }
    
    // Load recipe items from saved data
    for (const recipeId in recipes) {
        const recipe = recipes[recipeId];
        const recipeItems = recipe.recipe_items || {};
        for (const itemId in recipeItems) {
            const item = recipeItems[itemId];
            const stockItemId = item.stock_item_id;
            const saved = savedProductUsage[stockItemId];
            
            if (saved) {
                const key = `recipe_${stockItemId}`;
                if (!(key in tabData)) {  // Don't overwrite existing data
                    tabData[key] = { 
                        batchRef: saved.ref_number || '', 
                        used: saved.qty_used || 0 
                    };
                }
            }
        }
    }
    
    // ============ SAUCE TAB RECIPE ITEMS ============
    // READ THE ACTUAL "Usage for Day" INPUT VALUES (OVERRIDE saved data)
    document.querySelectorAll('input[name^="sauce_usage_"]').forEach(usageInput => {
        const stockItemId = usageInput.name.replace('sauce_usage_', '');
        const batchRefInput = document.querySelector(`input[name="sauce_batch_ref_${stockItemId}"]`);
        
        const used = parseFloat(usageInput.value) || 0;  // ✅ READ FROM INPUT
        const batchRef = batchRefInput?.value || '';
        
        const key = `recipe_${stockItemId}`;
        tabData[key] = { batchRef, used };
    });
    
    // ============ PACKAGING TAB ITEMS ============
    // READ THE ACTUAL "Usage for Day" INPUT VALUES (OVERRIDE saved data)
    document.querySelectorAll('input[name^="pkg_usage_"]').forEach(usageInput => {
        const stockItemId = usageInput.name.replace('pkg_usage_', '');
        const batchRefInput = document.querySelector(`input[name="pkg_batch_ref_${stockItemId}"]`);
        
        const used = parseFloat(usageInput.value) || 0;  // ✅ READ FROM INPUT
        const batchRef = batchRefInput?.value || '';
        
        const key = `comp_${stockItemId}`;
        tabData[key] = { batchRef, used };
    });
    
    // ============ UPDATE SUMMARY TABLE ============
    for (const itemKey in tabData) {
        const { batchRef, used } = tabData[itemKey];
        
        const batchRefInput = document.querySelector(`input[name="summary_batch_ref_${itemKey}"]`);
        const usedInput = document.querySelector(`input[name="summary_used_${itemKey}"]`);
        
        if (batchRefInput) batchRefInput.value = batchRef;
        if (usedInput) usedInput.value = used.toFixed(2);
    }
    
}

function syncMeatDataToSummary() {
    // Get all container selects and kg inputs from meat tab
    const containerSelects = document.querySelectorAll('select[name="container_id[]"]');
    const kgInputs = document.querySelectorAll('input[name="kg_frozen_meat_used[]"]');
    
    let containerNumbers = [];
    let kgValues = [];
    let totalKgUsed = 0;
    
    containerSelects.forEach((select, i) => {
        if (select.value) {
            containerNumbers.push(select.value);
        }
    });
    
    kgInputs.forEach((input) => {
        const kg = parseFloat(input.value) || 0;
        if (kg > 0) {
            kgValues.push(kg.toString());
            totalKgUsed += kg;
        }
    });
    
    // ✅ Get the main product component dynamically
    const mainComponents = window.BATCH_DATA.main_product_components || {};
    for (const mainKey in mainComponents) {
        const comp = mainComponents[mainKey];
        const stockItemId = comp.stock_item_id;
        
        // Update Summary table with meat data using dynamic stock item ID
        const batchRefInput = document.querySelector(`input[name="summary_batch_ref_main_${stockItemId}"]`);
        const usedInput = document.querySelector(`input[name="summary_used_main_${stockItemId}"]`);
        
        if (batchRefInput) {
            batchRefInput.value = containerNumbers.join(', ');
        }
        
        if (usedInput) {
            const displayText = kgValues.length > 0 
                ? `${kgValues.join(', ')} (${totalKgUsed} Combined)`
                : totalKgUsed.toFixed(2);
            usedInput.value = displayText;
        }
    }
}

function calculateSummaryDifferences() {
    // Get all rows in summary table
    document.querySelectorAll('tbody tr').forEach(row => {
        const idealInput = row.querySelector('input[name^="summary_ideal"]');
        const usedInput = row.querySelector('input[name^="summary_used"]');
        const differenceCell = row.cells[4]; // DIFFERENCE column
        
        if (idealInput && usedInput && differenceCell) {
            // Parse ideal - handle "5500, 5000 (1050" format for meat
            let ideal = 0;
            const idealValue = idealInput.value;
            if (!isNaN(idealValue)) {
                ideal = parseFloat(idealValue) || 0;
            }
            
            // Parse used - handle "5500, 5000 (10500 Combined)" format
            let used = 0;
            const usedValue = usedInput.value;
            const match = usedValue.match(/\((\d+(?:\.\d+)?)\s+Combined\)/);
            if (match) {
                used = parseFloat(match[1]) || 0;
            } else if (!isNaN(usedValue)) {
                used = parseFloat(usedValue) || 0;
            }
            
            // Calculate difference
            const difference = ideal - used;
            
            // Update difference cell
            differenceCell.innerHTML = `<span style="font-weight: bold; color: ${difference < 0 ? '#c71c2f' : '#22c55e'};">${difference.toFixed(2)}</span>`;
        }
    });
}

function updateDispatchTotal() {
    const inputs = document.querySelectorAll('input[name^="ready_dispatch_"]');
    let total = 0;
    
    // Calculate for each batch
    const allBatches = window.BATCH_DATA.all_batches || [];
    const pouchWasteData = window.BATCH_DATA.saved_pouch_waste_data || {};
    
    for (const batch of allBatches) {
        const batchNumber = batch.batch_number;
        const shiftTotal = parseFloat(batch.shift_total) || 0;
        
        // Get sample data for this batch
        const nsiSamples = pouchWasteData.nsi_sample_per_batch?.[batchNumber] || 0;
        const retentionSamples = pouchWasteData.retention_sample_per_batch?.[batchNumber] || 0;
        const unclearCoding = pouchWasteData.unclear_coding_per_batch?.[batchNumber] || 0;
        
        // Calculate: Shift Total - NSI - Retention - Unclear Coding
        const readyForDispatch = shiftTotal - nsiSamples - retentionSamples - unclearCoding;
        
        // Find input for this batch and set value
        const input = document.querySelector(`input[name="ready_dispatch_${batchNumber}"]`);
        if (input) {
            input.value = Math.max(0, readyForDispatch);  // ✅ Prevent negative
        }
        
        total += Math.max(0, readyForDispatch);
    }
    
    // Update total
    const totalField = document.getElementById('dispatch-total');
    if (totalField) totalField.value = total.toLocaleString();
    
}

/* ============================================================ */
/* CONTAINER CARD MANAGEMENT */
/* ============================================================ */

window.addContainerCard = function() {
  const row = document.querySelector('.container-row');
  if (!row) {

    return;
  }
  
  const source = window.currentMeatSource || 'import';
  const templateSelect = document.getElementById(`container-options-template-${source}`);
  let optionsHTML = '';
  
  if (templateSelect) {
    optionsHTML = templateSelect.innerHTML;
  } else {

    optionsHTML = '<option value="">--select--</option>';
  }
  
  // ✅ Generate unique ID for this card
  const cardId = 'container-card-' + Date.now();
  
  const newCard = document.createElement('div');
  newCard.className = 'container-card';
  newCard.id = cardId;
  newCard.setAttribute('data-source', source);
  newCard.innerHTML = `
    <div class="card-header">
      <input type="hidden" name="source_type[]" value="${source}">
      <select name="container_id[]" 
              onchange="populateBookOutQty(this); updateBalanceFromPrevShift(this);"
              data-source="${source}">
        ${optionsHTML}
      </select>
      <button type="button" class="btn-del-container" onclick="removeContainerCard(this)">
        <span class="delete-icon">🗑</span>
      </button>
    </div>

    <!-- ✅ NEW: Balance from Prev Shift (GREEN) -->
    <div class="form-group" style="background: #c8e6c9; padding: 8px; border-radius: 3px; border: 2px solid #4caf50;">
      <label style="font-size: 11px; font-weight: bold; color: #2e7d32;">💚 Balance from Prev Shift (kg)</label>
      <input type="number" 
             name="balance_from_prev_shift[]"
             class="balance-prev-shift-input"
             readonly
             value="0" 
             step="0.01"
             style="width: 100%; padding: 6px; background: #e8f5e9; font-weight: bold; border: 1px solid #4caf50; border-radius: 3px; color: #2e7d32; text-align: center;">
    </div>

    
    <!-- Book Out Qty -->
    <div class="form-group">
      <label>Book Out Qty (kg)</label>
      <input type="number" 
             name="book_out_qty[]" 
             value="0" 
             onchange="calculateDefrostedFresh(this); calculateWasteDefrostFilling();"
             class="book-out-qty-input"
             style="width: 100%; padding: 6px; background: #ffffcc; font-weight: bold; text-align: center; border: 1px solid #ccc; border-radius: 3px;">
    </div>

    <!-- Stock Left -->
    <div class="form-group">
      <label>Stock Left (kg)</label>
      <input type="number" 
             name="stock_left[]" 
             value="0" 
             step="0.01" 
             onchange="calculateDefrostedFresh(this); calculateWasteDefrostFilling();"
             style="width: 100%; padding: 6px; text-align: center; border: 1px solid #ccc; border-radius: 3px; box-sizing: border-box;">
    </div>
	
    <!-- Defrosted/Fresh (Calculated from Available - Stock Left) -->
    <div class="form-group">
      <label>Used Defrosted/Fresh (kg)</label>
      <input type="number" 
             name="kg_frozen_meat_used[]" 
             step="0.01" 
             readonly
             style="width: 100%; padding: 6px; background: #f5f5f5; font-weight: bold; text-align: center; border: 1px solid #ccc; border-radius: 3px;">
    </div>

    <!-- Waste Factor - Filling -->
    <div class="form-group">
	  <label>% Loss from Frozen/Raw - Filling</label>
	  <input type="number"
			 name="waste_factor[]"
			 readonly
			 style="width: 100%; padding: 6px; text-align: center; border: 1px solid #ccc; border-radius: 3px; box-sizing: border-box; font-weight: bold;">
	</div>
    
    <!-- Waste Factor - Pouch -->
    <div class="form-group">
      <label>% Loss From Frozen/Raw - Pouch Actual</label>
      <input type="number" 
       name="waste_factor_pouch[]" 
       step="0.01" 
       onchange="calculateWasteDefrostPouch();"
       readonly 
       style="width: 100%; padding: 6px; text-align: center; border: 1px solid #ccc; border-radius: 3px; box-sizing: border-box; font-weight: bold;">
    </div>

    <!-- Defrost Sheet Upload -->
	<div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #ccc;">
	  <div class="form-group">
		<label style="font-size: 11px;">Defrost Sheet (PDF/DOC)</label>

		<ul class="defrost-doc-list"></ul>

		<div class="defrost-file-rows" style="display:none;"></div>

		<button type="button"
				class="defrost-add-row"
				style="margin-top:5px;">+ Add Defrost Sheet</button>

		<small style="color: #999; font-size: 10px;">PDF, DOC, DOCX</small>
	  </div>
	</div>
  `;
  
  const sidebar = row.querySelector('.meat-production-sidebar');
  if (sidebar) {
    row.insertBefore(newCard, sidebar);
  } else {
    row.appendChild(newCard);
  }
  
};

// ✅ HELPER FUNCTION: Get balance from previous shift
window.getBalanceFromPrevShift = function(containerRef, containerSource) {
  try {
    const productionDate = new Date(window.BATCH_DATA.production_date.replace(/\\/g, '-'));
    const prevDate = new Date(productionDate);
    prevDate.setDate(prevDate.getDate() - 1);
    
    // Get all batch containers from database
    const allBatches = window.BATCH_DATA.all_batch_containers || [];
    
    // Filter for previous date, matching container
    const prevBatches = allBatches.filter(bc => {
      try {
        const bcDate = new Date(bc.production_date.replace(/\\/g, '-'));
        return bcDate.toDateString() === prevDate.toDateString() && 
               (bc.container === containerRef || bc.container_number === containerRef) &&
               (containerSource === 'all' || bc.source_type === containerSource);
      } catch (e) {
        return false;
      }
    });
    
    // Return stock_left from last matching entry
    if (prevBatches.length > 0) {
      const balance = parseFloat(prevBatches[prevBatches.length - 1].stock_left || 0);
      return isNaN(balance) ? 0 : balance;
    }
    return 0;
  } catch (e) {

    return 0;
  }
};

// ✅ UPDATE BALANCE FIELD when container is selected
window.updateBalanceFromPrevShift = function(selectElement) {
  try {
    const containerRef = selectElement.value;
    const source = selectElement.getAttribute('data-source') || window.currentMeatSource;
    const card = selectElement.closest('.container-card');
    const balanceInput = card?.querySelector('.balance-prev-shift-input');
    
    if (balanceInput && containerRef) {
      const balance = window.getBalanceFromPrevShift(containerRef, source);
      balanceInput.value = balance.toFixed(2);
    }
  } catch (e) {

  }
};

// ✅ CALCULATE Defrosted/Fresh (Balance + BookOut - StockLeft)
window.calculateDefrostedFresh = function(input) {
  try {
    const card = input.closest('.container-card');
    const balanceInput = card?.querySelector('.balance-prev-shift-input');
    const bookOutInput = card?.querySelector('input[name="book_out_qty[]"]');
    const stockLeftInput = card?.querySelector('input[name="stock_left[]"]');
    const defrostedInput = card?.querySelector('input[name="kg_frozen_meat_used[]"]');
    
    const balance = parseFloat(balanceInput?.value || 0);
    const bookOut = parseFloat(bookOutInput?.value || 0);
    const stockLeft = parseFloat(stockLeftInput?.value || 0);
    
    // Formula: Balance from Prev Shift + Book Out Qty - Stock Left
    const defrosted = balance + bookOut - stockLeft;
    
    if (defrostedInput) {
      defrostedInput.value = isNaN(defrosted) ? 0 : defrosted.toFixed(2);
    }
    
  } catch (e) {

  }
};

// UPDATE BALANCE FROM PREVIOUS PRODUCTION SHIFT
window.updateBalanceFromPrevShift = function(selectElement) {
  try {
    const containerRef = selectElement.value;
    const card = selectElement.closest('.container-card');
    const balanceInput = card?.querySelector('.balance-prev-shift-input');
    
    if (!balanceInput || !containerRef) return;
    
    // Get opening balance from meat_container_openings
    const openingData = window.BATCH_DATA?.meat_container_openings?.[containerRef];
    
    if (openingData && openingData.opening_balance !== undefined) {
      balanceInput.value = openingData.opening_balance.toFixed(0);
    } else {
      balanceInput.value = 0;
    }
  } catch (e) {

  }
};

// ✅ EXISTING FUNCTION: populateBookOutQty
// ✅ NOW: Works like sauce/packaging - pulls from SAVED DATA first
// Only if no saved data, check for NEW transactions from today
window.populateBookOutQty = function(selectElement) {
  try {
    const containerRef = selectElement.value;
    const card = selectElement.closest('.container-card');
    const bookOutInput = card?.querySelector('.book-out-qty-input');
    
    if (!bookOutInput) return;
    
    if (!containerRef) {
      bookOutInput.value = '0.00';
      return;
    }
    
    // ✅ STEP 0: Check if there's a value in the between_out_qty_map (instant lookup before save)
    const betweenOutMap = window.BATCH_DATA?.between_out_qty_map || {};
    if (betweenOutMap[containerRef] !== undefined && betweenOutMap[containerRef] !== null) {
      bookOutInput.value = parseFloat(betweenOutMap[containerRef]).toFixed(2);
      return;
    }
    
    // ✅ STEP 1: Check if there's SAVED data for this container
    // (stored in window.BATCH_DATA.saved_batch_containers)
    const savedContainers = window.BATCH_DATA?.saved_batch_containers || [];
    const savedContainer = savedContainers.find(c => {
      const id = c.container_id || c.batch_ref;
      return id === containerRef;
    });
    
    if (savedContainer && savedContainer.book_out_qty !== undefined && savedContainer.book_out_qty !== null) {
      // Use saved value
      bookOutInput.value = parseFloat(savedContainer.book_out_qty).toFixed(2);
      return;
    }
    
    // ✅ STEP 2: No saved data - check for NEW transactions from today
    const prodDate = window.BATCH_DATA?.production_date; // Format: "dd/mm/yyyy"
    if (!prodDate) {
      bookOutInput.value = '0.00';
      return;
    }
    
    // Convert production_date to YYYY-MM-DD format for comparison
    const [day, month, year] = prodDate.split('/');
    const normalizedProdDate = `${year}-${month}-${day}`;
    
    // Query stock transactions for NEW book out (created today)
    const transactions = window.BATCH_DATA.stock_transactions || [];
    
    // ✅ ONLY populate if transaction was created TODAY
    const newBookOut = transactions.find(t => 
      t.batch_ref === containerRef && 
      t.transaction_type === 'OUT' &&
      t.transaction_date === normalizedProdDate  // ← ONLY TODAY
    );
    
    if (newBookOut && parseFloat(newBookOut.quantity) > 0) {
      bookOutInput.value = parseFloat(newBookOut.quantity || 0).toFixed(2);
    } else {
      // No saved data and no new transaction - start at 0
      bookOutInput.value = '0.00';
    }
  } catch (e) {
    // Fallback to 0
    const card = selectElement?.closest('.container-card');
    if (card?.querySelector('.book-out-qty-input')) {
      card.querySelector('.book-out-qty-input').value = '0.00';
    }
  }
};

// ✅ REMOVE CONTAINER CARD
window.removeContainerCard = function(button) {
  if (confirm('Delete this container entry?')) {
    const card = button.closest('.container-card');
    card?.remove();
  }
};

// ✅ CALCULATE WASTE DEFROST POUCH
window.calculateWasteDefrostPouch = function() {
  try {
    const cards = document.querySelectorAll('.container-card');
    let totalWaste = 0;
    
    cards.forEach(card => {
      const wasteInput = card.querySelector('input[name="waste_factor_pouch[]"]');
      const defrostedInput = card.querySelector('input[name="kg_frozen_meat_used[]"]');
      
      if (wasteInput && defrostedInput) {
        const waste = (parseFloat(wasteInput.value || 0) / 100) * parseFloat(defrostedInput.value || 0);
        totalWaste += isNaN(waste) ? 0 : waste;
      }
    });
    
    const summaryInput = document.querySelector('input[name="total_waste"]');
    if (summaryInput) {
      summaryInput.value = totalWaste.toFixed(2);
    }
    
  } catch (e) {

  }
};

// ✅ CALCULATE WASTE DEFROST FILLING
window.calculateWasteDefrostFilling = function() {
  try {
    const cards = document.querySelectorAll('.container-card');
    let totalMeatFilled = 0;
    
    cards.forEach(card => {
      const defrostedInput = card.querySelector('input[name="kg_frozen_meat_used[]"]');
      if (defrostedInput) {
        const defrosted = parseFloat(defrostedInput.value || 0);
        totalMeatFilled += isNaN(defrosted) ? 0 : defrosted;
      }
    });
    
    const summaryInput = document.querySelector('input[name="total_meat_filled"]');
    if (summaryInput) {
      summaryInput.value = totalMeatFilled.toFixed(2);
    }
    
  } catch (e) {

  }
};



/* ============================================================ */
/* LOAD SAVED DATA */
/* ============================================================ */

function loadSavedData() {
  
  if (!window.BATCH_DATA) {

    return;
  }
  
  // LOAD CERTIFICATION DATA
  const certData = window.BATCH_DATA.saved_cert_data || {};
  for (const batch_number in certData) {
    const data = certData[batch_number];
    const statusSelect = document.querySelector(`select[name="status_${batch_number}"]`);
    if (statusSelect && data.status) statusSelect.value = data.status;
    
    const incStartInput = document.querySelector(`input[name="incubation_start_${batch_number}"]`);
    if (incStartInput && data.incubation_start) incStartInput.value = data.incubation_start;
    
    const incEndInput = document.querySelector(`input[name="incubation_end_${batch_number}"]`);
    if (incEndInput && data.incubation_end) incEndInput.value = data.incubation_end;
    
    const nsiSubInput = document.querySelector(`input[name="nsi_submission_date_${batch_number}"]`);
    if (nsiSubInput && data.nsi_submission_date) nsiSubInput.value = data.nsi_submission_date;
    
    const certInput = document.querySelector(`input[name="certification_date_${batch_number}"]`);
    if (certInput && data.certification_date) certInput.value = data.certification_date;
  }
  
  // LOAD MEAT CONTAINERS DATA
  const containerData = window.BATCH_DATA.saved_batch_containers || [];

  if (containerData.length > 0) {
    const row = document.querySelector('.container-row');

    if (row) {
      containerData.forEach(container => {
	  // ✅ SWITCH SOURCE FIRST if it's LOCAL
	  if (container.source_type === 'local') {
		window.currentMeatSource = 'local';
	  } else {
		window.currentMeatSource = 'import';
	  }
	  
	  addContainerCard();
	  
	  const cards = row.querySelectorAll('.container-card');
	  const lastCard = cards[cards.length - 1];
	  
	  const select = lastCard.querySelector('select[name="container_id[]"]');
	  if (select) {
		const value = container.container_id || container.batch_ref;
		select.value = value;
	  }

	  // ✅ LOAD SAVED OPENING BALANCE DIRECTLY (from previous production)
	  const balanceInput = lastCard?.querySelector('input[name="balance_from_prev_shift[]"]');
	  if (balanceInput && container.opening_balance !== undefined && container.opening_balance !== null) {
		balanceInput.value = parseFloat(container.opening_balance).toFixed(2);
	  } else if (balanceInput) {
		balanceInput.value = '0.00';
	  }
	  
	  // ✅ LOAD SAVED BOOK OUT QTY DIRECTLY (like packaging/sauce do)
	  const bookOutInput = lastCard?.querySelector('input[name="book_out_qty[]"]');
	  if (bookOutInput && container.book_out_qty !== undefined && container.book_out_qty !== null) {
		bookOutInput.value = parseFloat(container.book_out_qty).toFixed(2);
	  } else if (bookOutInput) {
		bookOutInput.value = '0.00';
	  }

	  // Load stock left
	  const stockLeftInput = lastCard.querySelector('input[name="stock_left[]"]');
	  if (stockLeftInput) {
		const stockLeftValue = container.stock_left !== undefined && container.stock_left !== null 
		  ? container.stock_left 
		  : 0;
		stockLeftInput.value = parseFloat(stockLeftValue).toFixed(0);
	  }

	  // ✅ NOW CALCULATE - after balance AND stock_left are both set
	  setTimeout(() => {
		const stockLeftInput = lastCard.querySelector('input[name="stock_left[]"]');
		if (stockLeftInput) {
		  calculateDefrostedFresh(stockLeftInput);
		}
	  }, 50);
      });
    }
  }
  
  // ✅ Load defrost documents for each container
  setTimeout(() => {
    const cards = document.querySelectorAll('.container-card');
    
    cards.forEach((card, idx) => {
      const container = containerData[idx];
      if (!container) return;

      const list = card.querySelector('.defrost-doc-list');
      if (!list) {

        return;
      }

      const docs = container.defrost_documents || [];
      
      docs.forEach(doc => {
        const li = document.createElement('li');
        li.className = 'defrost-doc-item';
        li.innerHTML = `
          <a href="${doc.url}" target="_blank">${doc.filename}</a>
          <button type="button"
                  class="defrost-remove-row"
                  data-doc-id="${doc.id}"
                  style="margin-left:5px; border:none; background:none; color:#d32f2f; font-weight:bold; cursor:pointer;">×</button>
        `;
        list.appendChild(li);
      });
    });
  }, 150);
  
  
  
  // LOAD MEAT SUMMARY DATA
  const meatSummary = window.BATCH_DATA.saved_meat_summary_data || {};

  if (Object.keys(meatSummary).length > 0) {
    // Total Meat Filled
    const totalMeatInput = document.querySelector('input[name="total_meat_filled"]');
    if (totalMeatInput && meatSummary.total_meat_filled !== undefined) {
      totalMeatInput.value = parseFloat(meatSummary.total_meat_filled).toFixed(2);
    }

    // Filling Weight per Pouch - load saved value or default to 0.277
	const fillingWeightInput = document.querySelector('input[name="filling_weight_per_pouch"]');
	if (fillingWeightInput) {
		const savedFillingWeight = meatSummary.filling_weight_per_pouch || 0.277;
		fillingWeightInput.value = savedFillingWeight;
	}


    // Total Waste
    const totalWasteInput = document.querySelector('input[name="total_waste"]');
    if (totalWasteInput && meatSummary.total_waste !== undefined) {
      totalWasteInput.value = parseFloat(meatSummary.total_waste).toFixed(2);
    }

    // ✅ TRIGGER CALCULATIONS AFTER A SMALL DELAY
    setTimeout(() => {
      calculateWasteDefrostFilling();
      calculateWasteDefrostPouch();
    }, 50);
  }


  
  // LOAD SAUCE DATA
  const sauceData = window.BATCH_DATA.saved_sauce_data || {};

  if (Object.keys(sauceData).length > 0) {
    const openingInput = document.querySelector('input[name="opening_balance"]');
    if (openingInput) openingInput.value = sauceData.opening_balance || 0;

    const amendedInput = document.getElementById('amended_opening_input');
    if (amendedInput) {
      amendedInput.value = sauceData.amended_opening_balance || '';
      amendedInput.disabled = true;  // default; checkbox controls it
    }

    const reasonInput = document.querySelector('textarea[name="amended_reason"]');
    if (reasonInput) reasonInput.value = sauceData.amended_reason || '';

    const mixedInput = document.querySelector('input[name="sauce_mixed"]');
    if (mixedInput) mixedInput.value = sauceData.sauce_mixed || 0;

    const closingInput = document.querySelector('input[name="closing_balance"]');
    if (closingInput) closingInput.value = sauceData.closing_balance || 0;

    const cancelCheckbox = document.querySelector('input[name="cancel_opening_balance"]');
	if (cancelCheckbox && sauceData.cancel_opening_balance) {  // ✅ CORRECT
	  cancelCheckbox.checked = true;
	  if (amendedInput) amendedInput.disabled = false;
	}

    calculateUsageForDay();
	
  }
  
  // ✅ LOAD RECIPE ITEM BALANCES (LEFT CARDS)
  if (window.BATCH_DATA.saved_sauce_recipe_items && Array.isArray(window.BATCH_DATA.saved_sauce_recipe_items)) {

      window.BATCH_DATA.saved_sauce_recipe_items.forEach(item => {
    
          const closingInput = document.querySelector(`input[name="sauce_closing_${item.stock_item_id}"]`);
          const batchRefInput = document.querySelector(`input[name="sauce_batch_ref_${item.stock_item_id}"]`);
          const reasonInput = document.querySelector(`textarea[name="sauce_reason_${item.stock_item_id}"]`);
          const cancelCheckbox = document.querySelector(`input[name="sauce_cancel_${item.stock_item_id}"]`);
    
    
          if (closingInput) {
              closingInput.value = item.closing_balance || 0;
          }
        
          // ✅ ONLY UPDATE BATCH REF IF DATABASE HAS A VALUE
          // OTHERWISE KEEP THE INITIAL VALUE FROM sauceBookouts
          if (batchRefInput) {
              if (item.batch_ref) {
                  batchRefInput.value = item.batch_ref;
              } else {
              }
          }
        
          if (cancelCheckbox) {
              cancelCheckbox.checked = item.cancel_opening_use_bookout || false;
          }
          if (reasonInput) {
              reasonInput.value = item.amended_reason || '';
          }
      });
  }

 
  // ✅ DOWN TIME DATA LOADING
  const downTimeData = window.BATCH_DATA.saved_pouch_waste_data || {};
  
  if (downTimeData.total_down_time) {
    const totalDownTimeInput = document.querySelector('input[name="total_down_time"]');
    const reasonsInput = document.querySelector('textarea[name="reasons_for_down_time"]');
    
    if (totalDownTimeInput) {
      totalDownTimeInput.value = downTimeData.total_down_time;
    }
    
    if (reasonsInput) {
      reasonsInput.value = downTimeData.reasons_for_down_time || '';
    }
  }

  // LOAD POUCH WASTE DATA
  const pouchData = window.BATCH_DATA.saved_pouch_waste_data || {};

  if (Object.keys(pouchData).length > 0) {
    // Machine Waste
    document.querySelector('input[name="machine_count"]') && (document.querySelector('input[name="machine_count"]').value = pouchData.machine_count || 0);
    document.querySelector('input[name="seal_creeps"]') && (document.querySelector('input[name="seal_creeps"]').value = pouchData.seal_creeps || 0);
    document.querySelector('input[name="unsealed_poor_seal"]') && (document.querySelector('input[name="unsealed_poor_seal"]').value = pouchData.unsealed_poor_seal || 0);
    document.querySelector('input[name="screwed_and_undated"]') && (document.querySelector('input[name="screwed_and_undated"]').value = pouchData.screwed_and_undated || 0);
    document.querySelector('input[name="over_weight"]') && (document.querySelector('input[name="over_weight"]').value = pouchData.over_weight || 0);
    document.querySelector('input[name="under_weight"]') && (document.querySelector('input[name="under_weight"]').value = pouchData.under_weight || 0);
    document.querySelector('input[name="empty_pouches"]') && (document.querySelector('input[name="empty_pouches"]').value = pouchData.empty_pouches || 0);
    document.querySelector('input[name="metal_detection"]') && (document.querySelector('input[name="metal_detection"]').value = pouchData.metal_detection || 0);
  
    // Retort Waste
    document.querySelector('input[name="retort_count"]') && (document.querySelector('input[name="retort_count"]').value = pouchData.retort_count || 0);
    document.querySelector('input[name="total_unclear_coding"]') && (document.querySelector('input[name="total_unclear_coding"]').value = pouchData.total_unclear_coding || 0);
    document.querySelector('input[name="retort_seal_creap"]') && (document.querySelector('input[name="retort_seal_creap"]').value = pouchData.retort_seal_creap || 0);
    document.querySelector('input[name="retort_under_weight"]') && (document.querySelector('input[name="retort_under_weight"]').value = pouchData.retort_under_weight || 0);
    document.querySelector('input[name="poor_ceiling_destroyed"]') && (document.querySelector('input[name="poor_ceiling_destroyed"]').value = pouchData.poor_ceiling_destroyed || 0);
  
    // ===== NEW: NSI & RETENTION SAMPLES =====
    const nsiPerBatch = pouchData.nsi_sample_per_batch || {};
    const retentionPerBatch = pouchData.retention_sample_per_batch || {};
    
    // Load NSI and Retention for each batch
    for (const [batchNumber, nsiQty] of Object.entries(nsiPerBatch)) {
      const nsiField = document.querySelector(`input[name="nsi_sample_pouches_${batchNumber}"]`);
      if (nsiField) nsiField.value = nsiQty || 0;
    }
    
    for (const [batchNumber, retentionQty] of Object.entries(retentionPerBatch)) {
      const retentionField = document.querySelector(`input[name="retention_sample_qty_${batchNumber}"]`);
      if (retentionField) retentionField.value = retentionQty || 0;
    }
    
    // Load Unclear Coding per batch
	const unclearCodingPerBatch = pouchData.unclear_coding_per_batch || {};
	for (const [batchNumber, qty] of Object.entries(unclearCodingPerBatch)) {
	  const field = document.querySelector(`input[name="unclear_coding_${batchNumber}"]`);
	  if (field) field.value = qty || 0;
	}

  
    // ✅ TRIGGER CALCULATIONS AFTER A SMALL DELAY
    setTimeout(() => {
      calculateMachineTotal();
      calculateRetortTotal();
    }, 50);
  
  }

  
	// LOAD PACKAGING DATA
	if (window.BATCH_DATA.saved_packaging_data) {
		const packagingData = window.BATCH_DATA.saved_packaging_data;
		
		for (const stockItemId in packagingData) {
			const data = packagingData[stockItemId];
			
			
			// Load Batch Ref Number
			const batchRefInput = document.querySelector(`input[name="pkg_batch_ref_${stockItemId}"]`);
			if (batchRefInput) {
				batchRefInput.value = data.batch_ref || '';
			}
			
			// Load Booked out stock
			const bookedInput = document.querySelector(`input[name="pkg_booked_${stockItemId}"]`);
			if (bookedInput) {
				bookedInput.value = data.booked_out_stock || 0;
			}
			
			// Load Opening Balance
			const openingInput = document.querySelector(`input[name="pkg_opening_${stockItemId}"]`);
			if (openingInput) {
				openingInput.value = data.opening_balance || 0;
			}
			
			// Load Closing Balance
			const closingInput = document.querySelector(`input[name="pkg_closing_${stockItemId}"]`);
			if (closingInput) {
				closingInput.value = data.closing_balance || 0;
				// calculatePackagingUsage(closingInput);
			}
			
			// Load Cancel checkbox
			const cancelCheckbox = document.querySelector(`input[name="pkg_cancel_${stockItemId}"]`);
			if (cancelCheckbox) {
				cancelCheckbox.checked = data.cancel_opening_use_bookout || false;
			}
			
			// Load Reason
			const reasonInput = document.querySelector(`textarea[name="pkg_reason_${stockItemId}"]`);
			if (reasonInput) {
				reasonInput.value = data.amended_reason || '';
			}
   
            // After all packaging data is loaded, trigger all calculations once
			setTimeout(() => {
			  updateAllPackagingItemUsages();
			}, 100);
			 
		}

	// LOAD SUMMARY DATA (Dispatch)
	if (window.BATCH_DATA.saved_summary_data) {
		const summaryData = window.BATCH_DATA.saved_summary_data;
		
		// Load packaging summary
		const packedPouch = document.querySelector('input[name="packed_pouches"]');
		if (packedPouch) packedPouch.value = summaryData.packed_pouches || 0;
		
		const boxesPacked = document.querySelector('input[name="boxes_packed"]');
		if (boxesPacked) boxesPacked.value = summaryData.boxes_packed || 0;
		
		const palletsPacked = document.querySelector('input[name="pallets_packed"]');
		if (palletsPacked) palletsPacked.value = summaryData.pallets_packed || 0;
		
	}

	// ✅ THEN RECALCULATE DISPATCH
	updateDispatchTotal();	
	
	}
}  // ✅ THIS CLOSES loadSavedData()

/* ============================================================ */
/* DATE CALCULATIONS */
/* ============================================================ */

function initializeDateCalculations() {
  const productionDateStr = window.BATCH_DATA?.production_date;
  if (!productionDateStr) {

    return;
  }
  
  const productionDate = new Date(productionDateStr);
  if (isNaN(productionDate)) {

    return;
  }
  
  const incubationStart = addDays(productionDate, 1);
  const incubationEnd = addDays(incubationStart, 10);
  const nsiSubmission = addDays(incubationEnd, 1);
  const certificationDate = addDays(nsiSubmission, 7);
  
  const incubationStartStr = formatDateForInput(incubationStart);
  const incubationEndStr = formatDateForInput(incubationEnd);
  const nsiSubmissionStr = formatDateForInput(nsiSubmission);
  const certificationDateStr = formatDateForInput(certificationDate);
  
  if (window.BATCH_DATA.all_batches) {
    window.BATCH_DATA.all_batches.forEach(batch => {
      const incStartInput = document.querySelector(`input[name="incubation_start_${batch.batch_number}"]`);
      if (incStartInput) incStartInput.value = incubationStartStr;
      
      const incEndInput = document.querySelector(`input[name="incubation_end_${batch.batch_number}"]`);
      if (incEndInput) incEndInput.value = incubationEndStr;
      
      const nsiSubInput = document.querySelector(`input[name="nsi_submission_date_${batch.batch_number}"]`);
      if (nsiSubInput) nsiSubInput.value = nsiSubmissionStr;
      
      const certInput = document.querySelector(`input[name="certification_date_${batch.batch_number}"]`);
      if (certInput) certInput.value = certificationDateStr;
    });
  }
  
}

function addDays(date, days) {
  const result = new Date(date);
  result.setDate(result.getDate() + days);
  return result;
}

function formatDateForInput(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function populateBookOutQty(selectElement) {
  // ✅ Handle both .meat-card and .container-card
  const card = selectElement.closest('.meat-card') || selectElement.closest('.container-card');
  
  if (!card) {
    return;
  }
  
  const bookOutInput = card.querySelector('.book-out-qty-input');
  
  if (!bookOutInput) {
    return;
  }
  
  const refValue = selectElement.value;
  
  if (!refValue) {
    bookOutInput.value = '0';
    return;
  }
  
  // ✅ STEP 0: Check if there's a value in the between_out_qty_map (instant lookup before save)
  const betweenOutMap = window.BATCH_DATA?.between_out_qty_map || {};
  if (betweenOutMap[refValue] !== undefined && betweenOutMap[refValue] !== null) {
    bookOutInput.value = parseFloat(betweenOutMap[refValue]).toFixed(2);
    return;
  }
  
  // ✅ STEP 1: Check if there's SAVED data (like packaging/sauce do)
  const savedContainers = window.BATCH_DATA?.saved_batch_containers || [];
  const savedContainer = savedContainers.find(c => {
    const id = c.container_id || c.batch_ref;
    return id === refValue;
  });
  
  if (savedContainer && savedContainer.book_out_qty !== undefined && savedContainer.book_out_qty !== null) {
    // Use saved value
    bookOutInput.value = parseFloat(savedContainer.book_out_qty).toFixed(2);
    return;
  }
  
  // ✅ STEP 2: No saved data - check for NEW transactions from today
  const prodDate = window.BATCH_DATA?.production_date;
  if (!prodDate) {
    bookOutInput.value = '0';
    return;
  }
  
  // Convert production_date to YYYY-MM-DD format for comparison
  const [day, month, year] = prodDate.split('/');
  const normalizedProdDate = `${year}-${month}-${day}`;
  
  // Get all stock transactions
  const stockTransactions = window.BATCH_DATA?.stock_transactions || [];
  
  // ✅ ONLY populate if transaction was created TODAY
  const matchingTx = stockTransactions.find(tx => 
    tx.batch_ref === refValue && 
    tx.transaction_type === 'OUT' &&
    tx.transaction_date === normalizedProdDate  // ← ONLY TODAY
  );
  
  if (matchingTx && parseFloat(matchingTx.quantity) > 0) {
    bookOutInput.value = parseFloat(matchingTx.quantity) || '0';
  } else {
    bookOutInput.value = '0';
  }
}

/* ============================================================ */
/* TAB SWITCHING */
/* ============================================================ */

window.showTab = function(event, tabName) {
  event.preventDefault();
  
  // HIDE all tabs first
  const tabs = document.querySelectorAll('.tab-content');
  tabs.forEach(tab => {
    tab.style.display = 'none';
    tab.classList.remove('active');
  });
  
  const buttons = document.querySelectorAll('.tab-btn');
  buttons.forEach(btn => btn.classList.remove('active'));
  
  // SHOW the selected tab
  const selectedTab = document.getElementById(tabName);
  if (selectedTab) {
    selectedTab.style.display = 'block';
    selectedTab.classList.add('active');
  }
  
  event.target.classList.add('active');
  
  const activeTabInput = document.getElementById('active_tab_input');
  if (activeTabInput) {
    activeTabInput.value = tabName;
  }
  
  // ❌ REMOVE THIS LINE:
  // loadSavedData();
};

window.switchMeatSourceAndAdd = function(event, source) {
  event.preventDefault();
  window.currentMeatSource = source;
  
  document.querySelectorAll('.btn-source-toggle').forEach(btn => {
    btn.classList.remove('active');
  });
  event.target.classList.add('active');
  
  addContainerCard();
};

window.currentMeatSource = 'import';

/* ============================================================ */
/* CALCULATION FUNCTIONS */
/* ============================================================ */

window.calculateWasteDefrostFilling = function() {
  const defrostedInputs = document.querySelectorAll('input[name="kg_frozen_meat_used[]"]');
  let totalDefrosted = 0;
  defrostedInputs.forEach(input => {
    totalDefrosted += parseFloat(input.value) || 0;
  });
  
  const totalMeatFilledInput = document.querySelector('input[name="total_meat_filled"]');
  const totalMeatFilled = parseFloat(totalMeatFilledInput ? totalMeatFilledInput.value : 0) || 0;
  
  const wasteFillPercentage = totalDefrosted > 0 ? ((totalDefrosted - totalMeatFilled) / totalDefrosted) * 100 : 0;
  
  const wasteFillingInputs = document.querySelectorAll('input[name="waste_factor[]"]');
  wasteFillingInputs.forEach(input => {
    input.value = wasteFillPercentage.toFixed(2);
  });
  
};

window.calculateWasteDefrostPouch = function() {
  let totalShiftQty = 0;
  if (window.BATCH_DATA && window.BATCH_DATA.all_batches) {
    window.BATCH_DATA.all_batches.forEach(batch => {
      totalShiftQty += parseFloat(batch.shift_total) || 0;
    });
  }
  
  let totalFrozenFresh = 0;
  document.querySelectorAll('input[name="kg_frozen_meat_used[]"]').forEach(input => {
    totalFrozenFresh += parseFloat(input.value) || 0;
  });
  
  const fillingWeight = parseFloat(document.querySelector('input[name="filling_weight_per_pouch"]')?.value) || 0;
  const expectedOutput = totalShiftQty * fillingWeight;
  
  let pouchActualLoss = 0;
  if (totalFrozenFresh > 0) {
    pouchActualLoss = ((totalFrozenFresh - expectedOutput) / totalFrozenFresh) * 100;
  }
  
  document.querySelectorAll('input[name="waste_factor_pouch[]"]').forEach(input => {
    input.value = pouchActualLoss.toFixed(2);
  });
};

window.calculateMachineTotal = function() {
  const fields = ['seal_creeps', 'unsealed_poor_seal', 'screwed_and_undated', 'over_weight', 'under_weight', 'empty_pouches', 'metal_detection'];
  let total = 0;
  fields.forEach(name => {
    const el = document.querySelector(`input[name="${name}"]`);
    if (el && el.value) {
      total += Number(el.value) || 0;
    }
  });
  
  const machineTotal = document.getElementById('machine_total');
  if (machineTotal) machineTotal.value = total;
  
  // Update yellow summary box
  const machineCount = parseFloat(document.querySelector('input[name="machine_count"]')?.value || 0);
  const balance = machineCount - total;
  
  const displayMachineCount = document.getElementById('display_machine_count');
  const displayMachineWaste = document.getElementById('display_machine_waste');
  const displayRetortReady = document.getElementById('display_retort_ready');
  
  if (displayMachineCount) displayMachineCount.textContent = machineCount;
  if (displayMachineWaste) displayMachineWaste.textContent = total;
  if (displayRetortReady) displayRetortReady.textContent = balance;
};

window.calculateRetortTotal = function() {
  const fields = ['total_unclear_coding', 'retort_seal_creap', 'retort_under_weight', 'poor_ceiling_destroyed'];
  let total = 0;
  fields.forEach(name => {
    const el = document.querySelector(`input[name="${name}"]`);
    if (el && el.value) {
      total += Number(el.value) || 0;
    }
  });
  
  const retortTotal = document.getElementById('retort_total');
  if (retortTotal) retortTotal.value = total;
};

window.calculateUsageForDay = function() {
  // ✅ CHECK IF AMENDED OPENING IS ACTIVE
  const checkbox = document.querySelector('input[name="cancel_opening_balance"]');
  const openingInput = document.querySelector('input[name="opening_balance"]');
  const amendedInput = document.getElementById('amended_opening_input');
  const mixedInput = document.querySelector('input[name="sauce_mixed"]');
  const closingInput = document.querySelector('input[name="closing_balance"]');
  const usageOutput = document.getElementById('usage_for_day');
  
  // Use amended if checked, otherwise use regular opening
  let opening = 0;
  if (checkbox.checked && amendedInput && amendedInput.value) {
    opening = parseFloat(amendedInput.value) || 0;
  } else {
    opening = parseFloat(openingInput ? openingInput.value : 0) || 0;
  }
  
  const mixed = parseFloat(mixedInput ? mixedInput.value : 0) || 0;
  const closing = parseFloat(closingInput ? closingInput.value : 0) || 0;
  
  const usage = opening + mixed - closing;
  if (usageOutput) usageOutput.value = Math.max(0, usage).toFixed(2);
  
};


/* ============================================================ */
/* INITIALIZATION */
/* ============================================================ */

function initializeTabs() {
  
  const certTab = document.getElementById('cert');
  const certBtn = document.querySelector('.tab-btn[onclick*="\'cert\'"]');
  const meatTab = document.getElementById('meat');
  const meatBtn = document.querySelector('.tab-btn[onclick*="\'meat\'"]');
  
  // First HIDE ALL tabs
  document.querySelectorAll('.tab-content').forEach(tab => {
    tab.style.display = 'none';
    tab.classList.remove('active');
  });
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.remove('active');
  });
  
  if (!window.BATCH_DATA?.requires_certification) {
    if (certTab) certTab.style.display = 'none';
    if (certBtn) certBtn.style.display = 'none';
    
    // Show Meat
    if (meatTab) {
      meatTab.style.display = 'block';
      meatTab.classList.add('active');
    }
    if (meatBtn) {
      meatBtn.classList.add('active');
    }
    
  } else {
	
    // ✅ ADD THIS:
    renderSummaryTab();
  
    // Show Cert
    if (certTab) {
      certTab.style.display = 'block';
      certTab.classList.add('active');
    }
    if (certBtn) {
      certBtn.classList.add('active');
    }
  }
  
}

function initializeCalculations() {
  
  // Calculate machine total on load
  calculateMachineTotal();
  
  // Calculate retort total on load
  calculateRetortTotal();
  
  // Calculate usage for day on load
  calculateUsageForDay();
  
}

function initializeFileInputs() {
}

