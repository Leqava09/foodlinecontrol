from datetime import datetime
from decimal import Decimal
from django.http import JsonResponse, Http404
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum
from django.urls import reverse
import json
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponse
from django.template.loader import render_to_string
from .models import BatchCosting, BatchPriceApproval, BillingDocumentHeader
from transport.models import DeliverySite 
from commercial.models import CompanyDetails
from manufacturing.models import Batch, BatchContainer, Waste
from inventory.models import RecipeStockItemBalance, PackagingBalance, StockTransaction, Container
from product_details.models import ProductComponent, ProductRecipeItem
from docxtpl import DocxTemplate
import io
import tempfile
import os
from subprocess import run, PIPE
import urllib.parse
from django.views.decorators.http import require_GET

def calculate_weighted_ideal_costing(items_group):
    """
    Calculate IDEAL COSTING using weighted average of batch prices
    - Single batch: ideal × price
    - Multiple batches: weighted by percentage used
    """
    if not items_group or len(items_group) == 0:
        return 0.0
    
    # Single batch - simple calculation
    if len(items_group) == 1:
        ideal = float(items_group[0].get('ideal', 0))
        price = float(items_group[0].get('price_per_unit', 0))
        return ideal * price
    
    # Multiple batches - weighted average
    total_used = sum(float(item.get('used', 0)) for item in items_group)
    
    if total_used == 0:
        ideal = float(items_group[0].get('ideal', 0))
        price = float(items_group[0].get('price_per_unit', 0))
        return ideal * price
    
    ideal_costing = 0.0
    ideal_qty = float(items_group[0].get('ideal', 0))
    
    for item in items_group:
        used = float(item.get('used', 0))
        price = float(item.get('price_per_unit', 0))
        
        percentage = (used / total_used) * 100 if total_used > 0 else 0
        ideal_share = (ideal_qty / 100) * percentage
        batch_costing = ideal_share * price
        ideal_costing += batch_costing
    
    return ideal_costing

def determine_is_local(batch_ref):
    """
    Determine if batch_ref is from local StockTransaction or import Container
    - If found in Container (container_number) → is_local = False (IMPORT)
    - If found in StockTransaction → is_local = True (LOCAL)
    """
    if not batch_ref or batch_ref == '-':
        return True
    
    try:
        # First check if it's an import container
        container = Container.objects.filter(
            container_number=batch_ref
        ).first()
        if container:
            return False  # Import container
    except Exception:
        pass
    
    # Otherwise assume local (StockTransaction)
    return True  # Local

def get_price_per_unit(batch_ref, is_local, stock_item=None):
    """
    Get price_per_unit
    - is_local=True → Query StockTransaction by batch_ref, get (invoice + transport) / quantity
    - is_local=False → Use Container.total_cost_nad / total_weight_container
    """
    try:
        if is_local:
            # LOCAL MEAT: Query StockTransaction directly
            stock_tx = StockTransaction.objects.filter(
                batch_ref=str(batch_ref),
                transaction_type='IN'
            ).first()
            
            if stock_tx:
                invoice = float(stock_tx.total_invoice_amount_excl or 0)
                transport = float(stock_tx.transport_cost or 0)
                qty = float(stock_tx.quantity or 1)
                
                total_cost = invoice + transport
                price = total_cost / qty if qty > 0 else 0
                return price
            else:
                # Fallback: Try standard_cost_incl_transport
                if stock_item:
                    cost = float(stock_item.standard_cost_incl_transport or 0)
                    return cost
                    
        else:
            # IMPORT: Container
            container = Container.objects.filter(
                container_number=batch_ref
            ).first()
            
            if container:
                total_cost = float(container.total_cost_nad or 0)
                total_weight = float(container.total_weight_container or 0)
                
                if total_weight > 0:
                    price = total_cost / total_weight
                    return price
                
    except Exception:
        pass
    
    return 0.00

def get_quoted_calculation(product, stock_item, ideal_qty):
    """
    Calculate quoted price from ProductCosting
    """
    from costing.models import ProductCosting, ProductCostingStockItem
    from product_details.models import ProductComponent, ProductRecipeItem
    
    try:
        costing = ProductCosting.objects.filter(product=product).first()
        if not costing:
            return 0.0
        
        costing_item = ProductCostingStockItem.objects.filter(
            product_costing=costing,
            stock_item=stock_item
        ).first()
        
        if not costing_item:
            return 0.0
        
        use_price = float(costing_item.use_price_per_unit or 0)
        waste_pct = float(costing_item.waste_percentage or 0)
        
        usage_per_unit = 1
        component = ProductComponent.objects.filter(
            product=product,
            stock_item=stock_item
        ).first()
        if component:
            usage_per_unit = float(component.standard_usage_per_production_unit or 1)
        else:
            recipe_item = ProductRecipeItem.objects.filter(
                recipe__product=product,
                stock_item=stock_item
            ).first()
            if recipe_item:
                usage_per_unit = float(recipe_item.standard_usage_per_production_unit or 1)
        
        ideal = float(ideal_qty or 0)
        adjusted_cost = (use_price / usage_per_unit) * (1 + waste_pct / 100) * 1.15
        quoted = ideal * adjusted_cost
        
        return quoted
            
    except Exception:
        return 0.0

