// static/js/stockitem_icons.js
document.addEventListener('DOMContentLoaded', function() {
    // Find category label and add icon
    const categoryLabel = document.querySelector('label[for="id_category"]');
    if (categoryLabel) {
        const icon = document.createElement('a');
        icon.href = '/admin/inventory/stockcategory/';
        icon.title = 'Manage Categories';
        icon.style.cssText = 'background:#417690;color:#fff;padding:4px 8px;border-radius:3px;text-decoration:none;display:inline-block;font-size:14px;margin-left:5px;vertical-align:middle;';
        icon.innerHTML = '📁';
        categoryLabel.appendChild(icon);
    }

    // Find sub_category label and add icon
    const subCategoryLabel = document.querySelector('label[for="id_sub_category"]');
    if (subCategoryLabel) {
        const icon = document.createElement('a');
        icon.href = '/admin/inventory/stockcategory/';
        icon.title = 'Manage Sub Categories';
        icon.style.cssText = 'background:#f39c12;color:#fff;padding:4px 8px;border-radius:3px;text-decoration:none;display:inline-block;font-size:14px;margin-left:5px;vertical-align:middle;';
        icon.innerHTML = '🏷️';
        subCategoryLabel.appendChild(icon);
    }

    // Find unit label and add icon
    const unitLabel = document.querySelector('label[for="id_unit_of_measure"]');
    if (unitLabel) {
        const icon = document.createElement('a');
        icon.href = '/admin/inventory/unitofmeasure/';
        icon.title = 'Manage Units';
        icon.style.cssText = 'background:#5b9bd5;color:#fff;padding:4px 8px;border-radius:3px;text-decoration:none;display:inline-block;font-size:14px;margin-left:5px;vertical-align:middle;';
        icon.innerHTML = '⚖️';
        unitLabel.appendChild(icon);
    }
});
