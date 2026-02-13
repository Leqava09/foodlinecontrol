document.addEventListener('DOMContentLoaded', function() {
    // Find all product category dropdowns in the main form
    const selects = document.querySelectorAll('select[name="category"]');
    
    selects.forEach(function(select) {
        // Create icon link
        const link = document.createElement('a');
        link.innerHTML = '✏️';
        link.style.marginLeft = '8px';
        link.style.color = '#417690';
        link.style.textDecoration = 'none';
        link.style.fontSize = '16px';
        link.style.cursor = 'pointer';
        link.target = '_self';  // Opens in same window
        link.title = 'Manage Product Categories';
        
        // Link goes to the Product Categories LIST page
        link.href = '/admin/product_details/productcategory/';
        link.style.display = 'inline-block';
        
        select.parentNode.insertBefore(link, select.nextSibling);
    });
});
