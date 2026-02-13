(function() {
    var $ = (typeof django !== 'undefined') ? django.jQuery : jQuery;

    function addViewLink($select, urlPrefix, label) {
        if (!$select.length) return;

        var $btn = $('<a>', {
            href: '#',
            html: '<i class="fa fa-eye"></i>',
            style: 'margin-left:4px;'
        });;

        $btn.on('click', function(e) {
            e.preventDefault();
            var id = $select.val();
            if (id) {
                var url = urlPrefix + id + '/change/';
                window.location.href = url;      // same window instead of _blank
            }
        });

        $select.after($btn);
    }

    $(function() {
        // adjust app/model names if different
        $('select[id$="linked_policy"]').each(function() {
            addViewLink($(this), '/admin/compliance/policycompliancedocument/', '[View]');
        });
        $('select[id$="linked_sop"]').each(function() {
            addViewLink($(this), '/admin/compliance/sopscompliancedocument/', '[View]');
        });
    });
})();
