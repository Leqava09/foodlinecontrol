(function($) {
    $(function() {
        var $batchField = $('#id_batch_costings');
        var $target = $('.batch_pricing_preview_container .grp-readonly');
        var $qtyHidden = $('#id_qty_for_invoice_data');

        // Hide the qty_for_invoice_data field completely
        $('textarea[name="qty_for_invoice_data"]').closest('.grp-row').hide();

        // Make billing method checkboxes act like radio buttons
        var $billingCheckboxes = $('input[name="bill_per_primary"], input[name="bill_per_secondary"], input[name="bill_per_pallet"]');
        
        $billingCheckboxes.on('change', function() {
            if ($(this).is(':checked')) {
                $billingCheckboxes.not(this).prop('checked', false);
            }
            // Update preview links with current billing method for live preview
            updatePreviewLinks();
        });
        
        // Function to update all billing preview links with current billing method
        function updatePreviewLinks() {
            var billingMethod = '';
            if ($('input[name="bill_per_primary"]').is(':checked')) {
                billingMethod = 'primary';
            } else if ($('input[name="bill_per_secondary"]').is(':checked')) {
                billingMethod = 'secondary';
            } else if ($('input[name="bill_per_pallet"]').is(':checked')) {
                billingMethod = 'pallet';
            }
            
            // Update all preview links (eye icons)
            $('a.billing-preview-link').each(function() {
                var $link = $(this);
                var href = $link.attr('href');
                if (!href) return;
                
                // Remove existing billing_method param
                var baseUrl = href.split('?')[0];
                
                // Add new billing_method param if one is selected
                if (billingMethod) {
                    $link.attr('href', baseUrl + '?billing_method=' + billingMethod);
                } else {
                    $link.attr('href', baseUrl);
                }
            });
        }
        
        // Run once on page load to set initial state
        updatePreviewLinks();

        // ✨ DYNAMIC DELIVERY INSTITUTION FILTERING BASED ON CLIENT SELECTION
        var $clientField = $('#id_client');
        var $institutionField = $('#id_delivery_institution');
        
        if ($clientField.length && $institutionField.length) {
            // Store the original options so we can reset/restore them
            var allOptions = $institutionField.find('option').clone();
            
            // Function to fetch and update institutions for selected client
            function updateInstitutions() {
                var clientId = $clientField.val();
                
                if (!clientId) {
                    // No client selected - show all institutions
                    $institutionField.empty().html(allOptions);
                    return;
                }
                
                // Fetch institutions for this client
                $.ajax({
                    url: '/inventory/api/delivery-sites/',
                    data: {client_id: clientId},
                    dataType: 'json',
                    success: function(data) {
                        var sites = data.sites || [];
                        var currentSelection = $institutionField.val();
                        
                        // Rebuild dropdown with only this client's sites
                        $institutionField.empty().append(
                            $('<option value="">---------</option>')
                        );
                        
                        sites.forEach(function(site) {
                            $institutionField.append(
                                $('<option></option>')
                                    .attr('value', site.id)
                                    .text(site.name)
                            );
                        });
                        
                        // Restore previous selection if it still exists
                        if (currentSelection) {
                            $institutionField.val(currentSelection);
                        }
                    },
                    error: function() {
                        $institutionField.empty().append(
                            $('<option value="">Error loading institutions</option>')
                        );
                    }
                });
            }
            
            // Update institutions when client changes
            $clientField.on('change', updateInstitutions);
            
            // Trigger on page load if client is already selected
            if ($clientField.val()) {
                updateInstitutions();
            }
        }

        if (!$batchField.length || !$target.length) {
            return;
        }

        function serializeQtyInputs() {
            if (!$qtyHidden.length) return;
            
            var data = {};
            var seenKeys = {};
            
            $target.find('input.qty-for-invoice-input').each(function() {
                var $input = $(this);
                var key = $input.data('batch-number');
                var val = $input.val();
                
                if (key && !seenKeys[key]) {
                    data[key] = val || null;
                    seenKeys[key] = true;
                }
            });
            
            $qtyHidden.val(JSON.stringify(data));
        }

        function loadBatchPricing() {
            var batchIds = $batchField.val();

            if (!batchIds || batchIds.length === 0) {
                $target.html('Select one or more Production Dates to see pricing.');
                if ($qtyHidden.length) {
                    $qtyHidden.val('{}');
                }
                return;
            }

            $target.html('Loading...');

            var billingId = '';
            var urlMatch = window.location.pathname.match(/\/billingdocumentheader\/(\d+)\//);
            if (urlMatch) {
                billingId = urlMatch[1];
            }

            var apiUrl = '/costing/api/batch-pricing-preview/' + batchIds.join(',') + '/';
            if (billingId) {
                apiUrl += '?billing_id=' + billingId;
            }

            $.get(apiUrl)
                .done(function(data) {
                    if (data.rows && data.rows.length) {
                        var existing = {};
                        try {
                            var currentVal = $qtyHidden.val();
                            var initialVal = $('input[name="initial-qty_for_invoice_data"]').val();
                            
                            existing = JSON.parse(currentVal || initialVal || '{}');
                        } catch (e) {

                        }

                        var rows = '';
                        data.rows.forEach(function(row, idx) {
                            var key = row.batch_number;
                            var existingVal = existing[key] || '';

                            rows += '<tr>' +
                                '<td style="padding:4px 10px;">' + row.batch_number + '</td>' +
                                '<td style="padding:4px 10px; min-width:260px; max-width:360px; white-space:normal;">' + row.product + '</td>' +
                                '<td style="padding:4px 10px; min-width:50px;">' + row.size + '</td>' +
                                '<td style="padding:4px 10px; text-align:right;">' + row.units + '</td>' +
                                '<td style="padding:4px 10px;">' + row.status + '</td>' +
                                '<td style="padding:4px 10px; min-width:100px; text-align:center; font-weight:700; color:#1b5e20;">' + row.ready_dispatch + '</td>' +
                                '<td style="padding:4px 10px; text-align:right;">' +
                                    '<input type="number" name="qty_for_invoice_' + idx + '" class="vIntegerField qty-for-invoice-input" data-batch-number="' + key + '" min="0" value="' + existingVal + '" style="width:80px; text-align:right;" />' +
                                '</td>' +
                                '<td style="padding:4px 10px; text-align:center; font-weight:600;">' + row.price_per_unit + '</td>' +
                                '<td style="padding:4px 10px; text-align:center;">' + (row.approved ? 'Yes' : 'No') + '</td>' +
                                '</tr>';
                        });

                        $target.html(
                            '<table style="width:100%;border-collapse:collapse;" border="1">' +
                                '<thead><tr style="background:#f0f0f0;">' +
                                    '<th style="padding:4px 10px;">Batch </th>' +
                                    '<th style="padding:4px 10px; min-width:260px; max-width:360px;">Product</th>' +
                                    '<th style="padding:4px 10px; min-width:50px;">Size</th>' +
                                    '<th style="padding:4px 10px;">Units</th>' +
                                    '<th style="padding:4px 10px;">Status</th>' +
                                    '<th style="padding:4px 10px; min-width:100px;">Ready for Billing</th>' +
                                    '<th style="padding:4px 10px;">Qty for Invoice</th>' +
                                    '<th style="padding:4px 10px;">Price/Unit</th>' +
                                    '<th style="padding:4px 10px;">Approved</th>' +
                                '</tr></thead>' +
                                '<tbody>' + rows + '</tbody>' +
                            '</table>'
                        );

                        $target.find('input.qty-for-invoice-input').on('input change keyup', function() {
                            serializeQtyInputs();
                        });
                    } else {
                        $target.html('No batch pricing rows.');
                        if ($qtyHidden.length) $qtyHidden.val('{}');
                    }
                });
        }

        var initialBatchIds = $batchField.val();
        if (initialBatchIds && initialBatchIds.length > 0 && $target.find('table').length === 0) {
            loadBatchPricing();
        }

        // Listen to direct batch_costings changes
		$batchField.on('change', function() {
			loadBatchPricing();
		});

		// ✨ LISTEN TO CUSTOM EVENT from calendar section
		$(document).on('batchCostingsUpdated', function() {

			loadBatchPricing();
		});

        var isAddPage = window.location.pathname.indexOf('/add/') !== -1;
        if (isAddPage) {
            var pollCount = 0;
            var pollingInterval = setInterval(function() {
                pollCount++;
                var currentIds = $batchField.val();
                
                if (currentIds && currentIds.length > 0 && $target.find('table').length === 0) {
                    loadBatchPricing();
                    clearInterval(pollingInterval);
                }
                
                if (pollCount >= 20) {
                    clearInterval(pollingInterval);
                }
            }, 500);
        }
        
        $('form').on('submit', function(e) {
            var finalData = {};
            var seenKeys = {};
            var inputsFound = $target.find('input.qty-for-invoice-input');
            
            inputsFound.each(function() {
                var $input = $(this);
                var key = $input.data('batch-number');
                var val = $input.val();
                
                if (key && val && !seenKeys[key]) {
                    finalData[key] = val;
                    seenKeys[key] = true;
                }
            });
            
            $qtyHidden.val(JSON.stringify(finalData));
        });
        
    });
})(grp.jQuery);

// ✨ MINIMAL calendar integration - just updates batch_costings field
(function($) {
    $(function() {
        var $input = $('#id_production_dates');
        if (!$input.length) return;

        var isAddPage = /\/add\/?$/.test(window.location.pathname);
        if (isAddPage) {
            $input.val('');
        }

        var dates = [];

        function fromInput() {
            var raw = $input.val();
            dates = raw ? raw.split(',').map(function(d) { return d.trim(); }).filter(Boolean) : [];
        }

        var $list;

        function syncInputAndList() {

			$input.val(dates.join(', '));
			
			if (!$list) {

				return;
			}
			
			$list.empty();
			dates.forEach(function(d) {
				var $li = $('<li style="margin-bottom:2px;"></li>');
				$li.text(d + ' ');
				var $remove = $('<a href="#" data-date="' + d + '" style="margin-left:6px; color:#c00;">✕</a>');
				$li.append($remove);
				$list.append($li);
			});
			
			// ✨ Update batch_costings field from dates
			var datesValue = $input.val();

			if (datesValue && datesValue.trim()) {
				
				// Get the current site ID from the Django template context
				var siteId = null;
				var siteIdElem = document.querySelector('[data-current-site-id]');
				if (siteIdElem) {
					siteId = siteIdElem.getAttribute('data-current-site-id');
				}
				
				// Build API parameters with site filtering
				var apiParams = {dates: datesValue};
				if (siteId) {
					apiParams.site_id = siteId;
				}

				$.get('/costing/api/dates-to-batch-costings/', apiParams)
					.done(function(response) {

						var ids = response.batch_costing_ids || [];

						var $batchField = $('#id_batch_costings');

						$batchField.val(ids);
						
						// ✨ DIRECTLY CALL loadBatchPricing from the main section

						$(document).trigger('batchCostingsUpdated');
					})
					.fail(function(xhr, status, error) {

					});
			} else {

				$('#id_batch_costings').val([]);
				$(document).trigger('batchCostingsUpdated');
			}

		}



        fromInput();

        if (typeof $input.datepicker === 'function') {
            $input.datepicker({
                dateFormat: 'dd/mm/yy',
                changeMonth: true,
                changeYear: true,
                showButtonPanel: true,
                yearRange: '-10:+10',
                onSelect: function(dateText) {
                    if (dates.indexOf(dateText) === -1) {
                        dates.push(dateText);
                        dates.sort();
                        syncInputAndList();
                    }
                }
            });
        }

        var $container = $('<div class="multi-date-container"></div>');
        $input.after($container);
        $container.append($input);

        $list = $('<ul class="multi-date-list" style="margin-top:5px; padding-left:18px;"></ul>');
        $container.append($list);

        var $addBtn = $('<button type="button" class="grp-button">Add date</button>');
        $container.append($addBtn);

        syncInputAndList();

        $list.on('click', 'a[data-date]', function(e) {
            e.preventDefault();
            var d = $(this).data('date');
            dates = dates.filter(function(x) { return x !== d; });
            syncInputAndList();
        });

        $addBtn.on('click', function(e) {
            e.preventDefault();
            if (typeof $input.datepicker === 'function') {
                $input.datepicker('show');
            } else {
                $input.focus();
            }
        });
    });
})(grp.jQuery);

// HIDE BATCH COSTINGS FIELDSET
(function($) {
    $(function() {
        $('#id_batch_costings').closest('fieldset').hide();
    });
})(grp.jQuery);