// static/js/transport_documents.js - DEBUG VERSION

document.addEventListener('DOMContentLoaded', function() {

    const form = document.querySelector('#transportload_form') || 
                 document.querySelector('form[id*="form"]') ||
                 document.querySelector('form[action*="transportload"]');
    
    if (form) {
        form.setAttribute('enctype', 'multipart/form-data');

    }
    
    // Check if add-new-document button exists
    const addBtn = document.getElementById('add-new-document');

});

let newDocCounter = 0;

document.addEventListener('click', function(e) {

    // ... rest of your existing standard documents code ...
    const docTypes = ['delivery_note', 'namra', 'daff', 'meat_board', 'import_permit'];
    
    docTypes.forEach(docType => {
        if (e.target.classList.contains(`${docType}-add-row`)) {
            const containerElem = document.querySelector(`.${docType}-file-rows`);
            const list = document.querySelector(`.${docType}-doc-list`);
            if (!containerElem || !list) return;
            const input = document.createElement('input');
            input.type = 'file';
            input.name = `${docType}_file[]`;
            input.style.display = 'none';
            input.accept = '.pdf,.doc,.docx';
            input.addEventListener('change', function() {
                if (!input.files || !input.files[0]) {
                    input.remove();
                    return;
                }
                const file = input.files[0];
                const li = document.createElement('li');
                li.className = `${docType}-doc-item`;
                li.style.cssText = 'display: inline-block; margin-right: 15px; margin-bottom: 5px;';
                li.innerHTML = `
                    <span style="color: #417690; font-size: 12px;">${file.name}</span>
                    <button type="button"
                            class="${docType}-remove-row"
                            style="margin-left:5px; border:none; background:none; color:#d32f2f; font-weight:bold; cursor:pointer; font-size: 16px; padding: 0; line-height: 1;">×</button>
                `;
                li._fileInput = input;
                list.appendChild(li);
            });
            containerElem.appendChild(input);
            input.click();
        }
        if (e.target.classList.contains(`${docType}-remove-row`)) {
            const li = e.target.closest(`.${docType}-doc-item`);
            const existingId = e.target.getAttribute('data-doc-id');
            if (existingId) {
                const form = document.querySelector('#transportload_form') || 
                             document.querySelector('form[action*="transportload"]');
                if (form) {
                    const hidden = document.createElement('input');
                    hidden.type = 'hidden';
                    hidden.name = `delete_${docType}_ids[]`;
                    hidden.value = existingId;
                    form.appendChild(hidden);
                }
            }
            if (li && li._fileInput) li._fileInput.remove();
            if (li) li.remove();
        }
    });
    
    // ========== ADD NEW DOCUMENT ==========
	if (e.target.id === 'add-new-document') {

		const nameInput = document.getElementById('new-doc-name');
		const docName = nameInput.value.trim();

		if (!docName) {
			alert('Please enter a document name');
			return;
		}
		
		const newIdx = `new_${newDocCounter}`;

		newDocCounter++;
		
		const newDocRow = e.target.closest('tr');
		const tbody = newDocRow.parentElement;
		
		const tr = document.createElement('tr');
		tr.style.cssText = 'border-bottom: 1px solid #e0e0e0;';
		tr.setAttribute('data-new-doc', newIdx);
		
		tr.innerHTML = `
			<td style="padding: 10px 20px 10px 0; width: 150px; font-weight: 500; vertical-align: top;">
				<div>${docName}</div>
				<button type="button" 
						class="new-remove-category" 
						data-idx="${newIdx}"
						style="background: #d32f2f; 
							   color: white; 
							   border: none; 
							   padding: 8px 16px; 
							   cursor: pointer; 
							   border-radius: 3px; 
							   font-size: 13px; 
							   font-weight: 500;
							   margin-top: 8px;
							   margin-left: 10px;
							   display: block;
							   min-width: 80px;">
					Remove
				</button>
			</td>
			<td style="padding: 10px 0;">
				<input type="hidden" name="new_other_doc_name[]" value="${docName}">
				<ul class="other-doc-list-${newIdx}" style="list-style: none; padding: 0; margin: 0 0 8px 0;"></ul>
				<div class="other-file-rows-${newIdx}" style="display:none;"></div>
				<button type="button" 
						class="other-add-file" 
						data-idx="${newIdx}"
						style="background: #417690; 
							   color: white; 
							   border: none; 
							   padding: 6px 16px; 
							   cursor: pointer; 
							   border-radius: 3px; 
							   font-size: 12px; 
							   font-weight: 500; 
							   white-space: nowrap; 
							   min-width: 70px;
							   display: inline-block;">
					+ Add
				</button>
			</td>
		`;

		tbody.insertBefore(tr, newDocRow);
		nameInput.value = '';

	}
		
    // ========== ADD FILE TO OTHER DOCS ==========
    if (e.target.classList.contains('other-add-file')) {
        const idx = e.target.getAttribute('data-idx');

        const container = document.querySelector(`.other-file-rows-${idx}`);
        const list = document.querySelector(`.other-doc-list-${idx}`);
        
        if (!container || !list) {

            return;
        }
        
        const input = document.createElement('input');
        input.type = 'file';
        input.name = `other_file_${idx}[]`;
        input.style.display = 'none';
        input.accept = '.pdf,.doc,.docx';
        
        input.addEventListener('change', function() {
            if (!input.files || !input.files[0]) {
                input.remove();
                return;
            }
            const file = input.files[0];

            const li = document.createElement('li');
            li.className = 'other-doc-item';
            li.style.cssText = 'display: inline-block; margin-right: 15px; margin-bottom: 5px;';
            li.innerHTML = `
                <span style="color: #417690; font-size: 12px;">${file.name}</span>
                <button type="button"
                        class="other-remove-file-new"
                        style="margin-left:5px; border:none; background:none; color:#d32f2f; font-weight:bold; cursor:pointer; font-size: 16px; padding: 0; line-height: 1;">×</button>
            `;
            li._fileInput = input;
            list.appendChild(li);
        });
        
        container.appendChild(input);
        input.click();
    }
    
    // ========== REMOVE CATEGORY (existing from DB) ==========
	if (e.target.classList.contains('other-remove-category')) {

		const idx = e.target.getAttribute('data-idx');
		const tr = e.target.closest('tr');
		
		const form = document.querySelector('#transportload_form') || 
					 document.querySelector('form[action*="transportload"]');
		if (form) {
			const hidden = document.createElement('input');
			hidden.type = 'hidden';
			hidden.name = 'remove_other_category[]';
			hidden.value = idx;
			form.appendChild(hidden);

		}
		
		tr.remove();
	}

	// ========== REMOVE NEW CATEGORY (not yet saved) ==========
	if (e.target.classList.contains('new-remove-category')) {
		e.target.closest('tr').remove();
	}

});
