// static/js/admin_enter_fix.js
(function($) {
    $(document).ready(function () {
        var $form = $('form');  // main admin form

        if (!$form.length) {
            return;
        }

        // 1) When Enter is pressed in an input/select, trigger "Save and continue"
        $form.on('keydown', 'input, select', function (e) {
            if (e.key === 'Enter' && this.tagName !== 'TEXTAREA') {
                e.preventDefault();
                e.stopPropagation();

                // Prefer explicit "Save and continue" button if present
                var $btn = $(
                    '.grp-button.grp-save-and-continue, ' +          // Grappelli button
                    'input[name="_continue"], ' +                    // Default admin button
                    'input[type="submit"][value*="continue"]'        // Fallback
                ).first();

                if ($btn.length) {
                    $btn.trigger('click');
                } else {
                    // Fallback: add _continue and submit
                    if ($form.find('input[name="_continue"]').length === 0) {
                        $('<input/>', {
                            type: 'hidden',
                            name: '_continue',
                            value: '1'
                        }).appendTo($form);
                    }
                    $form.trigger('submit');
                }
                return false;
            }
        });
    });
})(grp.jQuery || django.jQuery);
