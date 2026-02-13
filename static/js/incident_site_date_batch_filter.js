// Override AJAX to intercept smart-selects batch filtering and add site filtering
(function() {
    var checkJQuery = setInterval(function() {
        if (typeof django !== 'undefined' && typeof django.jQuery !== 'undefined') {
            clearInterval(checkJQuery);
            
            var $ = django.jQuery;
            var originalAjax = $.ajax;
            
            $.ajax = function(settings) {
                var url = settings.url || '';
                
                // Intercept smart-selects batch filtering for incidents
                if (url.indexOf('/chaining/filter/manufacturing/Batch') !== -1 && 
                    url.indexOf('incident_management/Incident/batch') !== -1) {
                    
                    // Extract date from URL
                    var isoDate;
                    var ddmmyyyyMatch = url.match(/\/(\d{2})-(\d{2})-(\d{4})\//);
                    var yyyymmddMatch = url.match(/\/(\d{4})-(\d{2})-(\d{2})\//);
                    
                    if (ddmmyyyyMatch) {
                        // Convert DD-MM-YYYY to YYYY-MM-DD
                        isoDate = ddmmyyyyMatch[3] + '-' + ddmmyyyyMatch[2] + '-' + ddmmyyyyMatch[1];
                    } else if (yyyymmddMatch) {
                        // Already in ISO format
                        isoDate = yyyymmddMatch[1] + '-' + yyyymmddMatch[2] + '-' + yyyymmddMatch[3];
                    }
                    
                    if (isoDate) {
                        // Get site selection from form
                        var siteField = $('#id_site');
                        var siteId = siteField.length ? siteField.val() : '';
                        
                        // Get admin URL path
                        var path = window.location.pathname || '';
                        var adminIndex = path.indexOf('/admin/');
                        var baseUrl = '/admin/incident_management/incident/batch-options/';
                        if (adminIndex !== -1) {
                            baseUrl = path.substring(0, adminIndex + 7) + 'incident_management/incident/batch-options/';
                        }
                        
                        // Build new URL with site filtering
                        var newUrl = baseUrl + '?production_date=' + isoDate;
                        if (siteId) {
                            newUrl += '&site_id=' + siteId;
                        }
                        
                        settings.url = newUrl;
                    }
                }
                
                return originalAjax.call(this, settings);
            };
        }
    }, 10);
})();
