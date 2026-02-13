// static/js/category_icon.js
document.addEventListener('DOMContentLoaded', function() {
    // Find category label and add icon
    const categoryLabel = document.querySelector('label[for="id_category"]');
    if (categoryLabel) {
        const icon = document.createElement('a');
        icon.href = '/admin/product_details/productcategory/';
        icon.target = '_blank';
        icon.title = 'Manage Categories';
        icon.style.cssText = 'background:#417690;color:#fff;padding:4px 8px;border-radius:3px;text-decoration:none;display:inline-block;font-size:14px;margin-left:5px;vertical-align:middle;';
        icon.innerHTML = '📁';
        categoryLabel.appendChild(icon);
    }
});
