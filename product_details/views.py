from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import Product, ProductComponent, MainProductComponent

@require_http_methods(["GET"])
@login_required
def product_components_json(request, product_id):
    """Return product components (both types) as JSON for list display"""
    try:
        product = Product.objects.get(pk=product_id)
        
        # Fetch Main Stock Items (ProductComponent - no sub-items)
        main_stock_items = product.components.filter(
            main_stock_item__isnull=True
        ).select_related(
            'category', 'sub_category', 'stock_item', 'unit_of_measure'
        )
        
        # Fetch Main Product Components
        main_product_components = product.main_product_components.all().select_related(
            'category', 'sub_category', 'stock_item', 'unit_of_measure'
        )
        
        data = {
            'product_id': product.id,
            'product_name': product.product_name,
            'components': []
        }
        
        # Add Main Stock Items
        for comp in main_stock_items:
            data['components'].append({
                'category': comp.category.name if comp.category else '-',
                'sub_category': comp.sub_category.name if comp.sub_category else '-',
                'stock_item': str(comp.stock_item) if comp.stock_item else '-',
                'usage': str(comp.standard_usage_per_production_unit) if comp.standard_usage_per_production_unit else '-',
                'unit': comp.unit_of_measure.abbreviation if comp.unit_of_measure and comp.unit_of_measure.abbreviation else (comp.unit_of_measure.name if comp.unit_of_measure else '-')
            })
        
        # Add Main Product Components
        for mpc in main_product_components:
            data['components'].append({
                'category': mpc.category.name if mpc.category else '-',
                'sub_category': mpc.sub_category.name if mpc.sub_category else '-',
                'stock_item': str(mpc.stock_item) if mpc.stock_item else '-',
                'usage': str(mpc.standard_usage_per_production_unit) if mpc.standard_usage_per_production_unit else '-',
                'unit': mpc.unit_of_measure.abbreviation if mpc.unit_of_measure and mpc.unit_of_measure.abbreviation else (mpc.unit_of_measure.name if mpc.unit_of_measure else '-')
            })
        
        return JsonResponse(data)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)