@staff_member_required
@require_http_methods(["GET"])
@csrf_exempt
def batch_summary_items_api(request, production_date_str):
    """
    DYNAMIC BATCH REF LOGIC - WITH DYNAMIC is_local DETERMINATION
    ideal_costing = price_per_unit × ideal
    used_costing = price_per_unit × used
    
    Accepts either:
    - A date string in format 'YYYY-MM-DD'
    - A Production ID (will extract the date from it)
    """
    # ✅ Get site context from session (set by SiteMiddleware)
    current_site_id = request.session.get('current_site_id')
    current_site = None
    if current_site_id:
        from tenants.models import Site
        try:
            current_site = Site.objects.get(pk=current_site_id)
        except Site.DoesNotExist:
            pass
    
    prod_date = None
    
    # Try to parse as date first
    try:
        prod_date = datetime.strptime(production_date_str, '%Y-%m-%d').date()
    except ValueError:
        # Try to parse as Production ID
        try:
            production_id = int(production_date_str)
            from manufacturing.models import Production
            # ✅ Filter Production by site
            production_qs = Production.objects
            if current_site:
                production_qs = production_qs.filter(site=current_site)
            production = production_qs.filter(pk=production_id).first()
            if production:
                prod_date = production.production_date
            else:
                return JsonResponse({'error': 'Production not found'}, status=404)
        except (ValueError, Exception) as e:
            return JsonResponse({'error': f'Invalid date format or production ID: {str(e)}'}, status=400)
    
    if not prod_date:
        return JsonResponse({'error': 'Could not determine production date'}, status=400)
    
    # ✅ Filter Batch by production_date AND site
    batch_qs = Batch.objects.filter(production_date=prod_date)
    if current_site:
        batch_qs = batch_qs.filter(site=current_site)
    batch = batch_qs.first()
    
    if not batch or not batch.product:
        return JsonResponse({'items': [], 'count': 0}, safe=False)
    
    # ✅ Filter total_pouches by site
    batch_filter_qs = Batch.objects.filter(production_date=prod_date)
    if current_site:
        batch_filter_qs = batch_filter_qs.filter(site=current_site)
    total_pouches = Decimal(str(
        batch_filter_qs.aggregate(
            total=Sum('shift_total')
        )['total'] or 0
    ))
    
    items = []
    
    # ==================== MEAT SECTION ====================
    # ✅ Filter BatchContainer by site (through container relationship)
    batch_containers = BatchContainer.objects.filter(
        production_date=prod_date
    ).select_related('container', 'container__stock_item')
    if current_site:
        batch_containers = batch_containers.filter(container__site=current_site)
    batch_containers = batch_containers.order_by('pk')
    

    for bc in batch_containers:
        if bc.container:
            stock_item = bc.container.stock_item
        else:
            main_components = batch.product.main_product_components.all()
            if main_components.exists():
                stock_item = main_components.first().stock_item
            else:
                continue

        if not stock_item:
            continue

        item_name = str(stock_item)
        unit = str(stock_item.unit_of_measure.abbreviation) if stock_item.unit_of_measure else 'Unit'
        used_qty = float(bc.kg_frozen_meat_used or 0)

        if bc.source_type == 'local':
            batch_ref = str(bc.batch_ref or '')
        else:
            batch_ref = str(bc.container.container_number or '')

        # Dynamically determine if local or import
        is_local = determine_is_local(batch_ref)

        ideals_cache = {}
        for mc in batch.product.main_product_components.all():
            stock_item_name = str(mc.stock_item)
            std_usage = Decimal(str(mc.standard_usage_per_production_unit or 0))
            ideal = float(total_pouches * std_usage)
            ideals_cache[stock_item_name] = ideal

        ideal = ideals_cache.get(item_name, 0)
        
        # Get price_per_unit for this batch_ref
        price_per_unit = get_price_per_unit(batch_ref, is_local, stock_item)
        ideal_costing = ideal * price_per_unit
        used_costing = used_qty * price_per_unit
        quoted = get_quoted_calculation(batch.product, stock_item, ideal)

        items.append({
            'section': 'meat',
            'item_name': item_name,
            'unit': unit,
            'ideal': ideal,
            'used': used_qty,
            'batch_ref': batch_ref,
            'ideal_costing': ideal_costing,
            'used_costing': used_costing,
            'price_per_unit': price_per_unit,
            'quoted': quoted,
            'type': 'main_component',
        })
    
    # ==================== SAUCE SECTION ====================
    # ✅ Filter RecipeStockItemBalance by site (through stock_item relationship)
    sauce_items = RecipeStockItemBalance.objects.filter(
        production_date=prod_date
    ).select_related('stock_item')
    if current_site:
        sauce_items = sauce_items.filter(stock_item__site=current_site)


    for sauce_item in sauce_items:
        stock_item = sauce_item.stock_item
        item_name = str(stock_item)
        unit = str(stock_item.unit_of_measure.abbreviation) if stock_item.unit_of_measure else 'L'
            
        recipe_item = ProductRecipeItem.objects.filter(
            recipe__product=batch.product,
            stock_item=stock_item
        ).first()
        
        std_usage = Decimal(str(recipe_item.standard_usage_per_production_unit or 0)) if recipe_item else Decimal(0)
        ideal = float(total_pouches * std_usage)
        
        opening = float(sauce_item.opening_balance or 0)
        booked = float(sauce_item.booked_out_stock or 0)
        closing = float(sauce_item.closing_balance or 0)
        cancel_opening = bool(sauce_item.cancel_opening_use_bookout)
        
        opening_batch_ref = str(sauce_item.opening_batch_ref or '')
        batch_ref = str(sauce_item.batch_ref or '')
        
        
        # If cancel_opening_use_bookout is checked, show only 1 row with booked qty
        if cancel_opening:
            used_qty = booked - closing
            # Extract ONLY the second part if "/" exists
            if "/" in batch_ref:
                parts = [ref.strip() for ref in batch_ref.split("/")]
                chosen_ref = parts[1] if len(parts) >= 2 else batch_ref
            else:
                chosen_ref = batch_ref if batch_ref else opening_batch_ref
            
            # Dynamically determine if local or import
            is_local = determine_is_local(chosen_ref)
            
            price_per_unit = get_price_per_unit(chosen_ref, is_local)
            ideal_costing = ideal * price_per_unit
            used_costing = used_qty * price_per_unit
            quoted = get_quoted_calculation(batch.product, stock_item, ideal)
            
            items.append({
                'section': 'sauce',
                'item_name': item_name,
                'unit': unit,
                'ideal': ideal,
                'used': used_qty,
                'batch_ref': chosen_ref,
                'ideal_costing': ideal_costing,
                'used_costing': used_costing,
                'price_per_unit': price_per_unit,
                'quoted': quoted,
                'type': 'recipe',
            })

        # Otherwise check for "/" or separate batch refs (normal 2-line logic)
        elif "/" in batch_ref:
            # Split mode: extract both refs from batch_ref
            parts = [ref.strip() for ref in batch_ref.split("/")]
            if len(parts) == 2:
                opening_batch_ref = parts[0]
                batch_ref = parts[1]
                used_qty_1 = opening
                used_qty_2 = booked - closing
                
                # Line 1
                is_local_1 = determine_is_local(opening_batch_ref)
                price_per_unit_1 = get_price_per_unit(opening_batch_ref, is_local_1, stock_item)
                ideal_costing_1 = ideal * price_per_unit_1
                used_costing_1 = used_qty_1 * price_per_unit_1
                quoted = get_quoted_calculation(batch.product, stock_item, ideal)
                
                items.append({
                    'section': 'sauce',
                    'item_name': item_name,
                    'unit': unit,
                    'ideal': ideal,
                    'used': used_qty_1,
                    'batch_ref': opening_batch_ref,
                    'ideal_costing': ideal_costing_1,
                    'used_costing': used_costing_1,
                    'price_per_unit': price_per_unit_1,
                    'quoted': quoted,
                    'type': 'recipe',
                })
                
                # Line 2
                is_local_2 = determine_is_local(batch_ref)
                price_per_unit_2 = get_price_per_unit(batch_ref, is_local_2, stock_item)
                ideal_costing_2 = ideal * price_per_unit_2
                used_costing_2 = used_qty_2 * price_per_unit_2
                quoted = get_quoted_calculation(batch.product, stock_item, ideal)
                
                items.append({
                    'section': 'sauce',
                    'item_name': item_name,
                    'unit': unit,
                    'ideal': ideal,
                    'used': used_qty_2,
                    'batch_ref': batch_ref,
                    'ideal_costing': ideal_costing_2,
                    'used_costing': used_costing_2,
                    'price_per_unit': price_per_unit_2,
                    'quoted': quoted,
                    'type': 'recipe',
                })
            else:
                # Fallback to single line
                used_qty = opening + booked - closing
                
                is_local = determine_is_local(batch_ref)
                price_per_unit = get_price_per_unit(batch_ref, is_local, stock_item)
                ideal_costing = ideal * price_per_unit
                used_costing = used_qty * price_per_unit
                quoted = get_quoted_calculation(batch.product, stock_item, ideal)
                
                items.append({
                    'section': 'sauce',
                    'item_name': item_name,
                    'unit': unit,
                    'ideal': ideal,
                    'used': used_qty,
                    'batch_ref': batch_ref,
                    'ideal_costing': ideal_costing,
                    'used_costing': used_costing,
                    'price_per_unit': price_per_unit,
                    'quoted': quoted,
                    'type': 'recipe',
                })
        elif opening_batch_ref and batch_ref and opening_batch_ref != batch_ref and opening_batch_ref != 'None':
            # Normal 2-line mode (from separate fields)
            used_qty_1 = opening
            used_qty_2 = booked - closing
            
            # Line 1
            is_local_1 = determine_is_local(opening_batch_ref)
            price_per_unit_1 = get_price_per_unit(opening_batch_ref, is_local_1)
            ideal_costing_1 = ideal * price_per_unit_1
            used_costing_1 = used_qty_1 * price_per_unit_1
            quoted = get_quoted_calculation(batch.product, stock_item, ideal)

            items.append({
                'section': 'sauce',
                'item_name': item_name,
                'unit': unit,
                'ideal': ideal,
                'used': used_qty_1,
                'batch_ref': opening_batch_ref,
                'ideal_costing': ideal_costing_1,
                'used_costing': used_costing_1,
                'price_per_unit': price_per_unit_1,
                'quoted': quoted,
                'type': 'recipe',
            })
            
            # Line 2
            is_local_2 = determine_is_local(batch_ref)
            price_per_unit_2 = get_price_per_unit(batch_ref, is_local_2, stock_item)
            ideal_costing_2 = ideal * price_per_unit_2
            used_costing_2 = used_qty_2 * price_per_unit_2
            quoted = get_quoted_calculation(batch.product, stock_item, ideal)
            
            items.append({
                'section': 'sauce',
                'item_name': item_name,
                'unit': unit,
                'ideal': ideal,
                'used': used_qty_2,
                'batch_ref': batch_ref,
                'ideal_costing': ideal_costing_2,
                'used_costing': used_costing_2,
                'price_per_unit': price_per_unit_2,
                'quoted': quoted,
                'type': 'recipe',
            })
        else:
            used_qty = opening + booked - closing
            chosen_ref = batch_ref or opening_batch_ref
            
            is_local = determine_is_local(chosen_ref)
            price_per_unit = get_price_per_unit(chosen_ref, is_local)
            ideal_costing = ideal * price_per_unit
            used_costing = used_qty * price_per_unit
            quoted = get_quoted_calculation(batch.product, stock_item, ideal)
            
            items.append({
                'section': 'sauce',
                'item_name': item_name,
                'unit': unit,
                'ideal': ideal,
                'used': used_qty,
                'batch_ref': chosen_ref,
                'ideal_costing': ideal_costing,
                'used_costing': used_costing,
                'price_per_unit': price_per_unit,
                'quoted': quoted,
                'type': 'recipe',
            })

    
    # ==================== PACKAGING SECTION ====================
    # ✅ Filter PackagingBalance by site (through stock_item relationship)
    packaging_items = PackagingBalance.objects.filter(
        production_date=prod_date
    ).select_related('stock_item')
    if current_site:
        packaging_items = packaging_items.filter(stock_item__site=current_site)


    for pkg_item in packaging_items:
        stock_item = pkg_item.stock_item
        item_name = str(stock_item)
        unit = str(stock_item.unit_of_measure.abbreviation) if stock_item.unit_of_measure else 'Unit'
        
        component = ProductComponent.objects.filter(
            product=batch.product,
            stock_item=stock_item
        ).first()
        
        std_usage = Decimal(str(component.standard_usage_per_production_unit or 0)) if component else Decimal(0)
        ideal = float(total_pouches * std_usage)
        
        opening = float(pkg_item.opening_balance or 0)
        booked = float(pkg_item.booked_out_stock or 0)
        closing = float(pkg_item.closing_balance or 0)
        cancel_opening = bool(pkg_item.cancel_opening_use_bookout)
        
        opening_batch_ref = str(pkg_item.opening_batch_ref or '')
        batch_ref = str(pkg_item.batch_ref or '')
        
        
        # If cancel_opening_use_bookout is checked, show only 1 row with booked qty
        if cancel_opening:
            used_qty = booked - closing
            # Extract ONLY the second part if "/" exists
            if "/" in batch_ref:
                parts = [ref.strip() for ref in batch_ref.split("/")]
                chosen_ref = parts[1] if len(parts) >= 2 else batch_ref
            else:
                chosen_ref = batch_ref if batch_ref else opening_batch_ref
            
            # Dynamically determine if local or import
            is_local = determine_is_local(chosen_ref)
            
            price_per_unit = get_price_per_unit(chosen_ref, is_local)
            ideal_costing = ideal * price_per_unit
            used_costing = used_qty * price_per_unit
            quoted = get_quoted_calculation(batch.product, stock_item, ideal)
            
            items.append({
                'section': 'packaging',
                'item_name': item_name,
                'unit': unit,
                'ideal': ideal,
                'used': used_qty,
                'batch_ref': chosen_ref,
                'ideal_costing': ideal_costing,
                'used_costing': used_costing,
                'price_per_unit': price_per_unit,
                'quoted': quoted,
                'type': 'component',
            })

        # Otherwise check for "/" or separate batch refs (normal 2-line logic)
        elif "/" in batch_ref:
            # Split mode: extract both refs from batch_ref
            parts = [ref.strip() for ref in batch_ref.split("/")]
            if len(parts) == 2:
                opening_batch_ref = parts[0]
                batch_ref = parts[1]
                used_qty_1 = opening
                used_qty_2 = booked - closing
                
                # Line 1
                is_local_1 = determine_is_local(opening_batch_ref)
                price_per_unit_1 = get_price_per_unit(opening_batch_ref, is_local_1, stock_item)
                ideal_costing_1 = ideal * price_per_unit_1
                used_costing_1 = used_qty_1 * price_per_unit_1
                quoted = get_quoted_calculation(batch.product, stock_item, ideal)
                
                items.append({
                    'section': 'packaging',
                    'item_name': item_name,
                    'unit': unit,
                    'ideal': ideal,
                    'used': used_qty_1,
                    'batch_ref': opening_batch_ref,
                    'ideal_costing': ideal_costing_1,
                    'used_costing': used_costing_1,
                    'price_per_unit': price_per_unit_1,
                    'quoted': quoted,
                    'type': 'component',
                })
                
                # Line 2
                is_local_2 = determine_is_local(batch_ref)
                price_per_unit_2 = get_price_per_unit(batch_ref, is_local_2, stock_item)
                ideal_costing_2 = ideal * price_per_unit_2
                used_costing_2 = used_qty_2 * price_per_unit_2
                quoted = get_quoted_calculation(batch.product, stock_item, ideal)
                
                items.append({
                    'section': 'packaging',
                    'item_name': item_name,
                    'unit': unit,
                    'ideal': ideal,
                    'used': used_qty_2,
                    'batch_ref': batch_ref,
                    'ideal_costing': ideal_costing_2,
                    'used_costing': used_costing_2,
                    'price_per_unit': price_per_unit_2,
                    'quoted': quoted,
                    'type': 'component',
                })
            else:
                # Fallback to single line
                used_qty = opening + booked - closing
                
                is_local = determine_is_local(batch_ref)
                price_per_unit = get_price_per_unit(batch_ref, is_local, stock_item)
                ideal_costing = ideal * price_per_unit
                used_costing = used_qty * price_per_unit
                quoted = get_quoted_calculation(batch.product, stock_item, ideal)
                
                items.append({
                    'section': 'packaging',
                    'item_name': item_name,
                    'unit': unit,
                    'ideal': ideal,
                    'used': used_qty,
                    'batch_ref': batch_ref,
                    'ideal_costing': ideal_costing,
                    'used_costing': used_costing,
                    'price_per_unit': price_per_unit,
                    'quoted': quoted,
                    'type': 'component',
                })
        elif opening_batch_ref and batch_ref and opening_batch_ref != batch_ref and opening_batch_ref != 'None':
            # Normal 2-line mode (from separate fields)
            used_qty_1 = opening
            used_qty_2 = booked - closing
            
            # Line 1
            is_local_1 = determine_is_local(opening_batch_ref)
            price_per_unit_1 = get_price_per_unit(opening_batch_ref, is_local_1)
            ideal_costing_1 = ideal * price_per_unit_1
            used_costing_1 = used_qty_1 * price_per_unit_1
            quoted = get_quoted_calculation(batch.product, stock_item, ideal)

            
            items.append({
                'section': 'packaging',
                'item_name': item_name,
                'unit': unit,
                'ideal': ideal,
                'used': used_qty_1,
                'batch_ref': opening_batch_ref,
                'ideal_costing': ideal_costing_1,
                'used_costing': used_costing_1,
                'price_per_unit': price_per_unit_1,
                'quoted': quoted,
                'type': 'component',
            })
            
            # Line 2
            is_local_2 = determine_is_local(batch_ref)
            price_per_unit_2 = get_price_per_unit(batch_ref, is_local_2, stock_item)
            ideal_costing_2 = ideal * price_per_unit_2
            used_costing_2 = used_qty_2 * price_per_unit_2
            quoted = get_quoted_calculation(batch.product, stock_item, ideal)
            
            items.append({
                'section': 'packaging',
                'item_name': item_name,
                'unit': unit,
                'ideal': ideal,
                'used': used_qty_2,
                'batch_ref': batch_ref,
                'ideal_costing': ideal_costing_2,
                'used_costing': used_costing_2,
                'price_per_unit': price_per_unit_2,
                'quoted': quoted,
                'type': 'component',
            })
        else:
            used_qty = opening + booked - closing
            chosen_ref = batch_ref or opening_batch_ref
            
            is_local = determine_is_local(chosen_ref)
            price_per_unit = get_price_per_unit(chosen_ref, is_local)
            ideal_costing = ideal * price_per_unit
            used_costing = used_qty * price_per_unit
            quoted = get_quoted_calculation(batch.product, stock_item, ideal)
            
            items.append({
                'section': 'packaging',
                'item_name': item_name,
                'unit': unit,
                'ideal': ideal,
                'used': used_qty,
                'batch_ref': chosen_ref,
                'ideal_costing': ideal_costing,
                'used_costing': used_costing,
                'price_per_unit': price_per_unit,
                'quoted': quoted,
                'type': 'component',
            })

    
    # ==================== CALCULATE WEIGHTED IDEAL COSTING ====================

    # Group items by item_name
    item_groups = {}
    for item in items:
        key = item['item_name']
        if key not in item_groups:
            item_groups[key] = []
        item_groups[key].append(item)

    # Calculate weighted ideal_costing for each group and update all items in group
    for item_name, group in item_groups.items():
        weighted_ideal_costing = calculate_weighted_ideal_costing(group)
        
        # Update ALL items in this group with the SAME weighted ideal_costing
        for item in group:
            item['ideal_costing'] = weighted_ideal_costing


    # ==================== CALCULATE TOTAL BATCH UNITS ====================
    # Use the TOTAL POUCHES from Batch.shift_total (actual production units)
    total_batch_units = float(total_pouches)  # NOT the Pouch Gravy used qty!

    # ==================== RETURN RESPONSE ====================
    
    return JsonResponse({
        'items': items,
        'count': len(items),
        'total_batch_units': total_batch_units,   
    }, safe=False)

