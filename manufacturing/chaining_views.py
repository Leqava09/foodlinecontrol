"""
Custom chaining views for smart-selects that filter by site.
Overrides the default smart-selects chaining endpoint to add site filtering.
"""

from smart_selects.views import FilteredSelectMultipleView, ChainedSelectChoicesView
from django.http import JsonResponse, HttpResponse
from django.views.generic import View
from product_details.models import Product, ProductCategory
from tenants.models import Site
import json


class SiteAwareChainedSelectView(ChainedSelectChoicesView):
    """
    Custom chaining view that filters by site context.
    Override to add site filtering when fetching chained select options.
    """
    
    def get_queryset(self):
        """Get queryset and filter by current site"""
        queryset = super().get_queryset()
        
        # Get site from request
        site = getattr(self.request, 'current_site', None)
        
        if site:
            # Filter queryset by site
            queryset = queryset.filter(site=site)
        
        return queryset


class ProductByCategoryAndSiteView(View):
    """
    Get products for a category, filtered by current site.
    This replaces the standard smart-selects chaining endpoint for Product model.
    
    URL pattern: /manufacturing/chaining/product-by-category/<int:category_id>/
    """
    
    def get(self, request, category_id):
        """Return products for category, filtered by site"""
        try:
            site = getattr(request, 'current_site', None)
            
            # Get all products for this category
            products = Product.objects.filter(category_id=category_id)
            
            # Filter by site if we have it
            if site:
                products = products.filter(site=site)
            
            # Return as JSON (like smart-selects endpoint does)
            options = []
            for product in products.order_by('product_name'):
                options.append({
                    'id': product.id,
                    'name': str(product),
                    'product_name': product.product_name,
                    'sku': product.sku,
                })
            
            return JsonResponse({'options': options})
        
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
