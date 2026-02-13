document.addEventListener('DOMContentLoaded', function() {
    const bodyClass = document.body.className || "";

    const label = document.querySelector('label[for="id_category"]');
    const select = document.getElementById('id_category');

    if (!label || !select) {
        return;
    }

    // Default to Policy, switch to Sops if we detect it
    let baseAdminUrl = '/admin/compliance/policycategory/';
    
    if (bodyClass.includes('sopscompliancedocument')) {

        baseAdminUrl = '/admin/compliance/sopscategory/';
    } else {

    }

    const icon = document.createElement('a');
    icon.href = baseAdminUrl;
    // REMOVED: icon.target = '_blank';
    icon.title = 'Edit selected category';
    icon.style.cssText =
        'background:#417690;color:#fff;padding:4px 8px;border-radius:3px;' +
        'text-decoration:none;display:inline-block;font-size:14px;' +
        'margin-left:5px;vertical-align:middle;cursor:pointer;';
    icon.innerHTML = '✏️';

    function updateHref() {
        const value = select.value;
        icon.href = value ? `${baseAdminUrl}${value}/change/` : baseAdminUrl;
    }

    updateHref();
    select.addEventListener('change', updateHref);
    label.appendChild(icon);

});