@staff_member_required
@csrf_protect
@require_http_methods(["POST"])
def save_batch_approvals(request):
    """
    Save batch price approvals via AJAX
    Called from batch_costing_unified.js before form submission
    Preserves ALL pricing and approval data
    """
    try:
        data = json.loads(request.body)
        approvals_data = data.get('approvals', [])
        batch_costing_id = data.get('batch_costing_id')
        
        
        saved_count = 0
        failed_count = 0
        
        for approval_data in approvals_data:
            approval_id = approval_data.get('id')
            price = approval_data.get('price')
            is_approved = approval_data.get('approved', False)
            
            try:
                approval = BatchPriceApproval.objects.get(id=approval_id)
                
                # Store OLD values for logging
                old_price = approval.batch_price_per_unit
                old_approved = approval.is_approved
                
                # UPDATE with NEW values
                approval.batch_price_per_unit = price
                approval.is_approved = is_approved
                approval.save()
                
                saved_count += 1
                
            except BatchPriceApproval.DoesNotExist:
                failed_count += 1
                continue
            except Exception as e:
                failed_count += 1
                continue
        
        response_data = {
            'success': True,
            'message': f'Saved {saved_count} approvals' + (f' ({failed_count} failed)' if failed_count > 0 else ''),
            'saved_count': saved_count,
            'failed_count': failed_count,
            'total': len(approvals_data)
        }
        
        return JsonResponse(response_data)
    
    except json.JSONDecodeError as e:
        return JsonResponse({
            'success': False,
            'message': f'Invalid JSON: {str(e)}'
        }, status=400)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)

