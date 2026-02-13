/**
 * Inventory Batch Tracker with Category Filtering
 * Shows all transactions (In/Out/Production) per batch with calculations
 */

window.InventoryApp = class {
    constructor(data) {
        this.data = data;
        this.groupedByBatch = data.grouped_by_batch || {};
        this.categories = data.categories_data || [];
        this.currentCategory = null;
        this.currentSubcategory = null;
        this.resultsContainer = null;

    }

    init() {
        this.resultsContainer = document.querySelector('.results-content');
        
        if (!this.resultsContainer) {

            return;
        }

        // Restore filters from querystring
        const params = new URLSearchParams(window.location.search);
        const cat = params.get('category');
        const sub = params.get('subcategory');

        if (cat) {
            this.currentCategory = Number(cat);
        }
        if (sub) {
            this.currentSubcategory = Number(sub);
        }
        
        // Also check for stored filter state in sessionStorage (in case URL params got stripped)
        const storedCategory = sessionStorage.getItem('inventory_currentCategory');
        const storedSubcategory = sessionStorage.getItem('inventory_currentSubcategory');
        
        if (!cat && storedCategory) {
            this.currentCategory = Number(storedCategory);
        }
        if (!sub && storedSubcategory) {
            this.currentSubcategory = Number(storedSubcategory);
        }

        this.render();
    }

    render() {





        // Clear existing content
        this.resultsContainer.innerHTML = '';

        // Create main structure
        const wrapper = document.createElement('div');
        wrapper.className = 'inventory-app-wrapper';
        
        // Add action buttons
        wrapper.appendChild(this.createActionButtons());

        // Add category tabs
        wrapper.appendChild(this.createCategoryTabs());

        // Add batch tracker container
        wrapper.appendChild(this.createBatchTrackerContainer());

        this.resultsContainer.appendChild(wrapper);

        // Apply filters and render batches
        this.updateCategoryTabs();
        if (this.currentCategory) {
            // Show sub-tabs for the current category
            const currentCategoryObj = this.categories.find(
                c => Number(c.id) === Number(this.currentCategory)
            );
            this.updateSubTabs(currentCategoryObj || null);
            this.updateSubTabHighlight();
        }

        this.renderBatches();

    }

    buildNextUrl() {
        /**
         * Build the filtered changelist URL with current category and subcategory
         * This ensures the next parameter includes all active filters
         */
        const params = new URLSearchParams();
        if (this.currentCategory) params.set('category', this.currentCategory);
        if (this.currentSubcategory) params.set('subcategory', this.currentSubcategory);
        const qs = params.toString();
        return qs
            ? `/admin/inventory/stocktransaction/?${qs}`
            : `/admin/inventory/stocktransaction/`;
    }

    createActionButtons() {
        const container = document.createElement('div');
        container.className = 'inventory-actions';
        container.style.display = 'flex';
        container.style.justifyContent = 'space-between';
        container.style.alignItems = 'center';
        
        // LEFT: Booking buttons group
        const leftGroup = document.createElement('div');
        leftGroup.style.display = 'flex';
        leftGroup.style.gap = '30px';
        
        const localBookingBtn = document.createElement('button');
        localBookingBtn.className = 'btn-action btn-booking-in';
        localBookingBtn.innerHTML = '+ Local Book In';
        localBookingBtn.type = 'button';
        localBookingBtn.addEventListener('click', () => {
            const params = new URLSearchParams();
            params.set('transaction_type', 'IN');
            if (this.currentCategory)    params.set('category', this.currentCategory);
            if (this.currentSubcategory) params.set('subcategory', this.currentSubcategory);

            // Get the site slug from the current URL path
            const pathMatch = window.location.pathname.match(/\/hq\/([^/]+)\//);
            const sitePath = pathMatch ? `/hq/${pathMatch[1]}` : '';
            window.location.href = `${sitePath}/admin/inventory/stocktransaction/add/?${params.toString()}`;
        });

        const importBookingBtn = document.createElement('button');
        importBookingBtn.className = 'btn-action btn-booking-in';
        importBookingBtn.innerHTML = '+ Import Book In';
        importBookingBtn.type = 'button';
        importBookingBtn.addEventListener('click', () => {
            const params = new URLSearchParams();
            if (this.currentCategory)    params.set('category', this.currentCategory);
            if (this.currentSubcategory) params.set('subcategory', this.currentSubcategory);

            // Get the site slug from the current URL path
            const pathMatch = window.location.pathname.match(/\/hq\/([^/]+)\//);
            const sitePath = pathMatch ? `/hq/${pathMatch[1]}` : '';
            window.location.href = `${sitePath}/admin/inventory/container/add/?${params.toString()}`;
        });
        
        leftGroup.appendChild(localBookingBtn);
        leftGroup.appendChild(importBookingBtn);
        
        // RIGHT: Archive button
        const currentUrl = window.location.href;
        const isArchived = currentUrl.includes('is_archived=1');

        const archiveBtn = document.createElement('a');
        archiveBtn.className = isArchived ? 'btn-action btn-archive-active' : 'btn-action btn-archive';  // ✅ Use CSS classes
        archiveBtn.textContent = isArchived ? 'Active' : 'Archived';
        archiveBtn.href = isArchived ? '?' : '?is_archived=1';

        container.appendChild(leftGroup);
        container.appendChild(archiveBtn);

        return container;
    }

    createCategoryTabs() {
		const container = document.createElement('div');
		container.className = 'inventory-tabs-container';

		const mainTabsDiv = document.createElement('div');
		mainTabsDiv.className = 'category-tabs main-tabs';

		// All tab
		const allTab = document.createElement('div');
		allTab.className = 'category-tab active';
		allTab.textContent = 'All Items';
		allTab.addEventListener('click', () => {
			this.filterByCategory(null);
			this.updateSubTabs(null);
			
			// Clear session storage when viewing all items
			sessionStorage.removeItem('inventory_currentCategory');
			sessionStorage.removeItem('inventory_currentSubcategory');
			
			// Update URL to remove all filters
			window.history.pushState({}, '', '/admin/inventory/stocktransaction/');
		});
		mainTabsDiv.appendChild(allTab);

		// Main category tabs
		this.categories.forEach(category => {
			const tab = document.createElement('div');
			tab.className = 'category-tab';
			tab.textContent = category.name;
			tab.dataset.categoryId = category.id;
			tab.addEventListener('click', () => {
				this.filterByCategory(Number(category.id));
				this.updateSubTabs(category);
				
				// ✅ SAVE TO SESSION STORAGE AS BACKUP
				sessionStorage.setItem('inventory_currentCategory', this.currentCategory);
				sessionStorage.setItem('inventory_currentSubcategory', this.currentSubcategory || '');

				// Update URL to include category parameter
				const params = new URLSearchParams();
				if (this.currentCategory) params.set('category', this.currentCategory);
				const qs = params.toString();
				const newUrl = qs 
					? `/admin/inventory/stocktransaction/?${qs}` 
					: `/admin/inventory/stocktransaction/`;
				window.history.pushState({}, '', newUrl);
			});
			mainTabsDiv.appendChild(tab);
		});

		container.appendChild(mainTabsDiv);

		// Sub-tabs container (hidden initially)
		const subTabsDiv = document.createElement('div');
		subTabsDiv.className = 'category-tabs sub-tabs';
		subTabsDiv.id = 'sub-tabs-container';
		subTabsDiv.style.display = 'none';
		container.appendChild(subTabsDiv);

		return container;
	}

	createBatchTrackerContainer() {
		const container = document.createElement('div');
		container.className = 'batch-tracker-container';
		container.id = 'batch-tracker';
		return container;
	}

	updateSubTabs(category) {
		const subTabsContainer = document.getElementById('sub-tabs-container');
		subTabsContainer.innerHTML = '';

		if (!category) {
			subTabsContainer.style.display = 'none';
			this.currentSubcategory = null;
			return;
		}

		if (!category.subcategories || category.subcategories.length === 0) {
			subTabsContainer.style.display = 'none';
			this.currentSubcategory = null;
			return;
		}

		subTabsContainer.style.display = 'flex';

		// Only show specific sub-category tabs
		category.subcategories.forEach((subcat, index) => {
			const subTab = document.createElement('div');
			subTab.className = 'category-tab sub-tab';
			subTab.textContent = subcat.name;
			subTab.dataset.subcategoryId = subcat.id;
			
			subTab.onclick = (e) => {
				e.preventDefault();
				e.stopPropagation();



				this.currentSubcategory = Number(subcat.id);


				// ✅ SAVE TO SESSION STORAGE AS BACKUP (in case URL params get stripped)
				sessionStorage.setItem('inventory_currentCategory', this.currentCategory);
				sessionStorage.setItem('inventory_currentSubcategory', this.currentSubcategory);

				this.updateSubTabHighlight();
				
				// Update URL to include subcategory parameter
				const params = new URLSearchParams();
				if (this.currentCategory) params.set('category', this.currentCategory);
				if (this.currentSubcategory) params.set('subcategory', this.currentSubcategory);
				const qs = params.toString();
				const newUrl = qs 
					? `/admin/inventory/stocktransaction/?${qs}` 
					: `/admin/inventory/stocktransaction/`;


				window.history.pushState({}, '', newUrl);

				this.renderBatches();
			};
			
			subTabsContainer.appendChild(subTab);
		});
	}

    updateSubTabHighlight() {
        const subTabs = document.querySelectorAll('.sub-tab');
        subTabs.forEach(tab => {
            tab.classList.remove('active');
            if (Number(tab.dataset.subcategoryId) === Number(this.currentSubcategory)) {
                tab.classList.add('active');
            }
        });
    }

    shouldDisplayRow(entry) {
        // No main category filter: show all
        if (!this.currentCategory) return true;

        // Must match the category
        if (Number(entry.category_id) !== Number(this.currentCategory)) {
            return false;
        }

        // If sub-category is selected, must match sub_category_id
        if (this.currentSubcategory) {
            const match = Number(entry.sub_category_id) === Number(this.currentSubcategory);

            return match;
        }

        // Category matches, no sub-category filter
        return true;
    }

    filterByCategory(categoryId) {

        this.currentCategory = categoryId;
        this.currentSubcategory = null;
        this.updateCategoryTabs();
        this.renderBatches();
    }

    updateCategoryTabs() {
        const tabs = document.querySelectorAll('.category-tabs.main-tabs .category-tab');
        tabs.forEach(tab => {
            tab.classList.remove('active');
            if (!this.currentCategory && tab.textContent === 'All Items') {
                tab.classList.add('active');
            } else if (tab.dataset.categoryId && Number(tab.dataset.categoryId) === Number(this.currentCategory)) {
                tab.classList.add('active');
            }
        });
    }

    renderBatches() {

        const container = document.getElementById('batch-tracker');
        container.innerHTML = '';

        const batches = Object.entries(this.groupedByBatch);

        if (batches.length === 0) {
            container.innerHTML = '<p style="text-align: center; padding: 20px;">No stock transactions found</p>';
            return;
        }

        batches.forEach(([batchRef, itemsData]) => {
            this.renderBatchSection(container, batchRef, itemsData);
        });
    }

    renderBatchSection(container, batchRef, itemsData) {
		const batchSection = document.createElement('div');
		batchSection.className = 'batch-section';

		// Get all entries for this batch
		let allEntries = [];
		Object.entries(itemsData).forEach(([itemName, entries]) => {
			entries.forEach(entry => {
				if (this.shouldDisplayRow(entry)) {
					allEntries.push({ ...entry, itemName });
				}
			});
		});

		if (allEntries.length === 0) return;
	
        // Action buttons at top
        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'batch-actions';

        const bookOutBtn = document.createElement('button');
        bookOutBtn.className = 'btn-batch-action btn-book-out';
        bookOutBtn.innerHTML = '⬇ Book Out';
        bookOutBtn.addEventListener('click', () => {
            const params = new URLSearchParams();
            params.set('transaction_type', 'OUT');
            params.set('batch_ref', batchRef);
            if (this.currentCategory)    params.set('category', this.currentCategory);
            if (this.currentSubcategory) params.set('subcategory', this.currentSubcategory);

            // Get the site slug from the current URL path
            const pathMatch = window.location.pathname.match(/\/hq\/([^/]+)\//);
            const sitePath = pathMatch ? `/hq/${pathMatch[1]}` : '';
            window.location.href = `${sitePath}/admin/inventory/stocktransaction/add/?${params.toString()}`;
        });

        const amendmentBtn = document.createElement('button');
        amendmentBtn.className = 'btn-batch-action btn-batch-amendment';
        amendmentBtn.innerHTML = '✎ Amendment';
        amendmentBtn.addEventListener('click', () => {
            const params = new URLSearchParams();
            params.set('batch_ref', batchRef);
            if (this.currentCategory)    params.set('category', this.currentCategory);
            if (this.currentSubcategory) params.set('subcategory', this.currentSubcategory);

            // Get the site slug from the current URL path
            const pathMatch = window.location.pathname.match(/\/hq\/([^/]+)\//);
            const sitePath = pathMatch ? `/hq/${pathMatch[1]}` : '';
            window.location.href = `${sitePath}/admin/inventory/amendment/add/?${params.toString()}`;
        });
        
        // ✅ ADD ARCHIVE/RESTORE BUTTON
        const isArchived = window.location.href.includes('is_archived=1');
        const archiveBtn = document.createElement('button');
        archiveBtn.className = 'btn-batch-action';
        archiveBtn.style.background = isArchived ? '#28a745' : '#6c757d';
        archiveBtn.style.color = 'white';
        archiveBtn.innerHTML = isArchived ? '↩ Restore' : '📦 Archive';
        archiveBtn.addEventListener('click', () => {
            if (confirm(`${isArchived ? 'Restore' : 'Archive'} this batch group (${batchRef})?`)) {
                const pathMatch = window.location.pathname.match(/\/hq\/([^/]+)\//);
                const sitePath = pathMatch ? `/hq/${pathMatch[1]}` : '';
                fetch(`${sitePath}/admin/inventory/stocktransaction/archive-batch/?batch_ref=${encodeURIComponent(batchRef)}&action=${isArchived ? 'restore' : 'archive'}`, {
                    method: 'POST',
                    headers: {'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value}
                }).then(() => window.location.reload());
            }
        });

        actionsDiv.appendChild(bookOutBtn);
        actionsDiv.appendChild(amendmentBtn);
        actionsDiv.appendChild(archiveBtn);  
        batchSection.appendChild(actionsDiv);

        // Table
        const table = document.createElement('table');
        table.className = 'batch-tracker-table';

        const thead = document.createElement('thead');
        thead.innerHTML = `
            <tr>
                <th>Supplier</th>
                <th>Batch</th>
                <th>Stock Item</th>
                <th>Unit</th>
                <th>Warehouse</th>
                <th>Dates</th>
                <th>Prod Batch</th>
                <th>ACTIVITY</th>
                <th>QTY</th>
                <th>Comments</th>
            </tr>
        `;
        table.appendChild(thead);

        const tbody = document.createElement('tbody');

		/// Group entries by item for display
		const itemGroups = {};
		allEntries.forEach(entry => {
			if (!itemGroups[entry.itemName]) {
				itemGroups[entry.itemName] = [];
			}
			itemGroups[entry.itemName].push(entry);
		});

		Object.entries(itemGroups).forEach(([itemName, entries]) => {
			// Get FIRST entry to show Unit + Warehouse (not repeated)
			const firstEntry = entries[0];
			
			// **PRESERVE FIRST ENTRY'S SUPPLIER** ← KEY FIX
			const supplierName = firstEntry.supplier_name || '-';
			
			// Sort entries oldest → newest by transaction_date / date
			entries.sort((a, b) => {
				const da = new Date(a.transaction_date || a.date);
				const db = new Date(b.transaction_date || b.date);
				return da - db;
			});

			entries.forEach((entry, idx) => {
				const row = tbody.insertRow();
				
				// Supplier (first row of item only) - USE THE PRESERVED SUPPLIER
				if (idx === 0) {
					const supplierCell = row.insertCell();
					supplierCell.textContent = supplierName;  // ← USE PRESERVED VALUE
					supplierCell.rowSpan = entries.length;
					supplierCell.className = 'cell-supplier';
				}

				// Batch (first row of item only)
				if (idx === 0) {
					const batchCell = row.insertCell();
					batchCell.textContent = entry.batch_ref || '-';
					batchCell.rowSpan = entries.length;
					batchCell.className = 'cell-batch';
				}

				// Stock Item (first row of item only)
				if (idx === 0) {
					const itemCell = row.insertCell();
					itemCell.textContent = itemName;
					itemCell.rowSpan = entries.length;
					itemCell.className = 'cell-item';
				}

				// Unit (first row of item only) - NOW WITH rowSpan
				if (idx === 0) {
					const unitCell = row.insertCell();
					unitCell.textContent = firstEntry.unit_of_measure || 'Unit';
					unitCell.rowSpan = entries.length;  // ← ADD THIS
					unitCell.className = 'cell-unit';
				}

				// Warehouse (first row of item only) - NOW WITH rowSpan
				if (idx === 0) {
					const warehouseCell = row.insertCell();
					warehouseCell.textContent = firstEntry.warehouse || '-';
					warehouseCell.rowSpan = entries.length;  // ← ADD THIS
					warehouseCell.className = 'cell-warehouse';
				}

				// Dates
				const dateCell = row.insertCell();
				dateCell.textContent = this.formatDate(entry.transaction_date || entry.date);
				dateCell.className = 'cell-date';

				// Prod Batch - Format with line breaks if multiple batches
				const prodBatchCell = row.insertCell();
				if (entry.prod_batch) {
					const batches = entry.prod_batch.split(', ');
					prodBatchCell.innerHTML = batches.join('<br>');
				} else {
					prodBatchCell.textContent = '-';
				}
				prodBatchCell.className = 'cell-prod-batch';

				// Activity
        const activityCell = row.insertCell();
        activityCell.className = 'cell-activity';
        activityCell.style.cursor = 'pointer';

        if (entry.type === 'transaction') {
            const transType = entry.transaction_type === 'IN' ? 'Booking In' : 'Booking Out';
            const typeClass = entry.transaction_type === 'IN' ? 'activity-booking-in' : 'activity-booking-out';
            const link = document.createElement('span');
            link.className = typeClass;
            link.textContent = transType;
            link.style.cursor = 'pointer';
            link.style.textDecoration = 'underline';
            link.addEventListener('click', (e) => {
                e.stopPropagation();
                const nextUrl = this.buildNextUrl();
                const pathMatch = window.location.pathname.match(/\/hq\/([^/]+)\//);
                const sitePath = pathMatch ? `/hq/${pathMatch[1]}` : '';
                window.location.href =
                    `${sitePath}/admin/inventory/stocktransaction/${entry.id}/change/?transaction_type=${entry.transaction_type}` +
                    `&next=${encodeURIComponent(nextUrl)}`;
            });
            activityCell.appendChild(link);
        } else if (entry.type === 'container') {
            const link = document.createElement('span');
            link.className = 'activity-booking-in';
            link.textContent = entry.activity || 'Booking In';
            link.style.cursor = 'pointer';
            link.style.textDecoration = 'underline';
            link.addEventListener('click', (e) => {
                e.stopPropagation();
                const nextUrl = this.buildNextUrl();
                const url = new URL(entry.edit_url, window.location.origin);
                url.searchParams.set('next', nextUrl);
                window.location.href = url.toString();
            });
            activityCell.appendChild(link);
        } else if (entry.type === 'amendment') {
            const amendType = entry.amendment_type === 'IN' ? 'Booking Back In' : 'Extra Use';
            const link = document.createElement('span');
            link.className = 'activity-amendment';
            link.textContent = amendType;
            link.style.cursor = 'pointer';
            link.style.textDecoration = 'underline';
            link.addEventListener('click', (e) => {
                e.stopPropagation();
                const nextUrl = this.buildNextUrl();
                const pathMatch = window.location.pathname.match(/\/hq\/([^/]+)\//);
                const sitePath = pathMatch ? `/hq/${pathMatch[1]}` : '';
                window.location.href =
                    `${sitePath}/admin/inventory/amendment/${entry.id}/change/?next=${encodeURIComponent(nextUrl)}`;
            });
            activityCell.appendChild(link);
        } else if (entry.type === 'manufacturing') {
            const link = document.createElement('span');
            link.className = 'activity-production-out';
            link.textContent = 'Production Out';
            link.style.cursor = 'pointer';
            link.style.textDecoration = 'underline';
            activityCell.appendChild(link);
        } else {
            activityCell.textContent = entry.type;
        }

                // QTY
                const qtyCell = row.insertCell();
                const isPositive = (entry.transaction_type === 'IN' || entry.amendment_type === 'IN');
                
                // ✅ PRODUCTION OUT gets ORANGE color
                let qtyClass = 'qty-negative';  // Default for OUT
                if (isPositive) {
                    qtyClass = 'qty-positive';  // Green for IN
                } else if (entry.type === 'manufacturing') {
                    qtyClass = 'qty-production-out';  // Orange for Production OUT
                }
                
                qtyCell.innerHTML = `<span class="${qtyClass}">${isPositive ? '+' : '-'}${Math.abs(entry.quantity).toFixed(2)}</span>`;
                qtyCell.className = 'cell-qty';

                // Comments
                const commentsCell = row.insertCell();
                if (entry.type === 'transaction') {
                    commentsCell.textContent = entry.usage_notes || '-';
                } else {
                    commentsCell.textContent = entry.reason || '-';
                }
                commentsCell.className = 'cell-comments';

                // Make the entire row clickable (except activity links)
                row.style.cursor = 'pointer';
                row.addEventListener('click', (e) => {
                    // Don't override clicks on interactive elements
                    if (e.target.closest('a, button') || e.target.closest('.cell-activity') || e.target.tagName === 'A') return;
                    const nextUrl = this.buildNextUrl();
                    
                    // ✅ DEBUG ROW CLICK




                    if (entry.type === 'transaction') {
                        const pathMatch = window.location.pathname.match(/\/hq\/([^/]+)\//);
                        const sitePath = pathMatch ? `/hq/${pathMatch[1]}` : '';
                        const finalUrl = `${sitePath}/admin/inventory/stocktransaction/${entry.id}/change/?transaction_type=${entry.transaction_type}&next=${encodeURIComponent(nextUrl)}`;

                        window.location.href = finalUrl;
                    } else if (entry.type === 'container') {
                        const url = new URL(entry.edit_url, window.location.origin);
                        url.searchParams.set('next', nextUrl);
                        window.location.href = url.toString();
                    } else if (entry.type === 'amendment') {
                        const pathMatch = window.location.pathname.match(/\/hq\/([^/]+)\//);
                        const sitePath = pathMatch ? `/hq/${pathMatch[1]}` : '';
                        const finalUrl = `${sitePath}/admin/inventory/amendment/${entry.id}/change/?next=${encodeURIComponent(nextUrl)}`;
                        window.location.href = finalUrl;
                    }
                });
            });
        });

        table.appendChild(tbody);
        batchSection.appendChild(table);

        // Summary row
        const summaryRow = this.createSummaryRow(allEntries);
        batchSection.appendChild(summaryRow);

        container.appendChild(batchSection);
    }

        createSummaryRow(entries) {
			const summaryDiv = document.createElement('div');
			summaryDiv.className = 'batch-summary';

			let bookingIn = 0;          // Single IN for this batch
			let bookingOutTotal = 0;    // Booking Out + amendments
			let totalProduction = 0;    // Production Out only
			let amendmentIn = 0;        // Amendment IN (booking back in)
			let amendmentOut = 0;       // Amendment OUT (extra use)

			entries.forEach(entry => {
				if (entry.type === 'transaction') {
					if (entry.transaction_type === 'IN') {
						// Only one per batch – just take its (possibly amended) quantity
						bookingIn = entry.quantity;
					} else {
						// Booking Out (negative)
						bookingOutTotal += entry.quantity;
					}
				} else if (entry.type === 'container') {  // ← ADD THIS BLOCK
					if (entry.transaction_type === 'IN') {
						bookingIn += entry.quantity;  // ← Add container qty to booking in
					}
				} else if (entry.type === 'amendment') {
					// Include amendments in balance calculation
					if (entry.amendment_type === 'IN') {
						amendmentIn += entry.quantity;
					} else if (entry.amendment_type === 'OUT') {
						amendmentOut += entry.quantity;
					}
				} else if (entry.type === 'manufacturing') {
					totalProduction += entry.quantity;
				}
			});

			// Balance = bookingIn - (bookingOutTotal + amendmentOut - amendmentIn)
			// Amendment IN (booking back in) REDUCES total out, not adds to in
			const totalIn = bookingIn;
			const totalOut = bookingOutTotal + amendmentOut - amendmentIn;
			const balanceAvailable = totalIn - totalOut;
			const productionQtyUsed = totalProduction;
			const difference = totalOut - totalProduction;

			summaryDiv.innerHTML = `
				<div class="summary-item">
					<span class="summary-label">Booking in</span>
					<span class="summary-pill summary-pill-in">+${totalIn.toFixed(2)}</span>
				</div>
				<div class="summary-item">
					<span class="summary-label">Balance available</span>
					<span class="summary-pill summary-pill-balance">${balanceAvailable.toFixed(2)}</span>
				</div>
				<div class="summary-item">
					<span class="summary-label">Booking out</span>
					<span class="summary-pill summary-pill-out">-${totalOut.toFixed(2)}</span>
				</div>
				<div class="summary-item">
					<span class="summary-label">Production Qty used</span>
					<span class="summary-pill summary-pill-production">-${productionQtyUsed.toFixed(2)}</span>
				</div>
				<div class="summary-item">
					<span class="summary-label">Difference</span>
					<span class="summary-pill ${difference >= 0 ? 'summary-pill-diff-positive' : 'summary-pill-diff-negative'}">
						${difference.toFixed(2)}
					</span>
				</div>
			`;

			return summaryDiv;
		}


    formatDate(dateString) {
        if (!dateString) return '-';
        const date = new Date(dateString);
        return date.toLocaleDateString('en-ZA', { 
            year: 'numeric', 
            month: '2-digit', 
            day: '2-digit' 
        });
    }
};

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {

    if (window.DATA) {

        const resultsDiv = document.querySelector('.results-content');
        if (resultsDiv) {
            const app = new window.InventoryApp(window.DATA);
            app.init();
        } else {

        }
    } else {

    }
});
