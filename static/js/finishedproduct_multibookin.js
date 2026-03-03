(function(djangoJQuery) {
    var $ = djangoJQuery;

    $(document).ready(function() {

        var $prodDate = $('#id_production_date');

        var $placeholder = $('#id_per_batch_placeholder');
        var $container = null;

        if ($placeholder.length) {
            var $row = $placeholder.closest('.grp-row, .form-row, tr');
            if ($row.length) {
                var existing = $('#per-batch-bookin');
                if (existing.length) {
                    $container = existing;
                } else {
                    $container = $('<div id="per-batch-bookin" style="margin-top:10px;"></div>');
                    // Put it AFTER the whole row so it is clearly visible
                    $row.after($container);
                }
            }
        }



        if (!$prodDate.length || !$container || !$container.length) {
            return;
        }

        var batchesUrl = '/inventory/api/batches-for-date/';
        var readyUrl   = '/inventory/admin-api/batch-ready/';

        function renderTable(batches) {

            if (!batches || !batches.length) {
                $container.html('<p>No batches for this date.</p>');
                return;
            }

            var html = '<table class="list-table">' +
					   '<thead><tr>' +
					   '<th style="padding-left: 15px;">Batch</th>' +      // align with td
					   '<th>Product</th>' +
					   '<th>Size</th>' +
					   '<th>Shift Qty</th>' +
					   '<th>Ready to Dispatch</th>' +
					   '<th>Warehouse</th>' +
					   '</tr></thead><tbody>';

            batches.forEach(function(b) {
                var bn    = b.batch_number;
                var shift = b.shift_total || 0;
                var pname = b.product_name || '';   // expects API to send product_name
                var size  = b.size || '';           // expects API to send size

                html += '<tr>' +
					'<td style="padding-left: 15px; padding-right: 10px;">' +   // more left space
						'<input type="hidden" name="multi_batch_' + bn + '" value="' + bn + '">' +
						bn +
					'</td>' +
					'<td style="padding-right: 25px;">' + pname + '</td>' +
					'<td style="padding-right: 25px;">' + size  + '</td>' +  // more space
					'<td>' +
						'<input type="number" ' +
						'name="multi_qty_' + bn + '" ' +
						'value="' + shift + '" step="0.01" readonly ' +
						'style="background:#f5f5f5;">' +
					'</td>' +
                        '<td>' +
                            '<input type="number" ' +
                            'name="multi_ready_' + bn + '" ' +
                            'id="id_multi_ready_' + bn + '" ' +
                            'readonly style="background:#e8f5e8;font-weight:bold;color:#006400;">' +
                        '</td>' +
                        '<td>' +
                            buildWarehouseSelectHtml('multi_wh_' + bn) +
                        '</td>' +
                        '</tr>';
            });

            html += '</tbody></table>';
            $container.html(html);

            batches.forEach(function(b) {
                loadReadyForBatch(b.batch_number);
            });
        }

        function buildWarehouseSelectHtml(name) {
            var $globalWh = $('#id_to_warehouse');
            if (!$globalWh.length) {
                return '<select name="' + name + '"></select>';
            }
            var html = '<select name="' + name + '">';
            $globalWh.find('option').each(function() {
                var val  = $(this).attr('value') || '';
                var text = $(this).text();
                html += '<option value="' + val + '">' + text + '</option>';
            });
            html += '</select>';
            return html;
        }

        function loadReadyForBatch(batchNumber) {
            $.ajax({
                url: readyUrl + '?batch_id=' + encodeURIComponent(batchNumber),
                type: 'GET',
                dataType: 'json',
                success: function(data) {
                    var ready = data && typeof data.ready !== 'undefined'
                        ? data.ready
                        : 0;
                    $('#id_multi_ready_' + batchNumber).val(ready);
                },
                error: function(xhr, status, error) {

                    $('#id_multi_ready_' + batchNumber).val('');
                }
            });
        }

        function loadBatchesForDate() {
            var dateVal = $prodDate.val();

            if (!dateVal) {
                $container.html('');
                return;
            }

            // Convert date from DD-MM-YYYY or DD.MM.YYYY to YYYY-MM-DD format
            var formattedDate = dateVal;
            if (dateVal.includes('-') || dateVal.includes('.')) {
                var separator = dateVal.includes('-') ? '-' : '.';
                var parts = dateVal.split(separator);
                if (parts.length === 3 && parts[0].length === 2) {
                    // DD-MM-YYYY or DD.MM.YYYY format
                    formattedDate = parts[2] + '-' + parts[1] + '-' + parts[0]; // YYYY-MM-DD
                } else if (parts.length === 3 && parts[0].length === 4) {
                    // Already YYYY-MM-DD format
                    formattedDate = dateVal;
                }
            }

            console.log('Loading batches for date:', formattedDate);

            $.ajax({
                url: batchesUrl + '?production_date=' + encodeURIComponent(formattedDate),
                type: 'GET',
                dataType: 'json',
                success: function(data) {
                    console.log('Batches response:', data);
                    // The new API returns {batches: [...]}
                    var batches = data.batches || [];
                    renderTable(batches);
                },
                error: function(xhr, status, error) {
                    console.error('Error loading batches:', error);
                    $container.html('<p>Error loading batches.</p>');
                }
            });
        }

        $prodDate.on('change', loadBatchesForDate);

        if ($prodDate.val()) {
            loadBatchesForDate();
        }
    });
})(django.jQuery);