@staff_member_required
@require_POST
@csrf_protect
def update_batch_price_approval(request, pk):
    """
    AJAX endpoint to save BatchPriceApproval changes
    Called from batch_price_approval_save.js
    """
    
    try:
        approval = get_object_or_404(BatchPriceApproval, pk=pk)

        price_str = request.POST.get('batch_price_per_unit', '')
        
        if price_str:
            price_clean = price_str.replace(',', '').strip()
            try:
                approval.batch_price_per_unit = Decimal(price_clean)
            except Exception as e:
                return JsonResponse({'ok': False, 'error': f'Invalid price: {str(e)}'}, status=400)

        is_approved_str = request.POST.get('is_approved', 'false')
        approval.is_approved = is_approved_str == 'true'

        approval.save()

        # Return minimal response immediately (avoids timeout/broken pipe)
        return JsonResponse({'ok': True})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)

@staff_member_required
@require_http_methods(["GET"])
@csrf_exempt
def batch_pricing_preview_api(request, pk):
    """Now handles multiple batch_costings: 1 or 1,2,3"""
    
    # Parse comma-separated IDs
    batch_costing_ids = [int(id.strip()) for id in str(pk).split(',') if id.strip()]
    
    if not batch_costing_ids:
        raise Http404("No batch costing IDs provided")
    
    # Get ALL requested batch costings
    batch_costings = BatchCosting.objects.filter(
        pk__in=batch_costing_ids
    ).prefetch_related(
        'production_date__batches',
        'price_approvals'
    )
    
    if not batch_costings.exists():
        raise Http404("BatchCosting not found")
    

    billing_id = request.GET.get('billing_id')
    
    # Determine if this is for a specific billing or showing current state
    current_billing = None
    exclude_billing = False
    
    if billing_id:
        try:
            current_billing = BillingDocumentHeader.objects.get(pk=billing_id)
            exclude_billing = True
        except:
            pass

    # Get approvals from ALL batch costings
    approvals = BatchPriceApproval.objects.filter(
        batch_costing__in=batch_costings
    ).select_related('batch')
    

    rows = []
    for a in approvals:
        b = a.batch
        shifttotal = float(b.shift_total or 0)
        
        from inventory.models import FinishedProductTransaction
        from django.db.models import Sum
        from decimal import Decimal

        in_tx = FinishedProductTransaction.objects.filter(
            batch=b,
            transaction_type='IN'
        ).order_by('pk').first()

        if in_tx and in_tx.ready_to_dispatch:
            starting_qty = Decimal(str(in_tx.ready_to_dispatch))
            
            # Filter RELEASED dispatches
            released_filter = FinishedProductTransaction.objects.filter(
                batch=b,
                transaction_type='DISPATCH',
                status='RELEASED'
            )
            
            # Only exclude current billing's dispatches if editing
            if exclude_billing and current_billing:
                released_filter = released_filter.exclude(
                    notes__contains=f"Billing {current_billing.base_number}"
                )
            
            released_dispatched = released_filter.aggregate(
                total=Sum('quantity')
            )['total'] or Decimal('0')
            
            # Scrap - for ADD page, subtract all; for edit, exclude same-day/future
            if exclude_billing and current_billing and current_billing.billing_date:
                scrapped = FinishedProductTransaction.objects.filter(
                    batch=b,
                    transaction_type='SCRAP',
                    date__lt=current_billing.billing_date
                ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
            else:
                scrapped = FinishedProductTransaction.objects.filter(
                    batch=b,
                    transaction_type='SCRAP'
                ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
            
            available_for_billing = float(starting_qty - released_dispatched - scrapped)
        else:
            available_for_billing = 0
        
        rows.append({
            'batch_number': getattr(b, 'batch_number', ''),
            'product': str(getattr(b, 'product', '')),
            'size': getattr(b, 'size', ''),
            'units': shifttotal,
            'status': b.get_formatted_status(),
            'ready_dispatch': available_for_billing,
            'price_per_unit': f"{a.batch_price_per_unit:.2f}",
            'approved': a.is_approved,
        })


    return JsonResponse({"rows": rows})


def billing_document_preview(request, pk, doc_type):
    header = get_object_or_404(BillingDocumentHeader, pk=pk)
    # For multi-tenant isolation: ALWAYS determine company from site (ignore stored company field)
    # This ensures existing records with wrong company values still use correct templates
    if header.site:
        company = CompanyDetails.objects.filter(site=header.site, is_active=True).first()
    else:
        # HQ documents (site=NULL) use HQ company (site__isnull=True)
        company = CompanyDetails.objects.filter(site__isnull=True, is_active=True).first()

    # Check for query parameter overrides for billing method (for live preview)
    # This allows the preview to reflect unsaved form changes
    bill_per_primary = header.bill_per_primary
    bill_per_secondary = header.bill_per_secondary
    bill_per_pallet = header.bill_per_pallet
    
    if 'billing_method' in request.GET:
        billing_method = request.GET.get('billing_method', '')
        bill_per_primary = billing_method == 'primary'
        bill_per_secondary = billing_method == 'secondary'
        bill_per_pallet = billing_method == 'pallet'

    # Normalize document type
    doc_type_upper = doc_type.upper()
    doc_type_map = {
        "INVOICE": "Invoice",
        "QUOTE": "Quote",
        "PROFORMA": "Proforma",
        "PICKING": "Picking Slip",
        "DELIVERY": "Delivery Note",
    }
    document_type = doc_type_map.get(doc_type_upper, "Billing Document")
    
    # Document number prefix for the document number field
    doc_prefix_map = {
        "INVOICE": "INV",
        "QUOTE": "QUO",
        "PROFORMA": "PRO",
        "PICKING": "PS",
        "DELIVERY": "DN",
    }
    document_prefix = doc_prefix_map.get(doc_type_upper, "")

    # Get exchange rate upfront
    rate = header.exchange_rate or Decimal("1")

    # Helper: normalize qty_for_invoice_data to flat {batch_number: qty} dict
    def get_qty_mapping(qty_data):
        """Extract flat batch_number->qty mapping from qty_for_invoice_data.
        Handles both formats:
          - Flat: {'A00825CH02A': '1000', ...}
          - Nested: {'qty_mapping': {'A00825CH02A': '1000', ...}, 'batch_data': [...], ...}
        """
        if not qty_data:
            return {}
        if isinstance(qty_data, dict) and 'qty_mapping' in qty_data:
            return qty_data['qty_mapping']
        # Assume flat format - but verify keys look like batch numbers (not nested keys)
        if isinstance(qty_data, dict):
            # If any value is a dict/list, it's nested format without qty_mapping
            if any(isinstance(v, (dict, list)) for v in qty_data.values()):
                return {}
            return qty_data
        return {}

    # Prepare table rows
    table_rows = []
    total_amount = Decimal("0.00")  # Accumulator in from-currency

    # ============ CHECK FOR HQ LINE ITEMS FIRST ============
    print(f"\n=== BILLING DATA DEBUG ===")
    print(f"Header ID: {header.pk}")
    print(f"Header Site: {header.site.name if header.site else 'HQ'}")
    print(f"Line Items Count: {header.line_items.count()}")
    print(f"Batch Costings Count: {header.batch_costings.count()}")
    
    if header.line_items.exists():
        # HQ BILLING: Use line_items (direct batch selection)
        print(f"Using HQ line_items for billing document")
        line_items = header.line_items.select_related('batch', 'batch__product', 'site')
        print(f"Line Items: {[li.pk for li in line_items]}")
        
        for line_item in line_items:
            batch = line_item.batch
            product = batch.product if batch else None
            
            # Get product details
            product_name = product.product_name if product else ""
            product_sku = product.sku if product and hasattr(product, 'sku') else ""
            
            # Get selling price and qty from line_item
            qty = line_item.qty_for_invoice or Decimal("0.00")
            price_per_unit = line_item.selling_price or Decimal("0.00")
            
            # Get packaging info dynamically (same as site billing)
            from product_details.models import ProductComponent
            packaging_info = ProductComponent.get_packaging_info(product) if product else {}
            
            # Determine display values based on billing method
            display_qty = qty
            display_price = price_per_unit
            
            if bill_per_primary:
                if packaging_info.get('primary'):
                    product_name = f"{product_name} - {packaging_info['primary']['name']}"
            elif bill_per_secondary:
                if packaging_info.get('primary') and packaging_info.get('secondary'):
                    primary_usage = Decimal(str(packaging_info['primary']['usage_per_pallet']))
                    secondary_usage_per_pallet = Decimal(str(packaging_info['secondary']['usage_per_pallet']))
                    pouches_per_box = primary_usage / secondary_usage_per_pallet
                    product_name = f"{product_name} - {packaging_info['secondary']['name']}"
                    display_qty = qty / pouches_per_box
                    display_price = price_per_unit * pouches_per_box
            elif bill_per_pallet:
                if packaging_info.get('primary') and packaging_info.get('pallet'):
                    pouches_per_pallet = Decimal(str(packaging_info['primary']['usage_per_pallet']))
                    product_name = f"{product_name} - {packaging_info['pallet']['name']}"
                    display_qty = qty / pouches_per_pallet
                    display_price = price_per_unit * pouches_per_pallet
            
            # Calculate line total in from-currency (always base: qty * price_per_unit)
            line_total_from_currency = qty * price_per_unit
            
            # Always accumulate total_amount for all document types
            total_amount += line_total_from_currency
            
            if doc_type_upper in ["INVOICE", "QUOTE", "PROFORMA"]:
                # Apply exchange rate
                display_price_converted = display_price * rate
                line_total_converted = line_total_from_currency * rate
                
                table_rows.append({
                    "batch_number": batch.batch_number if batch else "",
                    "sku": product_sku,
                    "product": product_name,
                    "size": batch.size if batch else "",
                    "qty": f"{display_qty:.2f}",
                    "price_per_unit": f"{display_price_converted:.2f}",
                    "price_per_unit_with_currency": f"{header.to_currency} {display_price_converted:.2f}",
                    "line_total": f"{line_total_converted:.2f}",
                    "line_total_with_currency": f"{header.to_currency} {line_total_converted:.2f}",
                })
            else:
                table_rows.append({
                    "batch_number": batch.batch_number if batch else "",
                    "sku": product_sku,
                    "product": product_name,
                    "size": batch.size if batch else "",
                    "qty": f"{display_qty:.2f}",
                })
        
        print(f"Processed {len(table_rows)} line items for HQ billing")
    
    elif header.batch_costings.exists():
        # SITE BILLING: Use batch_costings (with approvals)
        print(f"Using site batch_costings for billing document")
        print(f"Batch Costings: {[bc.pk for bc in header.batch_costings.all()]}")
        
        approvals = BatchPriceApproval.objects.filter(
            batch_costing__in=header.batch_costings.all(),
            is_approved=True
        ).select_related("batch", "batch__product", "batch_costing")
        
        print(f"Approved BatchPriceApprovals: {approvals.count()}")
        
        if approvals.count() > 0:
            print(f"Approval IDs: {[a.pk for a in approvals]}")
        else:
            # Check if there are UN-approved ones
            all_approvals = BatchPriceApproval.objects.filter(
                batch_costing__in=header.batch_costings.all()
            )
            print(f"Total (including unapproved) BatchPriceApprovals: {all_approvals.count()}")
            if all_approvals.count() > 0:
                print(f"WARNING: Found {all_approvals.count()} approvals but NONE are approved!")
        
        for approval in approvals:
            batch = approval.batch
            product = batch.product
            
            # Get entered qty (always in primary units/pouches)
            qty_mapping = get_qty_mapping(header.qty_for_invoice_data)
            entered_qty = qty_mapping.get(batch.batch_number, 0)
            
            price_per_unit = approval.batch_price_per_unit or Decimal("0.00")
            
            # Get packaging info dynamically
            from product_details.models import ProductComponent
            packaging_info = ProductComponent.get_packaging_info(product)
            
            # Start with full product name
            product_description = batch.product.product_name if batch.product else ""
            product_sku = batch.product.sku if batch.product and batch.product.sku else ""
            
            # Determine display values based on billing method
            # Uses local variables that may be overridden by query params for live preview
            display_qty = Decimal(str(entered_qty))
            display_price = price_per_unit
            
            if bill_per_primary:
                # Primary: append sub-category name
                if packaging_info.get('primary'):
                    product_description = f"{product_description} - {packaging_info['primary']['name']}"
                display_qty = Decimal(str(entered_qty))
                display_price = price_per_unit
                
            elif bill_per_secondary:
                # Secondary: append sub-category name and convert to boxes
                if packaging_info.get('primary') and packaging_info.get('secondary'):
                    primary_usage = Decimal(str(packaging_info['primary']['usage_per_pallet']))
                    secondary_usage_per_pallet = Decimal(str(packaging_info['secondary']['usage_per_pallet']))
                    
                    pouches_per_box = primary_usage / secondary_usage_per_pallet
                    
                    product_description = f"{product_description} - {packaging_info['secondary']['name']}"
                    display_qty = Decimal(str(entered_qty)) / pouches_per_box
                    display_price = price_per_unit * pouches_per_box
                    
            elif bill_per_pallet:
                # Pallet: append sub-category name and convert to pallets
                if packaging_info.get('primary') and packaging_info.get('pallet'):
                    pouches_per_pallet = Decimal(str(packaging_info['primary']['usage_per_pallet']))
                    
                    product_description = f"{product_description} - {packaging_info['pallet']['name']}"
                    display_qty = Decimal(str(entered_qty)) / pouches_per_pallet
                    display_price = price_per_unit * pouches_per_pallet
            
            # ✅ Base line total in from-currency (always: entered_qty * price_per_unit)
            line_total_from_currency = Decimal(str(entered_qty)) * price_per_unit
            
            # Always accumulate total_amount for all document types
            total_amount += line_total_from_currency

            if doc_type_upper in ["INVOICE", "QUOTE", "PROFORMA"]:
                # ✅ Apply exchange rate to display price and line total
                display_price_converted = display_price * rate
                line_total_converted = line_total_from_currency * rate
                
                table_rows.append({
                    "batch_number": batch.batch_number,
                    "sku": product_sku,
                    "product": product_description,
                    "size": batch.size or "",
                    "qty": f"{display_qty:.2f}",
                    "price_per_unit": f"{display_price_converted:.2f}",
                    "price_per_unit_with_currency": f"{header.to_currency} {display_price_converted:.2f}",
                    "line_total": f"{line_total_converted:.2f}",
                    "line_total_with_currency": f"{header.to_currency} {line_total_converted:.2f}",
                })
            else:
                table_rows.append({
                    "batch_number": batch.batch_number,
                    "sku": product_sku,
                    "product": product_description,
                    "size": batch.size or "",
                    "qty": f"{display_qty:.2f}",
                })
        
        print(f"Processed {len(table_rows)} batch costings for site billing")
        print(f"Total amount accumulated: {total_amount}")
        
        # Additional debug if table_rows is empty but batch_costings exist
        if len(table_rows) == 0 and header.batch_costings.exists():
            print("WARNING: Batch costings exist but no table rows generated!")
            print("Possible causes:")
            print("1. No BatchPriceApproval records found")
            print("2. BatchPriceApprovals are not approved (is_approved=False)")
            print("3. qty_for_invoice_data is empty")
            unapproved = BatchPriceApproval.objects.filter(
                batch_costing__in=header.batch_costings.all(),
                is_approved=False
            ).count()
            if unapproved > 0:
                print(f"   -> Found {unapproved} UNAPPROVED batch price approvals - these need to be approved first!")
    
    else:
        # FALLBACK: Check if this is an import with no batch_costings saved
        # (for existing records before the fix was applied)
        if header.import_source_site and header.import_source_invoice_number:
            print(f"Attempting fallback: looking up source invoice {header.import_source_invoice_number} from site {header.import_source_site.name}")
            try:
                source_invoice = BillingDocumentHeader.objects.get(
                    site=header.import_source_site,
                    base_number=header.import_source_invoice_number
                )
                source_batch_costings = source_invoice.batch_costings.all()
                if source_batch_costings.exists():
                    # Copy batch_costings to this header for future use
                    header.batch_costings.set(source_batch_costings)
                    print(f"✅ Copied {source_batch_costings.count()} batch_costings from source invoice")
                    
                    # Copy qty_for_invoice_data from source if HQ header doesn't have it
                    source_qty_data = source_invoice.qty_for_invoice_data or {}
                    if not header.qty_for_invoice_data and source_qty_data:
                        header.qty_for_invoice_data = source_qty_data
                        header.save(update_fields=['qty_for_invoice_data'])
                        print(f"✅ Copied qty_for_invoice_data from source invoice")
                    
                    # Use the source invoice's qty data for processing
                    raw_qty_data = header.qty_for_invoice_data or source_qty_data
                    qty_mapping = get_qty_mapping(raw_qty_data)
                    
                    # Now process them
                    approvals = BatchPriceApproval.objects.filter(
                        batch_costing__in=source_batch_costings,
                        is_approved=True
                    ).select_related("batch", "batch__product", "batch_costing")
                    
                    print(f"Approved BatchPriceApprovals from source: {approvals.count()}")
                    
                    for approval in approvals:
                        batch = approval.batch
                        product = batch.product
                        
                        entered_qty = qty_mapping.get(batch.batch_number, 0)
                        price_per_unit = approval.batch_price_per_unit or Decimal("0.00")
                        product_description = batch.product.product_name if batch.product else ""
                        product_sku = batch.product.sku if batch.product and batch.product.sku else ""
                        
                        display_qty = Decimal(str(entered_qty))
                        display_price = price_per_unit
                        
                        line_total_from_currency = Decimal(str(entered_qty)) * price_per_unit
                        total_amount += line_total_from_currency
                        
                        if doc_type_upper in ["INVOICE", "QUOTE", "PROFORMA"]:
                            display_price_converted = display_price * rate
                            line_total_converted = line_total_from_currency * rate
                            
                            table_rows.append({
                                "batch_number": batch.batch_number,
                                "sku": product_sku,
                                "product": product_description,
                                "size": batch.size or "",
                                "qty": f"{display_qty:.2f}",
                                "price_per_unit": f"{display_price_converted:.2f}",
                                "price_per_unit_with_currency": f"{header.to_currency} {display_price_converted:.2f}",
                                "line_total": f"{line_total_converted:.2f}",
                                "line_total_with_currency": f"{header.to_currency} {line_total_converted:.2f}",
                            })
                        else:
                            table_rows.append({
                                "batch_number": batch.batch_number,
                                "sku": product_sku,
                                "product": product_description,
                                "size": batch.size or "",
                                "qty": f"{display_qty:.2f}",
                            })
                    
                    print(f"Processed {len(table_rows)} rows from source invoice fallback")
                else:
                    print(f"WARNING: Source invoice has no batch_costings either!")
            except BillingDocumentHeader.DoesNotExist:
                print(f"ERROR: Source invoice {header.import_source_invoice_number} not found in site {header.import_source_site.name}")
            except Exception as e:
                print(f"ERROR in fallback: {e}")
        else:
            print("WARNING: No line_items or batch_costings linked to this billing header!")
    
    print(f"Total table rows: {len(table_rows)}")
    print(f"Total amount before exchange rate: {total_amount}")
    print(f"=== END DEBUG ===\n")


    client = header.client
    delivery_site = None
    if client:
        # Use explicitly selected delivery_institution if available
        if header.delivery_institution_id:
            delivery_site = header.delivery_institution
        else:
            # Fallback to first delivery site for client (for backward compatibility)
            delivery_site = DeliverySite.objects.filter(client=client).first()

    company_address = ""
    if company:
        address_parts = [
            company.address_line1,
            company.address_line2,
            company.city,
            company.postal_code,
            company.country,
        ]
        company_address = ", ".join([p for p in address_parts if p])

    # ✅ Totals in from-currency, then convert at the end
    sub_total = total_amount
    transport_cost_decimal = header.transport_cost or Decimal("0.00")
    total_before_tax = sub_total + transport_cost_decimal
    vat_rate = (header.vat_percentage or Decimal("15")) / Decimal("100")
    tax_amount = total_before_tax * vat_rate
    total_incl_tax = total_before_tax + tax_amount

    # ✅ Convert totals to to-currency using exchange rate
    display_sub_total = sub_total * rate
    display_transport = transport_cost_decimal * rate
    display_total_before_tax = total_before_tax * rate
    display_tax = tax_amount * rate
    display_total_incl = total_incl_tax * rate

    context = {
        "company_name": company.name if company else "",
        "company_legal_name": company.legal_name if company else "",
        "company_address_line1": company.address_line1 if company else "",
        "company_address_line2": company.address_line2 if company else "",
        "company_city": company.city if company else "",
        "company_province": company.province if company else "",
        "company_postal_code": company.postal_code if company else "",
        "company_country": company.country if company else "",
        "company_address": company_address,
        "company_phone": company.phone if company else "",
        "company_email": company.email if company else "",
        "company_vat_number": company.vat_number if company else "",
        "company_registration_number": company.registration_number if company else "",
        "bank_name": company.bank_name if company else "",
        "bank_account_name": company.bank_account_name if company else "",
        "bank_account_number": company.bank_account_number if company else "",
        "bank_branch_code": company.bank_branch_code if company else "",
        "client_legal_name": client.legal_name if client else "",
        "client_address_line1": client.address_line1 if client else "",
        "client_address_line2": client.address_line2 if client else "",
        "client_city": client.city if client else "",
        "client_province": client.province if client else "",
        "client_postal_code": client.postal_code if client else "",
        "client_country": client.country if client else "",
        "client_vat_number": client.vat_number if client else "",
        "client_payment_terms": client.payment_terms if client else "",
        "client_contact_person": client.contact_person if client else "",
        "client_phone": client.phone if client else "",
        "client_email": client.email if client else "",
        "delivery_address_line1": delivery_site.address_line1 if delivery_site else "",
        "delivery_address_line2": delivery_site.address_line2 if delivery_site else "",
        "delivery_city": delivery_site.city if delivery_site else "",
        "delivery_province": delivery_site.province if delivery_site else "",
        "delivery_postal_code": delivery_site.postal_code if delivery_site else "",
        "delivery_country": delivery_site.country if delivery_site else "",
        "document_type": document_type,
        "document_prefix": document_prefix,
        "document_number": f"{document_prefix} {header.base_number}" if document_prefix else header.base_number,
        "date": header.billing_date.strftime("%d %B %Y") if header.billing_date else "",
        "due_date": header.due_date.strftime("%d %B %Y") if header.due_date else "",
        "currency": (
            header.to_currency
            if doc_type_upper in ["INVOICE", "QUOTE", "PROFORMA"]
            else ""
        ),
        "vat_percentage": f"{header.vat_percentage:.2f}" if header.vat_percentage else "15.00",
        "transport_cost": (
            f"{display_transport:.2f}"
            if doc_type_upper in ["INVOICE", "QUOTE", "PROFORMA"]
            else ""
        ),
        "transport_cost_with_currency": (
            f"{header.to_currency} {display_transport:.2f}"
            if doc_type_upper in ["INVOICE", "QUOTE", "PROFORMA"]
            else ""
        ),
        "table_rows": table_rows,
        "sub_total": (
            f"{display_sub_total:.2f}"
            if doc_type_upper in ["INVOICE", "QUOTE", "PROFORMA"]
            else ""
        ),
        "sub_total_with_currency": (
            f"{header.to_currency} {display_sub_total:.2f}"
            if doc_type_upper in ["INVOICE", "QUOTE", "PROFORMA"]
            else ""
        ),
        "total_amount": (
            f"{display_total_before_tax:.2f}"
            if doc_type_upper in ["INVOICE", "QUOTE", "PROFORMA"]
            else ""
        ),
        "total_amount_with_currency": (
            f"{header.to_currency} {display_total_before_tax:.2f}"
            if doc_type_upper in ["INVOICE", "QUOTE", "PROFORMA"]
            else ""
        ),
        "total_tax": (
            f"{display_tax:.2f}"
            if doc_type_upper in ["INVOICE", "QUOTE", "PROFORMA"]
            else ""
        ),
        "total_tax_with_currency": (
            f"{header.to_currency} {display_tax:.2f}"
            if doc_type_upper in ["INVOICE", "QUOTE", "PROFORMA"]
            else ""
        ),
        "total_incl_tax": (
            f"{display_total_incl:.2f}"
            if doc_type_upper in ["INVOICE", "QUOTE", "PROFORMA"]
            else ""
        ),
        "total_incl_tax_with_currency": (
            f"{header.to_currency} {display_total_incl:.2f}"
            if doc_type_upper in ["INVOICE", "QUOTE", "PROFORMA"]
            else ""
        ),
    }

    if not company or not company.billing_template:
        return HttpResponse("No template configured for this company", status=400)

    try:
        # 1. Render DOCX from template - FIX broken tags first
        from inventory.views import fix_docx_jinja_tags
        fixed_template_path = fix_docx_jinja_tags(company.billing_template.path)
        doc = DocxTemplate(fixed_template_path)
        
        # Debug: Log what variables are being sent
        print(f"\n=== BILLING DOCUMENT GENERATION DEBUG ===")
        print(f"Document Type: {doc_type} ({document_type})")
        print(f"Template: {company.billing_template.path}")
        print(f"Site: {header.site.name if header.site else 'HQ'}")
        print(f"\nContext variables being passed:")
        for key in sorted(context.keys()):
            value = context[key]
            if isinstance(value, list):
                if value:
                    print(f"  {key}: LIST with {len(value)} items")
                    if value and isinstance(value[0], dict):
                        print(f"    First item keys: {list(value[0].keys())}")
                        print(f"    First item values: {list(value[0].values())[:3]}")
                else:
                    print(f"  {key}: EMPTY LIST")
            elif isinstance(value, dict):
                print(f"  {key}: DICT with {len(value)} keys")
            else:
                val_str = str(value)[:60]
                print(f"  {key}: {val_str}")
        print(f"\nTotal variables: {len(context)}")
        print(f"=== END DEBUG ===\n")
        
        doc.render(context)

        # 2. Save DOCX to temp file
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_docx:
            docx_path = tmp_docx.name
            doc.save(docx_path)

        # 3. Convert DOCX to PDF using Python libraries (no LibreOffice needed)
        try:
            from .docx_to_pdf import docx_to_pdf_bytes
            
            print("\n" + "="*60)
            print("ATTEMPTING PDF CONVERSION")
            print(f"DOCX Path: {docx_path}")
            print(f"DOCX exists: {os.path.exists(docx_path)}")
            print("="*60 + "\n")
            
            pdf_content = docx_to_pdf_bytes(docx_path)
            
            print("\n" + "="*60)
            print("✓ PDF CONVERSION SUCCESSFUL!")
            print(f"PDF size: {len(pdf_content)} bytes")
            print("="*60 + "\n")
            
            # Clean up temp DOCX file
            os.unlink(docx_path)
            
        except Exception as conversion_error:
            import traceback
            error_trace = traceback.format_exc()
            
            print("\n" + "="*60)
            print("✗ PDF CONVERSION FAILED!")
            print(f"Error: {str(conversion_error)}")
            print(f"Full traceback:\n{error_trace}")
            print("Falling back to DOCX...")
            print("="*60 + "\n")
            
            # Fallback: return DOCX if conversion fails
            with open(docx_path, 'rb') as f:
                docx_content = f.read()
            os.unlink(docx_path)
            response = HttpResponse(
                docx_content,
                content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )
            response['Content-Disposition'] = f'attachment; filename="{document_type}_{header.base_number}.docx"'
            response['X-PDF-Error'] = str(conversion_error)[:200]  # Add error in header for debugging
            return response

        # 4. Return PDF
        response = HttpResponse(pdf_content, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'inline; filename="{document_type}_{header.base_number}.pdf"'
        )
        return response

    except Exception as e:
        return HttpResponse(f"Error rendering document: {str(e)}", status=500)


def get_batch_pricing_rows_for_header(header: BillingDocumentHeader):
    """
    Build the same rows you show in the admin JS preview table.
    Returns a list of dicts:
    [
      {
        "batch_number": "...",
        "product": "...",
        "size": "...",
        "units": 1234,
        "status": "...",
        "ready_dispatch": 1234,
        "price_per_unit": Decimal(...),
        "approved": True/False,
      },
      ...
    ]
    """
    batch_costing = header.batch_costing
    if not batch_costing or not batch_costing.production_date:
        return []

    production = batch_costing.production_date
    batches = production.batches.select_related("product").all()

    rows = []
    for b in batches:
        # adapt these attributes to your real Batch fields
        rows.append({
            "batch_number": b.batch_number,
            "product": str(b.product) if b.product else "",
            "size": getattr(b, "size_display", "") or getattr(b, "size", ""),
            "units": b.shift_total or 0,
            "status": getattr(b, "status", ""),
            "ready_dispatch": getattr(b, "ready_dispatch", 0),
            "price_per_unit": getattr(b, "price_per_unit", batch_costing.price),
            "approved": getattr(b, "is_approved", False),
        })
    return rows

def email_billing_document(request, pk, doc_type):
    """
    Opens email with the PDF document:
    1. First downloads the PDF file
    2. Then opens mailto with pre-filled subject/body
    User just needs to attach the downloaded file.
    """
    header = get_object_or_404(BillingDocumentHeader, pk=pk)
    
    doc_type_upper = doc_type.upper()
    doc_type_map = {
        "INVOICE": "Invoice",
        "QUOTE": "Quote",
        "PROFORMA": "Proforma",
        "PICKING": "Picking Slip",
        "DELIVERY": "Delivery Note",
    }
    doc_prefix_map = {
        "INVOICE": "INV",
        "QUOTE": "QUO",
        "PROFORMA": "PRO",
        "PICKING": "PS",
        "DELIVERY": "DN",
    }
    document_type = doc_type_map.get(doc_type_upper, "Billing Document")
    document_prefix = doc_prefix_map.get(doc_type_upper, "")
    
    # Get client email
    client_email = header.client.email if header.client and header.client.email else ""
    
    if not client_email:
        return HttpResponse(
            "<html><body><h2>No client email address found</h2>"
            "<p>Please add an email address to the client record.</p>"
            "<script>setTimeout(function(){ window.close(); }, 3000);</script></body></html>",
            content_type="text/html"
        )
    
    # Build the PDF preview URL (to download)
    pdf_url = reverse("costing:billing_document_preview", args=[pk, doc_type_upper])
    
    # Build filename
    doc_number = f"{document_prefix} {header.base_number}" if document_prefix else header.base_number
    filename = f"{document_type.replace(' ', '_')}_{header.base_number}.pdf"
    
    # Build mailto link
    subject = f"{document_type} {doc_number}"
    body = f"""Dear {header.client.contact_person or header.client.name or 'Customer'},

Please find attached {document_type} {doc_number}.

Kind regards"""
    
    mailto_url = f"mailto:{client_email}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
    
    # Return HTML that:
    # 1. Downloads the PDF via hidden iframe
    # 2. Opens the mailto link
    # 3. Shows instructions
    return HttpResponse(
        f"""
        <html>
        <head>
            <title>Email {document_type}</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 40px; text-align: center; background: #f5f5f5; }}
                .container {{ background: white; padding: 30px; border-radius: 8px; max-width: 500px; margin: 0 auto; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                h2 {{ color: #417690; margin-bottom: 20px; }}
                .step {{ text-align: left; margin: 15px 0; padding: 10px; background: #f9f9f9; border-radius: 4px; }}
                .step-num {{ display: inline-block; width: 24px; height: 24px; background: #417690; color: white; border-radius: 50%; text-align: center; line-height: 24px; margin-right: 10px; font-size: 12px; }}
                .filename {{ font-family: monospace; background: #e8e8e8; padding: 2px 6px; border-radius: 3px; }}
                .close-btn {{ margin-top: 20px; padding: 10px 20px; background: #417690; color: white; border: none; border-radius: 4px; cursor: pointer; }}
                .close-btn:hover {{ background: #205067; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>📧 Email {document_type}</h2>
                <p>Your email client is opening with the document details.</p>
                
                <div class="step">
                    <span class="step-num">1</span>
                    PDF downloading: <span class="filename">{filename}</span>
                </div>
                <div class="step">
                    <span class="step-num">2</span>
                    Email opening with subject and body pre-filled
                </div>
                <div class="step">
                    <span class="step-num">3</span>
                    Attach the downloaded PDF to the email
                </div>
                
                <button class="close-btn" onclick="window.close()">Close Window</button>
            </div>
            
            <!-- Hidden iframe to trigger PDF download -->
            <iframe id="pdf-download" style="display:none;"></iframe>
            
            <script>
                // Step 1: Download PDF
                var downloadUrl = "{pdf_url}";
                var link = document.createElement('a');
                link.href = downloadUrl;
                link.download = "{filename}";
                link.target = "_blank";
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                
                // Step 2: Open mailto after short delay
                setTimeout(function() {{
                    window.location.href = "{mailto_url}";
                }}, 1000);
                
                // Auto-close after 10 seconds
                setTimeout(function() {{
                    window.close();
                }}, 10000);
            </script>
        </body>
        </html>
        """,
        content_type="text/html"
    )

@require_GET
def batches_by_date(request, date_str):
    """Return batch costing IDs for a given production date"""
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'batch_costing_ids': []})
    
    batch_ids = BatchCosting.objects.filter(
        production_date__date=target_date
    ).values_list('pk', flat=True)
    
    return JsonResponse({'batch_costing_ids': list(batch_ids)})

