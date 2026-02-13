document.addEventListener('DOMContentLoaded', function() {
    // Find all recipe category dropdowns in inline forms
    const selects = document.querySelectorAll('select[name*="recipe_category"]');
    
    selects.forEach(function(select) {
        const row = select.closest('tr');
        if (!row) return;
        
        // Create icon link
        const link = document.createElement('a');
        link.innerHTML = '✏️';
        link.style.marginLeft = '8px';
        link.style.color = '#417690';
        link.style.textDecoration = 'none';
        link.style.fontSize = '16px';
        link.style.cursor = 'pointer';
        link.target = '_self';  // CHANGED: Opens in same window
        link.title = 'Manage Recipe Categories';
        
        // Link always goes to the Recipe Categories LIST page
        link.href = '/admin/product_details/recipecategory/';
        link.style.display = 'inline-block';
        
        select.parentNode.insertBefore(link, select.nextSibling);
    });
});