@require_GET
def dates_to_batch_costings(request):
    """Convert DD/MM/YYYY dates to batch_costing IDs (filtered by site)"""
    from datetime import datetime
    from manufacturing.models import Production
    from costing.models import BatchCosting
    
    dates_str = request.GET.get('dates', '')
    site_id = request.GET.get('site_id')  # NEW: Get site from request
    
    if not dates_str:
        return JsonResponse({'batch_costing_ids': []})
    
    date_strings = [d.strip() for d in dates_str.split(',') if d.strip()]
    batch_costing_ids = []
    seen = set()
    
    for ds in date_strings:
        try:
            # Parse DD/MM/YYYY
            date_obj = datetime.strptime(ds, "%d/%m/%Y").date()
        except ValueError:
            continue
        
        # Find Production for this date - FILTERED BY SITE if provided
        if site_id:
            prod = Production.objects.filter(production_date=date_obj, site_id=site_id).first()
        else:
            prod = Production.objects.filter(production_date=date_obj).first()
        
        if not prod:
            continue
        
        # Find BatchCosting for this Production
        bc = BatchCosting.objects.filter(production_date=prod).first()
        if bc and bc.pk not in seen:
            batch_costing_ids.append(bc.pk)
            seen.add(bc.pk)
    
    return JsonResponse({'batch_costing_ids': batch_costing_ids})


@staff_member_required
@require_GET
def get_site_invoice_data(request):
    """API endpoint to fetch invoice data from a site for import"""
    site_id = request.GET.get('site_id')
    invoice_number = request.GET.get('invoice_number')
    
    if not site_id or not invoice_number:
        return JsonResponse({'error': 'Missing site_id or invoice_number'}, status=400)
    
    try:
        # Get the invoice from the site
        site_invoice = BillingDocumentHeader.objects.get(
            site_id=site_id,
            base_number=invoice_number
        )
        
        # Extract batch costing data with pricing
        batch_data = []
        for batch_costing in site_invoice.batch_costings.all():
            try:
                production = batch_costing.production_date
                if not production:
                    continue
                
                # Get all batches for this production date
                batches = production.batch_items.all()
                
                for batch in batches:
                    # Extract product name from batch
                    product_name = batch.product.product_name if batch.product else ''
                    
                    # Get size from batch
                    size = batch.size if batch.size else ''
                    
                    # Get qty_for_invoice from the JSON data
                    qty_for_invoice = 0
                    if site_invoice.qty_for_invoice_data:
                        qty_for_invoice = site_invoice.qty_for_invoice_data.get(batch.batch_number, 0)
                    
                    # Get the approved price from BatchPriceApproval
                    approved_price = batch_costing.price
                    price_approval = batch_costing.price_approvals.filter(batch=batch, is_approved=True).first()
                    if price_approval:
                        approved_price = price_approval.batch_price_per_unit
                    
                    batch_data.append({
                        'batch_costing_id': batch_costing.pk,
                        'batch_id': batch.batch_number,
                        'product_name': product_name,
                        'size': size,
                        'qty_for_invoice': qty_for_invoice,
                        'price_per_unit': str(batch_costing.price),
                        'inv_price': str(approved_price),
                    })
            except Exception as e:
                continue
        
        # Extract invoice-level data
        invoice_data = {
            'client': site_invoice.client.name if site_invoice.client else '',
            'client_id': site_invoice.client.pk if site_invoice.client else None,
            'billing_date': site_invoice.billing_date.strftime('%d-%m-%Y') if site_invoice.billing_date else '',
            'due_date': site_invoice.due_date.strftime('%d-%m-%Y') if site_invoice.due_date else '',
            'from_currency': site_invoice.from_currency,
            'to_currency': site_invoice.to_currency,
            'exchange_rate': str(site_invoice.exchange_rate),
            'bill_per_primary': site_invoice.bill_per_primary,
            'bill_per_secondary': site_invoice.bill_per_secondary,
            'bill_per_pallet': site_invoice.bill_per_pallet,
            'transporters': site_invoice.transporters.pk if site_invoice.transporters else None,
            'transporters_name': site_invoice.transporters.name if site_invoice.transporters else '',
            'transport_cost': str(site_invoice.transport_cost),
            'batch_data': batch_data,
            'qty_for_invoice_data': site_invoice.qty_for_invoice_data if site_invoice.qty_for_invoice_data else {},
        }
        
        return JsonResponse(invoice_data)
    
    except BillingDocumentHeader.DoesNotExist:
        return JsonResponse({'error': f'Invoice {invoice_number} not found for this site'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@staff_member_required
@require_http_methods(["GET"])
def get_costing_price(request, costing_type, costing_id):
    """
    API endpoint to fetch price_per_unit for a given costing
    costing_type: 'overhead', 'salary', or 'investor_loan'
    costing_id: The ID of the costing record
    """
    try:
        from .models import OverheadCosting, SalaryCosting, InvestorLoanCosting
        
        price_per_unit = 0
        
        if costing_type == 'overhead':
            costing = OverheadCosting.objects.get(pk=costing_id)
            price_per_unit = float(costing.price_per_unit)
        elif costing_type == 'salary':
            costing = SalaryCosting.objects.get(pk=costing_id)
            price_per_unit = float(costing.price_per_unit)
        elif costing_type == 'investor_loan':
            costing = InvestorLoanCosting.objects.get(pk=costing_id)
            price_per_unit = float(costing.price_per_unit)
        else:
            return JsonResponse({'error': 'Invalid costing type'}, status=400)
        
        return JsonResponse({'price_per_unit': price_per_unit})
    
    except (OverheadCosting.DoesNotExist, SalaryCosting.DoesNotExist, InvestorLoanCosting.DoesNotExist):
        return JsonResponse({'error': 'Costing not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

