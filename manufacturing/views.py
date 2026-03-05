from django import forms
from django.db.models import Sum, Q
from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404, HttpResponse, JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.db import transaction
from datetime import datetime
from decimal import Decimal
import json
from manufacturing.utils import log_field_change

from .models import Batch, Waste, MeatWaste, NSIDocument, BatchContainer, BatchProductInventoryUsed, Sauce, MeatProductionSummary, DefrostDocument
from inventory.models import StockItem, StockTransaction, Container, PackagingBalance, RecipeStockItemBalance
from product_details.models import Product, ProductComponent, ProductRecipeItem
from manufacturing.models import ProductionSummaryItem
from manufacturing.models import Production
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.contenttypes.models import ContentType

def log_change(user, obj, message):
    """Create a LogEntry for any model - Django 6 compatible"""
    try:
        LogEntry.objects.create(
            user_id=user.pk,
            content_type_id=ContentType.objects.get_for_model(obj).pk,
            object_id=str(obj.pk),
            object_repr=str(obj)[:200],
            action_flag=CHANGE,
            change_message=message,
        )
    except Exception as e:
        pass  # Silently handle logging errors

def normalize_value(val):
    """
    Normalize a value for comparison - handles decimals, units, etc.
    "31.00" → "31", "19500.00L" → "19500L", "0.00kg" → "0kg"
    Also treats 0, "0", empty string, and None as equivalent.
    """
    if val in (None, '', 'None', 'False', False):
        return ''
    
    s = str(val)
    
    # Extract numeric part and unit suffix (like "kg", "L", "%", etc.)
    import re
    match = re.match(r'^(-?\d+\.?\d*)(.*?)$', s)
    if match:
        num_str, suffix = match.groups()
        try:
            # Convert to float and back to remove trailing zeros
            num = float(num_str)
            # Treat 0 as empty (no change from nothing to zero)
            if num == 0:
                return ''
            # If it's a whole number, show without decimals
            if num == int(num):
                return f"{int(num)}{suffix}"
            else:
                return f"{num:g}{suffix}"  # :g removes trailing zeros
        except ValueError:
            pass
    
    return s

def get_field_changes(old_values, new_values):
    """
    Compare old vs new values and return only the actual changes.
    old_values: dict like {'status': 'In Incubation', 'incubation_start': '2025-01-10'}
    new_values: dict like {'status': 'Certified', 'incubation_start': '2025-01-10'}
    Returns: dict of only changed fields {'status': 'In Incubation → Certified'}
    """
    changes = {}
    for key, new_val in new_values.items():
        old_val = old_values.get(key)
        # Normalize both values for comparison
        old_norm = normalize_value(old_val)
        new_norm = normalize_value(new_val)
        
        if old_norm != new_norm:
            if old_norm and new_norm:
                changes[key] = f"{old_norm} → {new_norm}"
            elif new_norm:
                changes[key] = new_norm
    return changes

def log_model_changes(user, production, model_name, old_values, new_values):
    """
    Only log if actual changes were made (like Django admin).
    
    user: request.user
    production: Production object
    model_name: str like "Batch A014", "Sauce", "Meat Summary"
    old_values: dict of field values BEFORE save
    new_values: dict of field values AFTER save
    """
    changes = get_field_changes(old_values, new_values)
    if changes:
        change_str = ', '.join([f"{k}: {v}" for k, v in changes.items()])
        log_change(user, production, f"{model_name}: {change_str}")
    # If no changes, do nothing (no log entry)
        
def product_size_api(request, pk):
    """Get product size and SKU data"""
    try:
        p = Product.objects.get(pk=pk)
        return JsonResponse({'size': p.size or '', 'sku': p.sku or ''})
    except Product.DoesNotExist:
        return JsonResponse({'size': '', 'sku': ''})


def product_sku_options_api(request, pk):
    """Get all SKU options for products with the same product_name and site"""
    try:
        product = Product.objects.get(pk=pk)
        
        # Log what we're searching for
        import sys
        print(f"[SKU API] Product ID: {pk}", file=sys.stderr)
        print(f"[SKU API] Product Name: {product.product_name}", file=sys.stderr)
        print(f"[SKU API] Product Site: {product.site}", file=sys.stderr)
        print(f"[SKU API] Product SKU: {product.sku}", file=sys.stderr)
        
        # Get all products with the same product_name on the SAME SITE
        products = Product.objects.filter(
            product_name=product.product_name,
            site=product.site  # ✅ Filter by SAME site
        ).values_list('pk', 'sku', 'size').distinct()
        
        print(f"[SKU API] Found {products.count()} matching products", file=sys.stderr)
        for p in products:
            print(f"[SKU API]   - ID:{p[0]}, SKU:{p[1]}, Size:{p[2]}", file=sys.stderr)
        
        options = [{'id': p[0], 'sku': p[1] or '', 'size': p[2] or ''} for p in products]
        return JsonResponse({'options': options})
    except Product.DoesNotExist:
        print(f"[SKU API] Product {pk} not found", file=sys.stderr)
        return JsonResponse({'options': []})
    except Exception as e:
        print(f"[SKU API] Error: {str(e)}", file=sys.stderr)
        return JsonResponse({'options': [], 'error': str(e)})



def get_batch_ref_type(batch_ref_string, stock_item):
    """
    Auto-detect if batch_ref is from inventory (stock_source) or manufacturing (production)
    by checking if it exists in StockTransaction
    """
    if not batch_ref_string:
        return 'production'
    
    from inventory.models import StockTransaction
    
    # Check if exists in StockTransaction for this stock_item
    if StockTransaction.objects.filter(
        batch_ref=batch_ref_string,
        stock_item=stock_item
    ).exists():
        return 'stock_source'
    
    # Otherwise it's a production batch
    return 'production'
    
# ============= API VIEW =============

@require_http_methods(["GET"])
def get_batch_date(request):
    """API endpoint to get batch production date"""
    batch_number = request.GET.get('batch_number')
    
    if batch_number:
        try:
            batch = Batch.objects.get(batch_number=batch_number)
            return JsonResponse({
                'success': True,
                'production_date': batch.production_date.strftime('%Y-%m-%d') if batch.production_date else None
            })
        except Batch.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Batch not found'})
    
    return JsonResponse({'success': False, 'error': 'No batch number provided'})

# ============= FORMS =============

class ProductionDataForm(forms.ModelForm):
    class Meta:
        model = Batch
        fields = ['a_no', 'batch_number', 'product', 'size', 'shift_total', 'production_date']

class ProductionInfoForm(forms.ModelForm):
    class Meta:
        model = Batch
        fields = ['incubation_start', 'incubation_end', 'certification_date', 'dispatch_date', 'status', 'nsi_submission_date']

# ============= HELPER FUNCTIONS =============

def calculate_opening_balance_for_item(stock_item, production_date):
    """
    Calculate opening balance = previous production's closing balance for this item
    Returns 0 if no previous production exists
    """
    from inventory.models import PackagingBalance, RecipeStockItemBalance
    
    # For Packaging items
    previous_packaging = PackagingBalance.objects.filter(
        stock_item=stock_item,
        production_date__lt=production_date
    ).order_by('-production_date').first()
    
    if previous_packaging:
        return float(previous_packaging.closing_balance) or 0
    
    # For Recipe items (Sauce)
    previous_recipe = RecipeStockItemBalance.objects.filter(
        stock_item=stock_item,
        production_date__lt=production_date
    ).order_by('-production_date').first()
    
    if previous_recipe:
        return float(previous_recipe.closing_balance) or 0
    
    return 0
    
def filter_sauce_batch_refs_by_flag(sauce_items):
    """
    If cancel_opening_use_bookout == True  → show ONLY booked ref.
    If cancel_opening_use_bookout == False → show BOTH refs (balance / booked).
    """
    for stock_item_id, data in sauce_items.items():
        cancel_flag = data.get('cancel_opening_use_bookout', False)
        before = data.get('batch_ref', '')
        
        if cancel_flag:
            data['batch_ref'] = data.get('batch_ref_booked', '')
        else:
            bal = data.get('batch_ref_balance', '')
            booked = data.get('batch_ref_booked', '')
            if bal and booked and bal != booked:
                data['batch_ref'] = f"{bal} / {booked}"
            else:
                data['batch_ref'] = bal or booked
        
        after = data.get('batch_ref', '')
    
    return sauce_items
    
def get_sauce_recipe_bookouts(batch, current_site=None):
    """
    For each RECIPE COMPONENT:
    1. Get opening batch_ref from previous RecipeStockItemBalance
    2. Get booked out batch_ref from StockTransaction
    Show both if different, one if same
    """
    if not batch.product:
        return {}

    from inventory.models import StockTransaction, RecipeStockItemBalance

    data = {}
    
    recipe_items = ProductRecipeItem.objects.filter(
        recipe__product=batch.product
    ).select_related('stock_item')

    for recipe_item in recipe_items:
        stock_item = recipe_item.stock_item
        if not stock_item:
            continue

        # ✅ GET OPENING BATCH REF (from previous production's balance)
        previous_recipe = RecipeStockItemBalance.objects.filter(
            stock_item=stock_item,
            production_date__lt=batch.production_date
        ).order_by('-production_date').first()
        batch_ref_balance = previous_recipe.batch_ref if previous_recipe else ''

        # Find PREVIOUS production
        previous_prod_qs = Batch.objects.filter(
            production_date__lt=batch.production_date,
            product=batch.product
        )
        if current_site:
            previous_prod_qs = previous_prod_qs.filter(site=current_site)
        previous_prod = previous_prod_qs.order_by('-production_date').first()

        if previous_prod:
            # Get transactions BETWEEN previous and current production
            all_bookouts = StockTransaction.objects.filter(
                stock_item=stock_item,
                transaction_type='OUT',
                transaction_date__gt=previous_prod.production_date,
                transaction_date__lte=batch.production_date
            )
            if current_site:
                all_bookouts = all_bookouts.filter(site=current_site)
            all_bookouts = all_bookouts.order_by('-transaction_date')
        else:
            # First production - all transactions up to now
            all_bookouts = StockTransaction.objects.filter(
                stock_item=stock_item,
                transaction_type='OUT',
                transaction_date__lte=batch.production_date
            )
            if current_site:
                all_bookouts = all_bookouts.filter(site=current_site)
            all_bookouts = all_bookouts.order_by('-transaction_date')

        # ✅ JUST USE THE FIRST (LATEST) TRANSACTION IN THE RANGE
        latest_unused = all_bookouts.last() if all_bookouts.exists() else None  # ✅ Get OLDEST (first created)
        batch_ref_booked = (latest_unused.batch_ref.split(',')[0].strip() if latest_unused and latest_unused.batch_ref else '')
         
        # ✅ GET FLAG FROM CURRENT production, NOT previous
        current_recipe = RecipeStockItemBalance.objects.filter(
            stock_item=stock_item,
            production_date=batch.production_date  # ← CURRENT, not previous!
        ).first()

        cancel_flag = current_recipe.cancel_opening_use_bookout if current_recipe else False

        # ✅ COMBINE BOTH BATCH REFS - BUT RESPECT FLAG
        if cancel_flag:
            batch_ref_display = batch_ref_booked
    
        elif batch_ref_balance and batch_ref_booked and batch_ref_balance != batch_ref_booked:
            batch_ref_display = f"{batch_ref_balance} / {batch_ref_booked}"
        elif batch_ref_balance or batch_ref_booked:
            batch_ref_display = batch_ref_balance or batch_ref_booked
        else:
            batch_ref_display = ''

        data[str(stock_item.id)] = {
            "stock_item_name": stock_item.name,
            "unit_of_measure_name": getattr(stock_item.unit_of_measure, "abbreviation", "Litre") if stock_item.unit_of_measure else "Litre",
            "batch_ref": batch_ref_display,  # ✅ COMBINED
            "batch_ref_balance": batch_ref_balance,  # ✅ SEPARATE
            "batch_ref_booked": batch_ref_booked,  # ✅ SEPARATE
            "booked_out_stock": float(latest_unused.quantity) if latest_unused else 0,
        }

    return data

def get_sauce_recipe_openings(batch, current_site=None):
    """
    For each RECIPE COMPONENT, pull PREVIOUS production's closing_balance.
    Returns closing_balance keyed by stock_item.id (opening for today).
    """
    if not batch.product:
        return {}

    from inventory.models import RecipeStockItemBalance

    data = {}
    
    recipe_items = ProductRecipeItem.objects.filter(
        recipe__product=batch.product
    ).select_related('stock_item')

    for recipe_item in recipe_items:
        stock_item = recipe_item.stock_item
        if not stock_item:
            continue

        # ✅ Get PREVIOUS production's closing_balance
        previous_balance = RecipeStockItemBalance.objects.filter(
            stock_item=stock_item,
            production_date__lt=batch.production_date
        ).order_by('-production_date').first()

        if previous_balance:
            data[str(stock_item.id)] = {
                "closing_balance": float(previous_balance.closing_balance) or 0,
            }
        else:
            data[str(stock_item.id)] = {
                "closing_balance": 0,
            }

    return data

def get_packaging_data(batch, current_site=None, packaging_category=None):
    """
    Get packaging items - pull BOTH:
    1. Opening batch_ref from previous PackagingBalance
    2. Booked out batch_ref from StockTransaction
    If different, show both. If same, show once.
    
    packaging_category: The category name to filter packaging items by (e.g., 'Packing', 'Test packaging')
    If None, defaults to 'Packing' for backwards compatibility.
    """
    from inventory.models import StockTransaction, PackagingBalance
    
    # Default to 'Packing' if not provided
    if not packaging_category:
        packaging_category = 'Packing'
    
    packaging_items = {}
    
    if not batch or not batch.product:
        return {}
    
    # ✅ Get packaging components and filter by site
    packing_components = batch.product.components.filter(
        stock_item__category__name__iexact=packaging_category
    )
    if current_site:
        packing_components = packing_components.filter(stock_item__site=current_site)
    
    
    for component in packing_components:
        stock_item = component.stock_item
        if stock_item:
            stock_item_id = str(stock_item.id)
            
            
            # ✅ GET SAVED PACKAGING BALANCE FIRST (at the top!)
            saved_balance = PackagingBalance.objects.filter(
                stock_item=stock_item,
                production_date=batch.production_date
            ).first()
            
            # ✅ GET OPENING BATCH REF (from previous production's balance)
            previous_packaging = PackagingBalance.objects.filter(
                stock_item=stock_item,
                production_date__lt=batch.production_date
            ).order_by('-production_date').first()
            batch_ref_balance = previous_packaging.batch_ref if previous_packaging else ''
            
            # ✅ GET BOOKED OUT BATCH REF (from ALL OUT transactions, not just the first)
            # ✅ EXCLUDE transactions with manufacturing batch patterns
            import re
            mfg_pattern = r'[A-Z]\d{5}CH\d{2}[A-Z]'
            
            previous_prod_qs = Batch.objects.filter(
                production_date__lt=batch.production_date,
                product=batch.product
            )
            if current_site:
                previous_prod_qs = previous_prod_qs.filter(site=current_site)
            previous_prod = previous_prod_qs.order_by('-production_date').first()


            if previous_prod:
                # Get transactions BETWEEN previous and current production
                all_bookouts = StockTransaction.objects.filter(
                    stock_item=stock_item,
                    transaction_type='OUT',
                    transaction_date__gt=previous_prod.production_date,
                    transaction_date__lte=batch.production_date
                )
                if current_site:
                    all_bookouts = all_bookouts.filter(site=current_site)
                all_bookouts = all_bookouts.order_by('-transaction_date')
            else:
                # First production - all transactions up to now
                all_bookouts = StockTransaction.objects.filter(
                    stock_item=stock_item,
                    transaction_type='OUT',
                    transaction_date__lte=batch.production_date
                )
                if current_site:
                    all_bookouts = all_bookouts.filter(site=current_site)
                all_bookouts = all_bookouts.order_by('-transaction_date')

            # ✅ FILTER OUT transactions with manufacturing batch refs
            valid_bookouts = [tx for tx in all_bookouts if not (tx.batch_ref and re.search(mfg_pattern, tx.batch_ref))]
            
            # ✅ COLLECT ALL VALID BATCH REFS from all transactions (not just first one)
            # Group by batch_ref and keep unique references in order
            batch_refs_list = []
            seen_refs = set()
            for tx in valid_bookouts:
                if tx.batch_ref and tx.batch_ref not in seen_refs:
                    batch_refs_list.append(tx.batch_ref)
                    seen_refs.add(tx.batch_ref)
            
            # Latest transaction for qty info
            latest_unused = valid_bookouts[0] if valid_bookouts else None

            # ✅ ===== NEW LOGIC: EXTRACT OPENING AND BOOKED REFS =====
            opening_batch_ref = ""
            batch_ref_booked = ""
            
            if saved_balance and saved_balance.batch_ref:
                import re
                # Check if the saved batch_ref contains " / " (split mode)
                if ' / ' in saved_balance.batch_ref:
                    # Split into opening and booked parts
                    parts = saved_balance.batch_ref.split(' / ')
                    opening_batch_ref = parts[0].strip()
                    batch_ref_booked = parts[1].strip()
                    # ✅ FILTER OUT manufacturing batch patterns from both
                    if re.search(r'[A-Z]\d{5}CH\d{2}[A-Z]', opening_batch_ref):
                        opening_batch_ref = ""
                    if re.search(r'[A-Z]\d{5}CH\d{2}[A-Z]', batch_ref_booked):
                        batch_ref_booked = ""
                else:
                    # Single ref - use saved, check opening_batch_ref field
                    raw_ref = saved_balance.batch_ref.strip()
                    # ✅ FILTER OUT manufacturing batch patterns
                    if not re.search(r'[A-Z]\d{5}CH\d{2}[A-Z]', raw_ref):
                        batch_ref_booked = raw_ref
                    else:
                        batch_ref_booked = ""
                    opening_batch_ref = saved_balance.opening_batch_ref or ""
            elif saved_balance and saved_balance.opening_batch_ref:
                opening_batch_ref = saved_balance.opening_batch_ref.strip()
            
            # If still empty, try to get from previous balance
            if not opening_batch_ref and batch_ref_balance:
                opening_batch_ref = batch_ref_balance
            
            # If still empty, try from all transactions collected
            if not batch_ref_booked and batch_refs_list:
                # Join all batch refs with " / " separator (since there can be multiple bookouts)
                batch_ref_booked = " / ".join(batch_refs_list)

    
            # ✅ COMBINE FOR DISPLAY
            if opening_batch_ref and batch_ref_booked:
                batch_ref_display = f"{opening_batch_ref} / {batch_ref_booked}"
            elif batch_ref_booked:
                batch_ref_display = batch_ref_booked
            elif opening_batch_ref:
                batch_ref_display = opening_batch_ref
            else:
                batch_ref_display = ""
  
            packaging_items[stock_item_id] = {
                'stock_item_name': stock_item.name,
                'stock_item_id': stock_item.id,
                'unit': stock_item.unit_of_measure.abbreviation if stock_item.unit_of_measure else 'Unit',
                'opening_balance': calculate_opening_balance_for_item(stock_item, batch.production_date),
                'batch_ref': batch_ref_display,  # ✅ COMBINED
                'batch_ref_balance': opening_batch_ref,  # ✅ OPENING REF
                'batch_ref_booked': batch_ref_booked,  # ✅ BOOKED REF
                'booked_out_stock': float(latest_unused.quantity) if latest_unused else 0,
                'closing_balance': float(saved_balance.closing_balance) if saved_balance else 0,
                'amended_reason': saved_balance.amended_reason if saved_balance else '',
                'cancel_opening_use_bookout': saved_balance.cancel_opening_use_bookout if saved_balance else False,
            }
    
    packaging_items = filter_batch_refs_by_flag(packaging_items)
    
    return packaging_items

def get_packaging_openings(batch, current_site=None, packaging_category=None):
    """
    Get packaging items opening balances from PREVIOUS production's closing_balance.
    Returns closing_balance keyed by stock_item.id (opening for today).
    
    packaging_category: The category name to filter packaging items by (e.g., 'Packing', 'Test packaging')
    If None, defaults to 'Packing' for backwards compatibility.
    """
    from inventory.models import PackagingBalance
    
    # Default to 'Packing' if not provided
    if not packaging_category:
        packaging_category = 'Packing'
    
    packaging_openings = {}
    
    
    if not batch or not batch.product:
        return {}
    
    # ✅ Get packaging components with dynamic category and site filtering
    packing_components = batch.product.components.filter(
        stock_item__category__name__iexact=packaging_category
    )
    if current_site:
        packing_components = packing_components.filter(stock_item__site=current_site)
    
    
    for component in packing_components:
        stock_item = component.stock_item
        if stock_item:
            stock_item_id = str(stock_item.id)
            
            
            # ✅ Get PREVIOUS production's closing_balance
            previous_balance = PackagingBalance.objects.filter(
                stock_item=stock_item,
                production_date__lt=batch.production_date  # ✅ BEFORE today only
            ).order_by('-production_date').first()
            
            if previous_balance:
                packaging_openings[stock_item_id] = {
                    'closing_balance': float(previous_balance.closing_balance) or 0,
                }
            else:
                packaging_openings[stock_item_id] = {
                    'closing_balance': 0,
                }
    
    return packaging_openings

def filter_batch_refs_by_flag(packaging_items):
    """
    If cancel_opening_use_bookout == True  → show ONLY booked ref.
    If cancel_opening_use_bookout == False → show BOTH refs (balance / booked).
    Uses SAVED checkbox state from database.
    """
    for stock_item_id, data in packaging_items.items():
        # ✅ Get the SAVED checkbox state
        cancel_flag = data.get('cancel_opening_use_bookout', False)
        
        
        if cancel_flag:
            # ✅ Checkbox is CHECKED - show ONLY booked ref
            data['batch_ref'] = data.get('batch_ref_booked', '')
        else:
            # ✅ Checkbox is UNCHECKED - show both
            bal = data.get('batch_ref_balance', '')
            booked = data.get('batch_ref_booked', '')
            if bal and booked and bal != booked:
                data['batch_ref'] = f"{bal} / {booked}"
            else:
                data['batch_ref'] = bal or booked
    
    return packaging_items
  
def get_meat_containers_opening_balance(batch, current_site=None):
    """
    Get opening balance for meat containers from PREVIOUS production's Stock Left.
    Keys by container_id (container_number or batch_ref) to match across productions.
    Returns dict: { container_id: { 'opening_balance': stock_left_value } }
    """
    meat_openings = {}
    
    if not batch or not batch.product:
        return {}
    
    # Find PREVIOUS production for same product
    previous_prod_qs = Batch.objects.filter(
        production_date__lt=batch.production_date,
        product=batch.product
    )
    if current_site:
        previous_prod_qs = previous_prod_qs.filter(site=current_site)
    previous_prod = previous_prod_qs.order_by('-production_date').first()
    
    if not previous_prod:
        # First production - no previous balance
        return {}
    
    
    # Get ALL containers used in PREVIOUS production
    previous_containers = BatchContainer.objects.filter(
        production_date=previous_prod.production_date
    )
    # ✅ ALSO filter by site to match current site's containers
    if current_site:
        previous_containers = previous_containers.filter(
            Q(container__site=current_site) |  # Import containers from current site
            Q(container__isnull=True)  # All local items (batch_ref)
        )
    
    for bc in previous_containers:
        # Get container identifier (same way as batch_containers_data uses)
        # This matches the key used in the current production's batch containers
        container_id = bc.container.container_number if bc.container else bc.batch_ref
        
        if container_id:
            # Stock Left from previous batch becomes opening for current batch
            meat_openings[container_id] = {
                'opening_balance': float(bc.stock_left) if bc.stock_left else 0,
            }
    
    return meat_openings

def get_available_containers_with_stock(batch, current_site=None):
    """
    Returns containers with calculated available_stock.
    ONLY counts usage from production_dates BEFORE the current production_date.
    Filters to ONLY containers with stock_items in the MAIN product component category.
    """
    # ✅ Get the main product component category dynamically (same as stock transactions)
    main_comp = batch.product.main_product_components.select_related('category').first() if batch.product else None
    main_component_category = main_comp.category.name if main_comp and main_comp.category else 'Meat'
    
    # ✅ Filter containers by: status='Available' AND stock_item category matches main component
    available_containers = Container.objects.filter(
        status='Available',
        stock_item__category__name__iexact=main_component_category
    )
    if current_site:
        available_containers = available_containers.filter(site=current_site)
    available_containers = available_containers.order_by('container_number')
    containers_with_stock = []
    
    current_production_date = batch.production_date
    
    for container in available_containers:
        # ✅ Count total used from dates BEFORE this production_date
        total_used = BatchContainer.objects.filter(
            container=container,
            production_date__lt=current_production_date  # ✅ BEFORE this date only
        ).aggregate(total=Sum('kg_frozen_meat_used'))['total'] or Decimal('0')
        
        # Calculate available stock
        available_stock = max(Decimal('0'), container.net_weight - total_used)
        
        containers_with_stock.append({
            'pk': container.container_number,
            'container_number': container.container_number,
            'net_weight': container.net_weight,
            'available_stock': available_stock,
        })
    
    return containers_with_stock

def get_available_stock_transactions_with_stock(batch, current_site=None):
    """
    Get available stock transactions for the MAIN PRODUCT COMPONENT category (dynamic).
    This is the meat category - pulls dynamically from MainProductComponent.
    """
    # ✅ Get the main product component category dynamically
    main_comp = batch.product.main_product_components.select_related('category').first() if batch.product else None
    main_component_category = main_comp.category.name if main_comp and main_comp.category else 'Meat'
    
    # ✅ Show all stock transactions for this category (IN type, not yet processed)
    # Include all statuses except Processed
    stock_transactions = StockTransaction.objects.filter(
        transaction_type='IN',
        category__name__iexact=main_component_category
    ).exclude(status='Processed')
    
    # ✅ MUST filter by site
    if current_site:
        stock_transactions = stock_transactions.filter(site=current_site)
    
    stock_transactions = stock_transactions.select_related('stock_item', 'supplier', 'batch').order_by('-transaction_date')
    
    transactions_with_stock = []
    
    for trans in stock_transactions:
        # Use batch's batch_number if available, otherwise use batch_ref, otherwise TX-{pk}
        if trans.batch and trans.batch.batch_number:
            ref_display = trans.batch.batch_number
        elif trans.batch_ref:
            ref_display = trans.batch_ref
        else:
            ref_display = f"TX-{trans.pk}"
        
        available_stock = trans.quantity
        
        transactions_with_stock.append({
            'pk': ref_display,
            'batch_ref': ref_display,
            'reference': ref_display,
            'net_weight': float(trans.quantity),
            'available_stock': float(available_stock),
            'source_type': 'local',
        })
    
    return transactions_with_stock

def get_product_usage_data(batch):
    """Get product usage items for a batch - WITH SAUCE CONCENTRATE CALCULATION
    
    Uses BatchComponentSnapshot values when available to preserve original usage rates
    even if product details have changed since the batch was created.
    """
    import math
    from manufacturing.models import BatchComponentSnapshot
    
    product = batch.product
    items = []
    if not product:
        return items

    sauce = Sauce.objects.filter(production_date=batch.production_date).first()
    sauce_usage = sauce.usage_for_day if sauce else Decimal('0')
    
    # ✅ GET TOTAL PRODUCTION FOR THE DAY (ALL BATCHES COMBINED)
    total_production_day = Batch.objects.filter(
        production_date=batch.production_date
    ).aggregate(total=Sum('shift_total'))['total'] or 0
    
    # Pre-load snapshots for this batch for efficiency
    snapshots = {
        (s.stock_item_id, s.component_type): s 
        for s in BatchComponentSnapshot.objects.filter(batch=batch)
    }
    
    for ing in product.components.all():
        stock_item = ing.stock_item
        
        cat_name = getattr(getattr(stock_item, "category", None), "name", "").strip().lower()
        subcat_name = getattr(getattr(stock_item, "sub_category", None), "name", "").strip().lower()

        # Use BOTH category and subcategory for auto-calculation
        is_auto_calculated = (
            (cat_name == "concentrate" and subcat_name == "concentrate") or 
            (cat_name == "ingredients" and subcat_name == "starch")
        )

        # ✅ Use snapshot value if available, otherwise fall back to current product component value
        snapshot = snapshots.get((stock_item.id, 'component'))
        if snapshot:
            standard_usage = snapshot.standard_usage_per_production_unit
        else:
            standard_usage = getattr(ing, "standard_usage_per_production_unit", 0)
        
        # ✅ Use total_production_day (not batch.shift_total)
        supposed_usage = total_production_day * standard_usage if total_production_day and standard_usage else 0
        available = getattr(stock_item, "stock_level_display", "-")

        batch_usage = BatchProductInventoryUsed.objects.filter(
            batch=batch,
            stock_item=stock_item
        ).first()
        qty_used = batch_usage.qty_used if batch_usage else ""
        waste_qty = batch_usage.waste_qty if batch_usage else ""
        batch_ref = batch_usage.ref_number if batch_usage else ""

        available_batch_refs = StockTransaction.objects.filter(
            stock_item=stock_item,
            transaction_type='IN'
        ).values_list('batch_ref', flat=True).distinct().exclude(batch_ref='').exclude(batch_ref__isnull=True)

        # Apply auto-calculated value
        if is_auto_calculated:
            qty_used = sauce_usage * Decimal(str(standard_usage))

        items.append({
            "name": stock_item.name,
            "unit_of_measure": getattr(stock_item, "unit_of_measure", ""),
            "available": available,
            "stock_item": stock_item,
            "standard_usage": standard_usage,
            "supposed_usage": supposed_usage,
            "supposed_usage_rounded": math.ceil(supposed_usage) if stock_item.unit_of_measure != "L" else supposed_usage, 
            "qty_used": qty_used,
            "waste_qty": waste_qty,
            "batch_ref": batch_ref,
            "available_batch_refs": list(available_batch_refs),
            "is_concentrate": is_auto_calculated,
        })

    return items

def get_production_usage_data_for_inventory(production_date):
    """Get production usage data for inventory tracking"""
    try:
        batches = Batch.objects.filter(production_date=production_date)
        if not batches.exists():
            return {}
        
        batch = batches.first()
        usage_items = get_product_usage_data(batch)
        
        return {
            'production_date': production_date,
            'batches': list(batches.values('id', 'batch_number')),
            'usage_items': usage_items,
        }
    except Exception as e:
        return {}
        
@staff_member_required
def batch_detail_view(request, batch_id):
    """Simplified batch detail view - used for Summary tab and other focused views"""
    batch = get_object_or_404(Batch, id=batch_id)
    product = batch.product
    
    # ✅ Get dynamic packaging info
    packaging_info = ProductComponent.get_packaging_info(product)
    
    context = {
        'batch': batch,
        'product': product,
        'packaging_info': packaging_info,  # Pass to template
    }
    return render(request, 'batch_detail.html', context)

def record_change(request, batch, field_name, old_value, new_value):
    """
    Unified function to record changes for all tabs.
    Only logs if value actually changed.
    """
    if old_value != new_value:
        log_field_change(request.user, batch, field_name, old_value, new_value)
        return True
    return False

# ============= MAIN VIEW =============

@staff_member_required
@require_http_methods(["GET", "POST"])
def production_batch_detail_view(request, site_slug, production_date):
    """Production batch detail view - renders with CSS/JS injection, NO template file needed"""
    
    # ✅ Get site from URL slug (explicit and unambiguous)
    from tenants.models import Site
    try:
        current_site = Site.objects.get(slug=site_slug)
    except Site.DoesNotExist:
        raise Http404(f"Site '{site_slug}' not found")
    
    # Parse date string YYYYMMDD to date object
    try:
        prod_date = datetime.strptime(production_date, '%Y%m%d').date()
    except ValueError:
        raise Http404("Invalid date format")
    
    # ✅ Get batch from that production date filtered by site from URL
    batches = Batch.objects.filter(production_date=prod_date, site=current_site)
    if not batches.exists():
        raise Http404(f"No batches found for site '{site_slug}' on this date")
    
    batch = batches.first()
    
    # ✅ Get production filtered by site from URL
    production = Production.objects.filter(production_date=prod_date, site=current_site).first()
    if not production:
        raise Http404(f"No production record found for site '{site_slug}' on this date")


    # GET DYNAMIC TAB NAMES
    main_comp = batch.product.main_product_components.select_related('category').first() if batch.product else None
    main_component_category = main_comp.category.name if main_comp and main_comp.category else "Meat"
    
    first_recipe = batch.product.recipes.select_related('recipe_category').first() if batch.product else None
    sauce_tab_name = first_recipe.recipe_category.name if first_recipe and first_recipe.recipe_category else "Sauce"
    
    # ✅ DYNAMICALLY DETERMINE PACKAGING CATEGORY
    # Look at ALL product components (not just main ones) to find packaging category
    packaging_category = None
    packaging_tab_name = "Packaging"
    if batch.product:
        # Get all component categories from ProductComponent relation
        all_component_categories = batch.product.components.values_list(
            'stock_item__category__name', flat=True
        ).distinct()
        
        # Filter out the main component category and empty values
        other_categories = [cat for cat in all_component_categories if cat and cat.lower() != main_component_category.lower()]
        if other_categories:
            # Use the first (and typically only) non-main category as packaging
            packaging_category = other_categories[0]
            packaging_tab_name = packaging_category
    
    pouch_tab_name = "Processing"
    
    
    # ✅ CALL THE UPDATED FUNCTIONS
    sauce_recipe_bookouts = get_sauce_recipe_bookouts(batch, current_site)  # ✅ FIX: was sauce_bookouts
    sauce_recipe_bookouts = filter_sauce_batch_refs_by_flag(sauce_recipe_bookouts)  # ✅ NOW it exists
    sauce_openings = get_sauce_recipe_openings(batch, current_site)
    packaging_data = get_packaging_data(batch, current_site, packaging_category)  # ✅ PASS DYNAMIC CATEGORY
    
    # ============= HANDLE POST =============
    if request.method == 'POST':

        active_tab = request.POST.get('active_tab', 'cert')
        activetab = active_tab

        try:
            with transaction.atomic():

                # CERTIFICATION
                if active_tab == 'cert':

                    # 1) Delete existing NSI docs that were marked with the X
                    delete_ids = request.POST.getlist('delete_nsi_ids[]')
                    if delete_ids:
                        NSIDocument.objects.filter(id__in=delete_ids).delete()
                        log_change(request.user, production, f"Deleted {len(delete_ids)} NSI certificate(s)")

                    # 2) Update batches and save new NSI files
                    # ✅ Filter by site
                    all_batches = Batch.objects.filter(
                        production_date=batch.production_date
                    )
                    if current_site:
                        all_batches = all_batches.filter(site=current_site)
                    all_batches = all_batches.order_by('batch_number')

                    for b in all_batches:
                        # Capture OLD values before updating
                        old_values = {
                            'status': b.status,
                            'incubation_start': b.incubation_start,
                            'incubation_end': b.incubation_end,
                            'nsi_submission': b.nsi_submission_date,
                            'certification': b.certification_date,
                        }
                        
                        # Apply new values
                        b.status = request.POST.get(f'status_{b.batch_number}', b.status)
                        b.incubation_start = (
                            request.POST.get(f'incubation_start_{b.batch_number}') or b.incubation_start
                        )
                        b.incubation_end = (
                            request.POST.get(f'incubation_end_{b.batch_number}') or b.incubation_end
                        )
                        b.nsi_submission_date = (
                            request.POST.get(f'nsi_submission_date_{b.batch_number}') or b.nsi_submission_date
                        )
                        b.certification_date = (
                            request.POST.get(f'certification_date_{b.batch_number}') or b.certification_date
                        )
                        b.save()
                        
                        # Log only actual changes
                        new_values = {
                            'status': b.status,
                            'incubation_start': b.incubation_start,
                            'incubation_end': b.incubation_end,
                            'nsi_submission': b.nsi_submission_date,
                            'certification': b.certification_date,
                        }
                        log_model_changes(request.user, production, b.batch_number, old_values, new_values)
                        
                        # New NSI uploads for this batch
                        nsi_file_key = f'nsi_certificate_{b.batch_number}'
                        files = request.FILES.getlist(nsi_file_key)
                        for f in files:
                            NSIDocument.objects.create(batch=b, file=f)
                            log_change(request.user, production, f"NSI cert uploaded for {b.batch_number}: {f.name}")
                            
                    messages.success(request, '✅ Certification data saved!')

                    
                # MEAT (Per-container dynamic save)
                elif activetab == 'meat':
                    
                    delete_defrost_ids = request.POST.getlist('delete_defrost_ids[]')
                    if delete_defrost_ids:
                        DefrostDocument.objects.filter(id__in=delete_defrost_ids).delete()
                        log_change(request.user, production, f"Deleted {len(delete_defrost_ids)} defrost sheets")
                    
                    # ✅ 1) DELETE marked defrost docs FIRST
                    delete_defrost_ids = request.POST.getlist('delete_defrost_ids[]')
                    if delete_defrost_ids:
                        DefrostDocument.objects.filter(id__in=delete_defrost_ids).delete()
                    
                    container_ids_raw = request.POST.getlist('container_id[]')
                    kg_used_raw = request.POST.getlist('kg_frozen_meat_used[]')
                    filled_raw = request.POST.getlist('meat_filled[]')
                    waste_raw = request.POST.getlist('container_waste[]')
                    waste_factor_raw = request.POST.getlist('waste_factor[]')
                    source_type_raw = request.POST.getlist('source_type[]')
                    book_out_qty_raw = request.POST.getlist('book_out_qty[]')
                    stock_left_raw = request.POST.getlist('stock_left[]')
                    balance_from_prev_shift_raw = request.POST.getlist('balance_from_prev_shift[]')
                    
                    
                    valid_containers = []
                    
                    for idx in range(len(container_ids_raw)):
                        cid = container_ids_raw[idx].strip() if idx < len(container_ids_raw) else None
                        if not cid or not str(cid).strip():
                            continue
                        
                        try:
                            stock_left = float(stock_left_raw[idx]) if idx < len(stock_left_raw) and stock_left_raw[idx] else 0
                            book_out_qty = float(book_out_qty_raw[idx]) if idx < len(book_out_qty_raw) and book_out_qty_raw[idx] else 0
                            waste_factor = float(waste_factor_raw[idx]) if idx < len(waste_factor_raw) and waste_factor_raw[idx] else 0
                            source = source_type_raw[idx] if idx < len(source_type_raw) else 'import'
                            
                            # ✅ Calculate balance_from_prev_shift from PREVIOUS production's stock_left
                            # This ensures the stored value is always correct, not relying on form input
                            balance_from_prev_shift = 0.0
                            if source == 'local':
                                # For local items, lookup by batch_ref
                                # Note: Site filtering not needed here as batch_ref is unique and batch is already site-filtered
                                prev_bc_qs = BatchContainer.objects.filter(
                                    production_date__lt=batch.production_date,
                                    batch_ref=cid
                                )
                                prev_bc = prev_bc_qs.order_by('-production_date').first()
                            else:
                                # For import containers, lookup by container number filtered by site
                                prev_bc_qs = BatchContainer.objects.filter(
                                    production_date__lt=batch.production_date,
                                    container__container_number=cid
                                )
                                if current_site:
                                    prev_bc_qs = prev_bc_qs.filter(container__site=current_site)
                                prev_bc = prev_bc_qs.order_by('-production_date').first()
                            
                            if prev_bc and prev_bc.stock_left:
                                balance_from_prev_shift = float(prev_bc.stock_left)
                            
                            kg_used = balance_from_prev_shift + book_out_qty - stock_left
                            filled = kg_used * (100 - waste_factor) / 100
                            waste = kg_used * waste_factor / 100
                            
                            valid_containers.append({
                                'container_number': cid,
                                'balance_from_prev_shift': balance_from_prev_shift,
                                'kg_used': kg_used,
                                'filled': filled,
                                'waste': waste,
                                'waste_factor': waste_factor,
                                'book_out_qty': book_out_qty,
                                'stock_left': stock_left,
                                'source_type': source,
                            })
                        except (ValueError, TypeError) as e:
                            continue
                    
                    # Check for duplicates
                    container_set = set()
                    for item in valid_containers:
                        if item['container_number'] in container_set:
                            messages.error(request, f'❌ Error: Cannot use the same container twice!')
                            return redirect(f'{request.path}?tab={activetab}')
                        container_set.add(item['container_number'])
                    
                    # ✅ 2) PRESERVE existing DefrostDocuments before deleting containers
                    old_containers = BatchContainer.objects.filter(production_date=batch.production_date)
                    preserved_defrost = {}  # key: container_number, value: list of file paths
                    
                    # ✅ CAPTURE OLD container values for change detection
                    old_container_data = {}
                    for old_bc in old_containers:
                        key = old_bc.container.container_number if old_bc.container else old_bc.batch_ref
                        if key:
                            old_container_data[key] = {
                                'stock_left': float(old_bc.stock_left) if old_bc.stock_left else 0,
                                'book_out_qty': float(old_bc.book_out_qty) if old_bc.book_out_qty else 0,
                                'kg_used': float(old_bc.kg_frozen_meat_used) if old_bc.kg_frozen_meat_used else 0,
                            }
                            docs = old_bc.defrost_documents.all()
                            if docs.exists():
                                preserved_defrost[key] = [doc.file for doc in docs]
                    
                    
                    # ✅ 3) NOW delete old containers (cascade-deletes DefrostDocuments)
                    BatchContainer.objects.filter(production_date=batch.production_date).delete()
                    
                    # ✅ 4) CREATE new containers and restore + add defrost docs
                    created_count = 0
                    
                    for idx, item in enumerate(valid_containers):
                        try:
                            if item['source_type'] == 'local':
                                bc = BatchContainer.objects.create(
                                    production_date=batch.production_date,
                                    container=None,
                                    batch_ref=item['container_number'],
                                    balance_from_prev_shift=Decimal(str(item['balance_from_prev_shift'])),
                                    kg_frozen_meat_used=Decimal(str(item['kg_used'])),
                                    meat_filled=Decimal(str(item['filled'])),
                                    container_waste=Decimal(str(item['waste'])),
                                    waste_factor=Decimal(str(item['waste_factor'])),
                                    book_out_qty=Decimal(str(item['book_out_qty'])),
                                    stock_left=Decimal(str(item['stock_left'])),
                                    source_type='local',
                                )
                            else:
                                # ✅ Get container filtered by site
                                container_qs = Container.objects.filter(container_number=item['container_number'])
                                if current_site:
                                    container_qs = container_qs.filter(site=current_site)
                                container = container_qs.first()
                                if not container:
                                    continue  # Skip if container not found or not in current site
                                
                                bc = BatchContainer.objects.create(
                                    production_date=batch.production_date,
                                    container=container,
                                    balance_from_prev_shift=Decimal(str(item['balance_from_prev_shift'])),
                                    kg_frozen_meat_used=Decimal(str(item['kg_used'])),
                                    meat_filled=Decimal(str(item['filled'])),
                                    container_waste=Decimal(str(item['waste'])),
                                    waste_factor=Decimal(str(item['waste_factor'])),
                                    book_out_qty=Decimal(str(item['book_out_qty'])),
                                    stock_left=Decimal(str(item['stock_left'])),
                                    batch_ref=None,
                                    source_type='import',
                                )
                            
                            created_count += 1
                            
                            # ✅ LOG CONTAINER CHANGES (only if stock_left changed)
                            container_key = item['container_number']
                            old_data = old_container_data.get(container_key, {})
                            new_stock_left = item['stock_left']
                            old_stock_left = old_data.get('stock_left', 0)
                            
                            if normalize_value(old_stock_left) != normalize_value(new_stock_left):
                                if old_stock_left:
                                    log_change(request.user, production, f"{container_key}: stock_left: {old_stock_left}kg → {new_stock_left}kg")
                                else:
                                    log_change(request.user, production, f"{container_key}: stock_left: {new_stock_left}kg")
                            
                            # Log restored defrost docs
                            if container_key in preserved_defrost:
                                for old_file in preserved_defrost[container_key]:
                                    DefrostDocument.objects.create(batch_container=bc, file=old_file)
                            
                            # Log new defrost uploads
                            defrost_key = f'defrost_sheet_{idx}[]'
                            # ✅ Allow container creation to fail silently if container not found or not in current site
                            new_files = request.FILES.getlist(defrost_key)
                            for f in new_files:
                                DefrostDocument.objects.create(batch_container=bc, file=f)
                                log_change(request.user, production, f"{container_key}: Defrost sheet → {f.name}")

                        except Container.DoesNotExist:
                            continue
                        except Exception as e:
                            import traceback
                            traceback.print_exc()
                            continue
                    
                    if created_count > 0:
                        messages.success(request, f'✅ Saved {created_count} containers!')
                    else:
                        messages.warning(request, '⚠️ No valid containers to save')
                    
                    # ✅ MEAT SUMMARY (unchanged)
                    try:
                        total_meat_filled_str = request.POST.get('total_meat_filled', '').strip()
                        total_waste_str = request.POST.get('total_waste', '0').strip()
                        filling_weight_str = request.POST.get('filling_weight_per_pouch', '').strip()
                        
                        if not total_meat_filled_str or float(total_meat_filled_str) == 0:
                            messages.error(request, '❌ Total Meat Filled is REQUIRED!')
                            return redirect(f"{request.path}?tab=meat")
                        
                        meat_summary, _ = MeatProductionSummary.objects.get_or_create(
                            production_date=batch.production_date,
                            site=current_site
                        )
                        # Capture OLD values
                        old_meat = {
                            'total_filled': f"{meat_summary.total_meat_filled}kg" if meat_summary.total_meat_filled else '',
                            'total_waste': f"{meat_summary.total_waste}kg" if meat_summary.total_waste else '',
                            'filling_weight': f"{meat_summary.filling_weight_per_pouch}kg/pouch" if meat_summary.filling_weight_per_pouch else '',
                        }
                        
                        meat_summary.total_meat_filled = Decimal(total_meat_filled_str)
                        meat_summary.total_waste = Decimal(total_waste_str) if total_waste_str else Decimal('0')
                        
                        if filling_weight_str:
                            meat_summary.filling_weight_per_pouch = Decimal(filling_weight_str)
                        
                        if 'filling_weight_sheet' in request.FILES:
                            meat_summary.filling_weight_sheet = request.FILES['filling_weight_sheet']
                            log_change(request.user, production, f"Meat summary: Filling weight sheet uploaded")
                        
                        meat_summary.save()
                        
                        # Log only changes
                        new_meat = {
                            'total_filled': f"{meat_summary.total_meat_filled}kg",
                            'total_waste': f"{meat_summary.total_waste}kg",
                            'filling_weight': f"{meat_summary.filling_weight_per_pouch}kg/pouch" if meat_summary.filling_weight_per_pouch else '',
                        }
                        log_model_changes(request.user, production, "Meat summary", old_meat, new_meat)
                        
                        messages.success(request, '✅ Meat Summary saved!')
                        return redirect(f"{request.path}?tab={active_tab}")
                        
                    except Exception as e:
                        messages.error(request, f'❌ Error: {e}')
                
                # Sauce Tab
                elif active_tab == 'sauce':
                    
                    
                    # ✅ PART 1: SAVE RECIPE STOCK ITEM BALANCES (LEFT CARDS)
                    all_recipe_stock_items = {
                        item.stock_item.id: item.stock_item 
                        for item in ProductRecipeItem.objects.filter(
                            recipe__product=batch.product
                        ).select_related('stock_item')
                    }
                    
                    
                    # ✅ ITERATE ALL RECIPE ITEMS, DON'T SKIP ZEROS
                    for stock_item_id, stock_item in all_recipe_stock_items.items():
                        closing_balance_str = request.POST.get(f'sauce_closing_{stock_item_id}', '0').strip()
                        
                        try:
                            reason = request.POST.get(f'sauce_reason_{stock_item_id}', '').strip()
                            cancel_checkbox = request.POST.get(f'sauce_cancel_{stock_item_id}') == 'on'
                            batch_ref = request.POST.get(f'sauce_batch_ref_{stock_item_id}', '').strip()
                            booked_qty = Decimal(request.POST.get(f'sauce_booked_{stock_item_id}', 0) or 0)
                            opening_balance = Decimal(request.POST.get(f'sauce_opening_{stock_item_id}', 0) or 0)
                            closing_balance = Decimal(closing_balance_str or 0)
                            
                            # ✅ NEW: Auto-detect batch_ref type
                            batch_ref_type = get_batch_ref_type(batch_ref, stock_item)
                            
                            
                            # ✅ CAPTURE OLD VALUES for change detection
                            old_recipe_item = RecipeStockItemBalance.objects.filter(
                                production_date=batch.production_date,
                                stock_item=stock_item
                            ).first()
                            old_recipe = {
                                'opening': f"{old_recipe_item.opening_balance}L" if old_recipe_item and old_recipe_item.opening_balance else '',
                                'closing': f"{old_recipe_item.closing_balance}L" if old_recipe_item and old_recipe_item.closing_balance else '',
                                'cancel': old_recipe_item.cancel_opening_use_bookout if old_recipe_item else False,
                                'reason': old_recipe_item.amended_reason if old_recipe_item else '',
                            } if old_recipe_item else {'opening': '', 'closing': '', 'cancel': False, 'reason': ''}
                            
                            # ✅✅✅ DELETE OLD ROWS BEFORE UPDATE (CRITICAL FIX!)
                            RecipeStockItemBalance.objects.filter(
                                production_date=batch.production_date,
                                stock_item=stock_item
                            ).exclude(batch_ref=batch_ref, batch_ref_type=batch_ref_type).delete()
                            
                            # ✅ UPDATED: Include batch_ref_type and batch_ref
                            RecipeStockItemBalance.objects.update_or_create(
                                production_date=batch.production_date,
                                stock_item=stock_item,
                                batch_ref_type=batch_ref_type,
                                batch_ref=batch_ref,
                                defaults={
                                    'opening_balance': opening_balance,
                                    'booked_out_stock': booked_qty,
                                    'closing_balance': closing_balance,
                                    'amended_reason': reason,
                                    'cancel_opening_use_bookout': cancel_checkbox,
                                }
                            )
                            
                            # ✅ LOG CHANGES for recipe item
                            new_recipe = {
                                'opening': f"{opening_balance}L",
                                'closing': f"{closing_balance}L",
                                'cancel': cancel_checkbox,
                                'reason': reason,
                            }
                            log_model_changes(request.user, production, f"Sauce {stock_item.name}", old_recipe, new_recipe)
                                        
                        except Exception as e:
                            import traceback
                            traceback.print_exc()
                    
                    # ✅ PART 2: SAVE SAUCE SUMMARY (RIGHT CARD)
                    sauce, _ = Sauce.objects.get_or_create(
                        production_date=batch.production_date,
                        defaults={}
                    )
                    # Capture OLD values
                    old_sauce = {
                        'opening': f"{sauce.opening_balance}L" if sauce.opening_balance else '',
                        'mixed': f"{sauce.sauce_mixed}L" if sauce.sauce_mixed else '',
                        'closing': f"{sauce.closing_balance}L" if sauce.closing_balance else '',
                        'cancel_opening': sauce.cancel_opening_balance,
                        'reason': sauce.amended_reason or '',
                    }
                    
                    sauce.opening_balance = Decimal(request.POST.get('opening_balance') or 0)
                    sauce.amended_opening_balance = Decimal(request.POST.get('amended_opening_balance') or 0) if request.POST.get('amended_opening_balance') else None
                    sauce.amended_reason = request.POST.get('amended_reason') or ''
                    sauce.sauce_mixed = Decimal(request.POST.get('sauce_mixed') or 0)
                    sauce.closing_balance = Decimal(request.POST.get('closing_balance') or 0)
                    sauce.cancel_opening_balance = request.POST.get('cancel_opening_balance') == 'on'

                    if 'reference_file' in request.FILES:
                        sauce.reference_file = request.FILES['reference_file']
                        log_change(request.user, production, f"Sauce: Reference file → {request.FILES['reference_file'].name}")
                        
                    delete_recipe_ids = request.POST.getlist('delete_recipe_ids[]')
                    if delete_recipe_ids:
                        current_docs = sauce.recipe_documents if sauce.recipe_documents else []
                        sauce.recipe_documents = [
                            d for d in current_docs 
                            if str(d.get('id')) not in delete_recipe_ids
                        ]
                        log_change(request.user, production, f"Deleted {len(delete_recipe_ids)} recipe docs")

                    # Handle new recipe document uploads
                    recipe_files = request.FILES.getlist('recipe_documents[]')

                    if recipe_files:
                        import uuid
                        from django.core.files.storage import default_storage
                        
                        current_docs = sauce.recipe_documents if sauce.recipe_documents else []
                        
                        for f in recipe_files:
                            file_path = default_storage.save(f'recipe_docs/{f.name}', f)
                            current_docs.append({
                                'id': str(uuid.uuid4()),
                                'file': file_path,
                                'filename': f.name,
                            })
                            log_change(request.user, production, f"Sauce: Recipe doc → {f.name}")
                        
                        sauce.recipe_documents = current_docs
                    
                    # ✅ Handle Inventory Book Out Documents (for sauce items)
                    pouch_waste, _ = Waste.objects.get_or_create(batch=batch, defaults={'production_date': batch.production_date})

                    inventory_docs = pouch_waste.inventory_book_out_documents if pouch_waste.inventory_book_out_documents else {}

                    for stock_item_id in all_recipe_stock_items.keys():
                        # Handle deletions
                        delete_ids = request.POST.getlist(f'delete_inventory_bookout_{stock_item_id}[]')
                        if delete_ids:
                            if str(stock_item_id) in inventory_docs:
                                inventory_docs[str(stock_item_id)] = [
                                    d for d in inventory_docs[str(stock_item_id)]
                                    if str(d.get('id')) not in delete_ids
                                ]
                                item_name = all_recipe_stock_items[stock_item_id].name
                                log_change(request.user, production, f"Sauce {item_name}: Deleted {len(delete_ids)} book-out docs")
                
                                
                        # Handle uploads
                        files = request.FILES.getlist(f'inventory_bookout_{stock_item_id}[]')
                        if files:
                            import uuid
                            from django.core.files.storage import default_storage
                            
                            if str(stock_item_id) not in inventory_docs:
                                inventory_docs[str(stock_item_id)] = []
                            
                            for f in files:
                                file_path = default_storage.save(f'inventory_bookout/{f.name}', f)
                                inventory_docs[str(stock_item_id)].append({
                                    'id': str(uuid.uuid4()),
                                    'file': file_path,
                                    'filename': f.name,
                                })
                                item_name = all_recipe_stock_items[stock_item_id].name
                                log_change(request.user, production, f"Sauce {item_name}: Book-out doc → {f.name}")
                
                    pouch_waste.inventory_book_out_documents = inventory_docs
                    pouch_waste.save()

                    sauce.save()
                    
                    # ✅ LOG SAUCE SUMMARY (only if changed)
                    new_sauce = {
                        'opening': f"{sauce.opening_balance}L",
                        'mixed': f"{sauce.sauce_mixed}L",
                        'closing': f"{sauce.closing_balance}L",
                        'cancel_opening': sauce.cancel_opening_balance,
                        'reason': sauce.amended_reason or '',
                    }
                    log_model_changes(request.user, production, "Sauce summary", old_sauce, new_sauce)
                    
                    messages.success(request, '✅ Sauce data saved!')
                    return redirect(f"{request.path}?tab={active_tab}")

                # PRODUCT
                elif active_tab == 'product':
                    usage_items = get_product_usage_data(batch)
                    inventory_batch_refs = {}  # ✅ Collect inventory batch refs
                    
                    # First, save BatchProductInventoryUsed items
                    for item in usage_items:
                        stock_id = item['stock_item'].id
                        qty_used = float(request.POST.get(f'qty_used_{stock_id}') or 0)
                        waste_qty = float(request.POST.get(f'waste_qty_{stock_id}') or 0)
                        batch_ref = request.POST.get(f'batch_ref_{stock_id}') or ''
                        
                        BatchProductInventoryUsed.objects.update_or_create(
                            batch=batch,
                            stock_item=item['stock_item'],
                            defaults={
                                'product': batch.product,
                                'qty_used': Decimal(str(qty_used)),
                                'waste_qty': Decimal(str(waste_qty)),
                                'ref_number': batch_ref,
                            }
                        )
                        
                        # ✅ SAVE the inventory batch ref for later use
                        if batch_ref:
                            inventory_batch_refs[stock_id] = batch_ref
                    
                    # Delete old stock transactions
                    deleted_count = StockTransaction.objects.filter(
                        batch=batch,
                        transaction_type='OUT',
                        transaction_date=batch.production_date
                    ).count()
                    
                    StockTransaction.objects.filter(
                        batch=batch,
                        transaction_type='OUT',
                        transaction_date=batch.production_date
                    ).delete()
                    
                    # Calculate totals
                    total_production_day = Batch.objects.filter(
                        production_date=batch.production_date
                    ).aggregate(total=Sum('shift_total'))['total'] or 0

                    sauce = Sauce.objects.filter(production_date=batch.production_date).first()
                    sauce_usage_for_day = sauce.usage_for_day if sauce else Decimal('0')

                    packaging_balances = {
                        pb.stock_item.id: pb
                        for pb in PackagingBalance.objects.filter(production_date=batch.production_date)
                    }

                    all_components = ProductComponent.objects.filter(
                        product=batch.product
                    ).select_related('stock_item', 'stock_item__category')
                    
                    booking_out_data = {}
                    for comp in all_components:
                        stock_item = comp.stock_item
                        total_out = StockTransaction.objects.filter(
                            stock_item=stock_item,
                            transaction_type='OUT'
                        ).aggregate(sum=Sum('quantity'))['sum'] or Decimal('0')
                        booking_out_data[stock_item.id] = total_out

                    usage_items_summary = []
                    for comp in all_components:
                        stock_item = comp.stock_item
                        category_name = getattr(getattr(stock_item, "category", None), "name", "").strip().lower()
                        
                        standard_usage = comp.standard_usage_per_production_unit or Decimal('0')
                        supposed_usage = total_production_day * standard_usage if total_production_day and standard_usage else Decimal('0')
                        
                        if category_name == 'packing':
                            pb = packaging_balances.get(stock_item.id)
                            if pb:
                                booked = booking_out_data.get(stock_item.id, Decimal('0'))
                                balance = pb.closing_balance or Decimal('0')
                                usage_for_day = booked - balance
                            else:
                                usage_for_day = Decimal('0')
                        
                        elif category_name == 'liver':
                            continue
                        
                        elif category_name in ['concentrate', 'ingredients']:
                            usage_for_day = sauce_usage_for_day * standard_usage
                        
                        else:
                            usage_for_day = booking_out_data.get(stock_item.id, Decimal('0'))
                        
                        if usage_for_day and usage_for_day != 0:
                            usage_items_summary.append({
                                'stock_item': stock_item,
                                'qty': usage_for_day,
                                'reason': packaging_balances.get(stock_item.id).amended_reason if packaging_balances.get(stock_item.id) else '',
                            })

                    batches_today = Batch.objects.filter(production_date=batch.production_date)

                    created_count = 0
                    for item_data in usage_items_summary:
                        try:
                            stock_item = item_data['stock_item']
                            
                            # ✅ USE INVENTORY BATCH REF ONLY - never use manufacturing batch refs
                            batch_ref_for_item = inventory_batch_refs.get(stock_item.id, '')
                            
                            st = StockTransaction.objects.create(
                                category=stock_item.category,
                                stock_item=stock_item,
                                batch=batch,
                                batch_ref=batch_ref_for_item,
                                quantity=item_data['qty'],
                                transaction_type='OUT',
                                transaction_date=batch.production_date,
                                usage_notes=item_data['reason'],
                            )
                            created_count += 1
                            
                        except Exception as e:
                            import traceback
                            traceback.print_exc()
                    
                    messages.success(request, f'✅ Product usage saved! Created {created_count} Stock Transactions.')

                # DOWN TIME
                elif active_tab == 'downtime':
                    pouch_waste, _ = Waste.objects.get_or_create(
                        batch=batch,
                        defaults={'production_date': batch.production_date}
                    )
                    # Capture OLD values
                    old_downtime = {
                        'minutes': str(pouch_waste.total_down_time) if pouch_waste.total_down_time else '',
                        'reason': pouch_waste.reasons_for_down_time or '',
                    }
                    
                    pouch_waste.total_down_time = Decimal(request.POST.get('total_down_time') or 0)
                    pouch_waste.reasons_for_down_time = request.POST.get('reasons_for_down_time') or ''
                    
                    pouch_waste.save()
                    
                    # Log only changes
                    new_downtime = {
                        'minutes': str(pouch_waste.total_down_time),
                        'reason': pouch_waste.reasons_for_down_time or '',
                    }
                    log_model_changes(request.user, production, "Down time", old_downtime, new_downtime)
                    messages.success(request, '✅ Down Time data saved!')
                
                # Packaging
                elif active_tab == 'packaging':
                    
                    # Use dynamic packaging_category instead of hardcoded 'Packing'
                    if packaging_category:
                        all_packaging_items = {item.id: item for item in StockItem.objects.filter(category__name__iexact=packaging_category)}
                    else:
                        all_packaging_items = {item.id: item for item in StockItem.objects.filter(category__name__iexact='Packing')}
                    
                    for key, closing_balance_str in request.POST.items():
                        if not key.startswith('pkg_closing_'):
                            continue
                        
                        stock_item_id = int(key.replace('pkg_closing_', ''))
                        closing_balance_str = closing_balance_str.strip()
                        
                        if not closing_balance_str or closing_balance_str in ['0', '0.00']:
                            continue
                        
                        try:
                            item = all_packaging_items[stock_item_id]
                            reason = request.POST.get(f'pkg_reason_{stock_item_id}', '').strip()
                            cancel_checkbox = request.POST.get(f'pkg_cancel_{stock_item_id}') == 'on'
                            booked_qty = Decimal(request.POST.get(f'pkg_booked_{stock_item_id}', 0) or 0)
                            opening_balance = Decimal(request.POST.get(f'pkg_opening_{stock_item_id}', 0) or 0)
                            closing_balance = Decimal(closing_balance_str)
                            
                            # ✅ REBUILD batch_ref fresh from DB (don't read from form like sauce)
                            previous_packaging = PackagingBalance.objects.filter(
                                stock_item=item,
                                production_date__lt=batch.production_date
                            ).order_by('-production_date').first()
                            batch_ref_balance = previous_packaging.batch_ref if previous_packaging else ''
                            
                            import re
                            if batch_ref_balance:
                                # Check if it contains production batch pattern like "A00825CH02A"
                                if re.search(r'[A-Z]\d{5}CH\d{2}[A-Z]', batch_ref_balance):
                                    batch_ref_balance = ''
                                # If it's a combined ref like "A00825CH02A / Toets 2 Pallet", only take the part after /
                                elif ' / ' in batch_ref_balance:
                                    parts = batch_ref_balance.split(' / ')
                                    # Use the second part if the first part is a production batch
                                    if re.search(r'[A-Z]\d{5}CH\d{2}[A-Z]', parts[0].strip()):
                                        batch_ref_balance = parts[1].strip() if len(parts) > 1 else ''
                                        
                            previous_prod = Batch.objects.filter(
                                production_date__lt=batch.production_date,
                                product=batch.product
                            ).order_by('-production_date').first()
                            
                            if previous_prod:
                                all_bookouts = StockTransaction.objects.filter(
                                    stock_item=item,
                                    transaction_type='OUT',
                                    transaction_date__gt=previous_prod.production_date,
                                    transaction_date__lte=batch.production_date
                                ).order_by('-transaction_date')
                            else:
                                all_bookouts = StockTransaction.objects.filter(
                                    stock_item=item,
                                    transaction_type='OUT',
                                    transaction_date__lte=batch.production_date
                                ).order_by('-transaction_date')
                            
                            latest_unused = all_bookouts.first() if all_bookouts.exists() else None
                            batch_ref_booked_val = latest_unused.batch_ref.split(',')[0].strip() if latest_unused and latest_unused.batch_ref else ''
                            # ✅ COMBINE batch_ref with " / " if both exist
                            if batch_ref_balance and batch_ref_booked_val and batch_ref_balance != batch_ref_booked_val:
                                # Both exist and different - combine them
                                batch_ref = f"{batch_ref_balance} / {batch_ref_booked_val}"
                            elif batch_ref_booked_val:
                                # Only booked exists
                                batch_ref = batch_ref_booked_val
                            elif batch_ref_balance:
                                # Only balance exists
                                batch_ref = batch_ref_balance
                            else:
                                # Neither exists
                                batch_ref = ''
                            
                            # ✅ NEW: Auto-detect batch_ref type
                            batch_ref_type = get_batch_ref_type(batch_ref, item)
                            
                            
                            # ✅ CAPTURE OLD VALUES for change detection
                            old_pkg_item = PackagingBalance.objects.filter(
                                production_date=batch.production_date,
                                stock_item=item
                            ).first()
                            old_pkg = {
                                'opening': f"{old_pkg_item.opening_balance}" if old_pkg_item and old_pkg_item.opening_balance else '',
                                'closing': f"{old_pkg_item.closing_balance}" if old_pkg_item and old_pkg_item.closing_balance else '',
                                'cancel': old_pkg_item.cancel_opening_use_bookout if old_pkg_item else False,
                                'reason': old_pkg_item.amended_reason if old_pkg_item else '',
                            } if old_pkg_item else {'opening': '', 'closing': '', 'cancel': False, 'reason': ''}
                            
                            # ✅✅✅ DELETE OLD ROWS BEFORE UPDATE
                            PackagingBalance.objects.filter(
                                production_date=batch.production_date,
                                stock_item=item
                            ).exclude(batch_ref=batch_ref, batch_ref_type=batch_ref_type).delete()
                            
                            # ✅ Save
                            PackagingBalance.objects.update_or_create(
                                production_date=batch.production_date,
                                stock_item=item,
                                batch_ref_type=batch_ref_type,
                                batch_ref=batch_ref,
                                defaults={
                                    'opening_balance': opening_balance,
                                    'booked_out_stock': booked_qty,
                                    'closing_balance': closing_balance,
                                    'amended_reason': reason,
                                    'cancel_opening_use_bookout': cancel_checkbox,
                                }
                            )
                            
                            # ✅ LOG CHANGES for packaging item
                            new_pkg = {
                                'opening': f"{opening_balance}",
                                'closing': f"{closing_balance}",
                                'cancel': cancel_checkbox,
                                'reason': reason,
                            }
                            log_model_changes(request.user, production, f"Packaging {item.name}", old_pkg, new_pkg)
                                            
                        except (ValueError, KeyError) as e:
                            import traceback
                            traceback.print_exc()
                    
                    # ✅ Handle Final Product Packaging Documents (multiple files)
                    pouch_waste, _ = Waste.objects.get_or_create(batch=batch, defaults={'production_date': batch.production_date})

                    delete_final_packaging_ids = request.POST.getlist('delete_final_packaging_ids[]')
                    if delete_final_packaging_ids:
                        current_docs = pouch_waste.final_product_packaging_documents if pouch_waste.final_product_packaging_documents else []
                        pouch_waste.final_product_packaging_documents = [
                            d for d in current_docs 
                            if str(d.get('id')) not in delete_final_packaging_ids
                        ]
                        log_change(request.user, production, f"Deleted {len(delete_final_packaging_ids)} final packaging docs")

                    final_packaging_files = request.FILES.getlist('final_packaging_documents[]')

                    if final_packaging_files:
                        import uuid
                        from django.core.files.storage import default_storage
                        
                        current_docs = pouch_waste.final_product_packaging_documents if pouch_waste.final_product_packaging_documents else []
                        
                        for f in final_packaging_files:
                            file_path = default_storage.save(f'final_packaging/{f.name}', f)
                            current_docs.append({
                                'id': str(uuid.uuid4()),
                                'file': file_path,
                                'filename': f.name,
                            })
                        
                        pouch_waste.final_product_packaging_documents = current_docs
   
                    # ✅ Handle Inventory Book Out Documents (for packaging items)
                    pouch_waste, _ = Waste.objects.get_or_create(batch=batch, defaults={'production_date': batch.production_date})

                    inventory_docs = pouch_waste.inventory_book_out_documents if pouch_waste.inventory_book_out_documents else {}

                    for stock_item_id in all_packaging_items.keys():
                        item_name = all_packaging_items[stock_item_id].name
                        
                        # Handle deletions
                        delete_ids = request.POST.getlist(f'delete_inventory_bookout_{stock_item_id}[]')
                        if delete_ids:
                            if str(stock_item_id) in inventory_docs:
                                inventory_docs[str(stock_item_id)] = [
                                    d for d in inventory_docs[str(stock_item_id)]
                                    if str(d.get('id')) not in delete_ids
                                ]
                                log_change(request.user, production, f"Packaging {item_name}: Deleted {len(delete_ids)} book-out docs")
                        
                        # Handle uploads
                        files = request.FILES.getlist(f'inventory_bookout_{stock_item_id}[]')
                        if files:
                            import uuid
                            from django.core.files.storage import default_storage
                            
                            if str(stock_item_id) not in inventory_docs:
                                inventory_docs[str(stock_item_id)] = []
                            
                            for f in files:
                                file_path = default_storage.save(f'inventory_bookout/{f.name}', f)
                                inventory_docs[str(stock_item_id)].append({
                                    'id': str(uuid.uuid4()),
                                    'file': file_path,
                                    'filename': f.name,
                                })
                                log_change(request.user, production, f"Packaging {item_name}: Book-out doc → {f.name}")

                    pouch_waste.inventory_book_out_documents = inventory_docs
                    pouch_waste.save()
                    messages.success(request, '✅ Packaging data saved!')
                    return redirect(f"{request.path}?tab={active_tab}")

                # ===== SAVE PRODUCTION SUMMARY TAB =====
                elif active_tab == 'summary':
                    from manufacturing.models import ProductionSummaryItem, BatchComponentSnapshot
                    
                    # ✅ USE MAIN PRODUCTION QTY (Shift Totals), NOT JS 23916
                    total_pouches = (
                        Batch.objects.filter(production_date=batch.production_date)
                        .aggregate(total=Sum('shift_total'))['total'] or 0
                    )
                    
                    # Pre-load snapshots for this batch for efficiency
                    snapshots = {
                        (s.stock_item_id, s.component_type): s 
                        for s in BatchComponentSnapshot.objects.filter(batch=batch)
                    }
                                                                   
                    # Get all summary items from POST
                    summary_items_to_create = []
                    
                    # Iterate through all form fields that start with "summary"
                    for key, value in request.POST.items():
                        if key.startswith('summaryideal_'):
                            stock_item_id = key.replace('summaryideal_', '')
                            ideal_str = value.strip() or '0'
                            used_str = request.POST.get(f'summaryused_{stock_item_id}', '0').strip() or '0'
                            batchref = request.POST.get(f'summarybatchref_{stock_item_id}', '').strip()

                            try:
                                used = Decimal(used_str)

                                # 1) Get stock_item
                                try:
                                    stock_item = StockItem.objects.get(id=stock_item_id)
                                except StockItem.DoesNotExist:
                                    continue

                                # 2) Component type (model choices)
                                if 'main' in key:
                                    component_type = 'main'
                                elif 'comp' in key:
                                    component_type = 'component'
                                elif 'recipe' in key:
                                    component_type = 'recipe'
                                else:
                                    component_type = 'component'

                                # 3) std_usage - Use snapshot if available, otherwise from Product Details
                                std_usage = Decimal('0')
                                
                                # First try to get from snapshot
                                snapshot = snapshots.get((int(stock_item_id), component_type))
                                if snapshot:
                                    std_usage = snapshot.standard_usage_per_production_unit
                                else:
                                    # Fall back to current product detail values
                                    if component_type == 'main':
                                        from product_details.models import MainProductComponent
                                        comp = MainProductComponent.objects.filter(
                                            product=batch.product,
                                            stock_item=stock_item,
                                        ).first()
                                        if comp and comp.standard_usage_per_production_unit is not None:
                                            std_usage = comp.standard_usage_per_production_unit

                                    elif component_type == 'component':
                                        comp = ProductComponent.objects.filter(
                                            product=batch.product,
                                            stock_item=stock_item,
                                        ).first()
                                        if comp and comp.standard_usage_per_production_unit is not None:
                                            std_usage = comp.standard_usage_per_production_unit

                                    elif component_type == 'recipe':
                                        rec_item = ProductRecipeItem.objects.filter(
                                            recipe__product=batch.product,
                                            stock_item=stock_item,
                                        ).first()
                                        if rec_item and rec_item.standard_usage_per_production_unit is not None:
                                            std_usage = rec_item.standard_usage_per_production_unit

                                # 4) ✅ IDEAL = 24000 (from Batch) × usage per unit
                                ideal = Decimal(total_pouches) * (std_usage or Decimal('0'))
                                difference = ideal - used

                                summary_items_to_create.append({
                                    'stock_item': stock_item,
                                    'component_type': component_type,
                                    'ideal': ideal,
                                    'used': used,
                                    'difference': difference,
                                    'batch_ref': batchref,
                                })


                            except (ValueError, TypeError, Decimal.InvalidOperation) as e:
                                continue

                    
                    # Delete old records for this production date
                    old_count = ProductionSummaryItem.objects.filter(
                        production_date=batch.production_date.production_date
                    ).delete()[0]
                    
                    # Create all new records in batch
                    created_count = 0
                    for item_data in summary_items_to_create:
                        try:
                            ProductionSummaryItem.objects.create(
                                production_date=batch.production_date.production_date,
                                stock_item=item_data['stock_item'],
                                component_type=item_data['component_type'],
                                ideal=item_data['ideal'],
                                used=item_data['used'],
                                difference=item_data['difference'],
                                batch_ref=item_data['batch_ref'],
                            )
                            created_count += 1
                        except Exception as e:
                            import traceback
                            traceback.print_exc()
                    
                    if created_count > 0:
                        messages.success(request, f"✅ Production summary saved! Created {created_count} summary items.")
                        log_change(request.user, production, f"Summary: Created {created_count} items")
                    else:
                        messages.warning(request, "⚠️  No summary items to save.")

                                        
                # POUCH
                elif active_tab == 'processing':
                    pouch_waste, _ = Waste.objects.get_or_create(
                        batch=batch,
                        defaults={'production_date': batch.production_date}
                    )
                    # Capture OLD values for change detection
                    old_machine = {
                        'count': pouch_waste.machine_count,
                        'seal_creeps': pouch_waste.seal_creeps,
                        'unsealed': pouch_waste.unsealed_poor_seal,
                        'screwed': pouch_waste.screwed_and_undated,
                        'overweight': pouch_waste.over_weight,
                        'underweight': pouch_waste.under_weight,
                        'empty': pouch_waste.empty_pouches,
                        'metal': pouch_waste.metal_detection,
                    }
                    old_retort = {
                        'count': pouch_waste.retort_count,
                        'unclear': pouch_waste.total_unclear_coding,
                        'seal_creap': pouch_waste.retort_seal_creap,
                        'underweight': pouch_waste.retort_under_weight,
                        'poor_ceiling': pouch_waste.poor_ceiling_destroyed,
                    }
                    old_samples = {b.batch_number: {
                        'nsi': (pouch_waste.nsi_sample_per_batch or {}).get(b.batch_number, 0),
                        'retention': (pouch_waste.retention_sample_per_batch or {}).get(b.batch_number, 0),
                        'unclear': (pouch_waste.unclear_coding_per_batch or {}).get(b.batch_number, 0),
                    } for b in Batch.objects.filter(production_date=batch.production_date)}
                    
                    pouch_waste.machine_count = int(request.POST.get('machine_count') or 0)
                    pouch_waste.seal_creeps = int(request.POST.get('seal_creeps') or 0)
                    pouch_waste.metal_detection = int(request.POST.get('metal_detection') or 0)
                    pouch_waste.unsealed_poor_seal = int(request.POST.get('unsealed_poor_seal') or 0)
                    pouch_waste.screwed_and_undated = int(request.POST.get('screwed_and_undated') or 0)
                    pouch_waste.over_weight = int(request.POST.get('over_weight') or 0)
                    pouch_waste.under_weight = int(request.POST.get('under_weight') or 0)
                    pouch_waste.empty_pouches = int(request.POST.get('empty_pouches') or 0)
                    pouch_waste.retort_count = int(request.POST.get('retort_count') or 0)
                    pouch_waste.total_unclear_coding = int(request.POST.get('total_unclear_coding') or 0)
                    pouch_waste.retort_seal_creap = int(request.POST.get('retort_seal_creap') or 0)
                    pouch_waste.retort_under_weight = int(request.POST.get('retort_under_weight') or 0)
                    pouch_waste.poor_ceiling_destroyed = int(request.POST.get('poor_ceiling_destroyed') or 0)
                    pouch_waste.pouches_withdrawn = int(request.POST.get('pouches_withdrawn') or 0)
                    pouch_waste.packed = int(request.POST.get('packed') or 0)
                    
                    # Collect all per-batch data in ONE loop
                    total_nsi = 0
                    total_retention = 0
                    nsi_per_batch_dict = {}
                    retention_per_batch_dict = {}
                    unclear_per_batch_dict = {}

                    # ✅ Filter batches by site
                    all_batches = Batch.objects.filter(production_date=batch.production_date)
                    if current_site:
                        all_batches = all_batches.filter(site=current_site)
                    
                    for b in all_batches:
                        nsi_val = int(request.POST.get(f'nsi_sample_pouches_{b.batch_number}') or 0)
                        retention_val = int(request.POST.get(f'retention_sample_qty_{b.batch_number}') or 0)
                        unclear_val = int(request.POST.get(f'unclear_coding_{b.batch_number}') or 0)
                        
                        total_nsi += nsi_val
                        total_retention += retention_val
                        
                        nsi_per_batch_dict[b.batch_number] = nsi_val
                        retention_per_batch_dict[b.batch_number] = retention_val
                        unclear_per_batch_dict[b.batch_number] = unclear_val

                    pouch_waste.nsi_sample_pouches = total_nsi
                    pouch_waste.retention_sample_qty = total_retention
                    pouch_waste.nsi_sample_per_batch = nsi_per_batch_dict
                    pouch_waste.retention_sample_per_batch = retention_per_batch_dict
                    pouch_waste.unclear_coding_per_batch = unclear_per_batch_dict

                    # ===== NSI SAMPLE LOG DOCUMENTS =====
                    delete_sample_log_ids = request.POST.getlist('delete_nsi_sample_log_ids[]')
                    if delete_sample_log_ids:
                        current_docs = pouch_waste.nsi_sample_log_documents if pouch_waste.nsi_sample_log_documents else []
                        pouch_waste.nsi_sample_log_documents = [
                            d for d in current_docs 
                            if str(d.get('id')) not in delete_sample_log_ids
                        ]
                        # ✅ LOG DELETIONS
                        log_change(request.user, production, f"Deleted {len(delete_sample_log_ids)} NSI sample log docs")
                    
                    sample_log_files = request.FILES.getlist('nsi_sample_log_documents[]')

                    if sample_log_files:
                        import uuid
                        from django.core.files.storage import default_storage
                        
                        current_docs = pouch_waste.nsi_sample_log_documents if pouch_waste.nsi_sample_log_documents else []
                        
                        for f in sample_log_files:
                            file_path = default_storage.save(f'nsi_sample_logs/{f.name}', f)
                            current_docs.append({
                                'id': str(uuid.uuid4()),
                                'file': file_path,
                                'filename': f.name,
                            })
                            # ✅ LOG EACH UPLOAD
                            log_change(request.user, production, f"NSI sample log → {f.name}")
                        
                        pouch_waste.nsi_sample_log_documents = current_docs
                    
                    # ===== MACHINE PRODUCTION DOCUMENTS =====
                    delete_machine_ids = request.POST.getlist('delete_machine_production_ids[]')
                    if delete_machine_ids:
                        current_docs = pouch_waste.machine_production_documents if pouch_waste.machine_production_documents else []
                        pouch_waste.machine_production_documents = [
                            d for d in current_docs 
                            if str(d.get('id')) not in delete_machine_ids
                        ]
                        # ✅ LOG DELETIONS
                        log_change(request.user, production, f"Deleted {len(delete_machine_ids)} machine docs")

                    machine_files = request.FILES.getlist('machine_production_documents[]')
                    if machine_files:
                        import uuid
                        from django.core.files.storage import default_storage
                        
                        current_docs = pouch_waste.machine_production_documents if pouch_waste.machine_production_documents else []
                        
                        for f in machine_files:
                            file_path = default_storage.save(f'machine_docs/{f.name}', f)
                            current_docs.append({
                                'id': str(uuid.uuid4()),
                                'file': file_path,
                                'filename': f.name,
                            })
                            # ✅ LOG EACH UPLOAD
                            log_change(request.user, production, f"Machine doc → {f.name}")
                        
                        pouch_waste.machine_production_documents = current_docs

                    # ===== RETORT CONTROL DOCUMENTS =====
                    delete_retort_ids = request.POST.getlist('delete_retort_control_ids[]')
                    if delete_retort_ids:
                        current_docs = pouch_waste.retort_control_documents if pouch_waste.retort_control_documents else []
                        pouch_waste.retort_control_documents = [
                            d for d in current_docs 
                            if str(d.get('id')) not in delete_retort_ids
                        ]
                        # ✅ LOG DELETIONS
                        log_change(request.user, production, f"Deleted {len(delete_retort_ids)} retort docs")

                    retort_files = request.FILES.getlist('retort_control_documents[]')
                    if retort_files:
                        import uuid
                        from django.core.files.storage import default_storage
                        
                        current_docs = pouch_waste.retort_control_documents if pouch_waste.retort_control_documents else []
                        
                        for f in retort_files:
                            file_path = default_storage.save(f'retort_docs/{f.name}', f)
                            current_docs.append({
                                'id': str(uuid.uuid4()),
                                'file': file_path,
                                'filename': f.name,
                            })
                            # ✅ LOG EACH UPLOAD
                            log_change(request.user, production, f"Retort doc → {f.name}")
                        
                        pouch_waste.retort_control_documents = current_docs
                    
                    # Save everything
                    pouch_waste.save()
                    
                    # ✅ LOG MACHINE WASTE (only if changed)
                    new_machine = {
                        'count': pouch_waste.machine_count,
                        'seal_creeps': pouch_waste.seal_creeps,
                        'unsealed': pouch_waste.unsealed_poor_seal,
                        'screwed': pouch_waste.screwed_and_undated,
                        'overweight': pouch_waste.over_weight,
                        'underweight': pouch_waste.under_weight,
                        'empty': pouch_waste.empty_pouches,
                        'metal': pouch_waste.metal_detection,
                    }
                    log_model_changes(request.user, production, "Machine waste", old_machine, new_machine)
                    
                    # ✅ LOG RETORT WASTE (only if changed)
                    new_retort = {
                        'count': pouch_waste.retort_count,
                        'unclear': pouch_waste.total_unclear_coding,
                        'seal_creap': pouch_waste.retort_seal_creap,
                        'underweight': pouch_waste.retort_under_weight,
                        'poor_ceiling': pouch_waste.poor_ceiling_destroyed,
                    }
                    log_model_changes(request.user, production, "Retort waste", old_retort, new_retort)
                    
                    # ✅ LOG SAMPLES PER BATCH (only if changed)
                    for b in all_batches:
                        nsi = nsi_per_batch_dict.get(b.batch_number, 0)
                        retention = retention_per_batch_dict.get(b.batch_number, 0)
                        unclear = unclear_per_batch_dict.get(b.batch_number, 0)
                        old_b = old_samples.get(b.batch_number, {'nsi': 0, 'retention': 0, 'unclear': 0})
                        
                        if nsi != old_b['nsi'] or retention != old_b['retention'] or unclear != old_b['unclear']:
                            changes = []
                            if nsi != old_b['nsi']: changes.append(f"NSI: {old_b['nsi']} → {nsi}")
                            if retention != old_b['retention']: changes.append(f"retention: {old_b['retention']} → {retention}")
                            if unclear != old_b['unclear']: changes.append(f"unclear: {old_b['unclear']} → {unclear}")
                            log_change(request.user, production, f"{b.batch_number}: {', '.join(changes)}")
                    
                    messages.success(request, '✅ Pouch waste data saved!')
        except Exception as e:
            import traceback
            traceback.print_exc()
            messages.error(request, f'❌ Error: {str(e)}')
        
        # Redirect
        if request.POST.get('save_action') == 'save_exit':
            return redirect('admin:manufacturing_production_changelist')
        else:
            current_tab = request.POST.get('active_tab', 'cert')
            redirect_url = f"{request.path}?tab={current_tab}"
            return redirect(redirect_url)

    # ============= HANDLE GET - BUILD AND INJECT RESPONSE =============
    # ✅ Filter all batches by site
    all_batches = Batch.objects.filter(production_date=batch.production_date)
    if current_site:
        all_batches = all_batches.filter(site=current_site)
    all_batches = all_batches.order_by('batch_number')
    
    available_containers_list = get_available_containers_with_stock(batch, current_site)
    available_stock_transactions = get_available_stock_transactions_with_stock(batch, current_site)
    
    complete_packaging_data = get_packaging_data(batch, current_site, packaging_category)

    sauce_recipe_bookouts = get_sauce_recipe_bookouts(batch, current_site)

    # ✅ APPLY FILTER TO SAUCE
    sauce_recipe_bookouts = filter_batch_refs_by_flag(sauce_recipe_bookouts)

    # ✅ APPLY FILTER TO INGREDIENTS
    sauce_recipe_bookouts = filter_batch_refs_by_flag(sauce_recipe_bookouts)

    # ✅ ADD PER-ITEM OPENING BALANCES FOR SAUCE ITEMS
    sauce_recipe_openings = {}
    for recipe_item in ProductRecipeItem.objects.filter(
            recipe__product=batch.product
        ).select_related('stock_item'):
        previous_recipe = RecipeStockItemBalance.objects.filter(
            stock_item=recipe_item.stock_item,
            production_date__lt=batch.production_date,
        ).order_by('-production_date').first()

        sauce_recipe_openings[str(recipe_item.stock_item.id)] = {
            # use the correct field name with underscore
            "opening_balance": float(previous_recipe.closing_balance) if previous_recipe else 0,
        }
        
    # ✅ Get batch containers for this production date - ALWAYS show all containers
    batch_containers_qs = BatchContainer.objects.filter(production_date=batch.production_date)
    
    # Filter by site if in site context
    if current_site:
        batch_containers_qs = batch_containers_qs.filter(
            Q(container__site=current_site) |  # Import containers from current site
            Q(container__isnull=True)  # All local items (batch_ref)
        )
    
    batch_containers = batch_containers_qs
    
    # ✅ Get opening balances from PREVIOUS production FIRST
    meat_openings = get_meat_containers_opening_balance(batch, current_site)
    
    batch_containers_data = []
    
    # Find the previous production batch to get date range for booking outs
    previous_batch = Batch.objects.filter(
        production_date__lt=batch.production_date,
        site=batch.site
    ).order_by('-production_date').first()
    
    # Get booking out transactions BETWEEN previous batch and current batch
    if previous_batch:
        # Get OUT transactions after previous batch date and before current batch date
        between_out_transactions = StockTransaction.objects.filter(
            transaction_date__gt=previous_batch.production_date,
            transaction_date__lt=batch.production_date,
            transaction_type='OUT'
        ).values('batch_ref').annotate(total_qty=Sum('quantity'))
    else:
        # First batch: get all OUT transactions before this batch date
        between_out_transactions = StockTransaction.objects.filter(
            transaction_date__lt=batch.production_date,
            transaction_type='OUT'
        ).values('batch_ref').annotate(total_qty=Sum('quantity'))
    
    # Convert to dict for quick lookup: {batch_ref: total_qty}
    between_out_qty_map = {
        tx['batch_ref']: abs(float(tx['total_qty'])) if tx['total_qty'] else 0 
        for tx in between_out_transactions
    }
    

    
    # Step 1: Add containers from saved BatchContainer records
    # For each container, get its book_out_qty from between-batch OUT transactions
    if batch_containers.exists():
        for bc in batch_containers:
            container_id = bc.container.container_number if bc.container else bc.batch_ref
            if not container_id:
                continue
            
            opening_balance = meat_openings.get(container_id, {}).get('opening_balance', 0)
            
            # Get book_out_qty from OUT transactions between batches
            between_book_out_qty = between_out_qty_map.get(container_id, 0)
            
            batch_containers_data.append({
                'container_id': container_id,
                'opening_balance': opening_balance,
                'book_out_qty': between_book_out_qty,  # Only booking outs between batches
                'kg_used': 0,
                'stock_left': float(bc.stock_left) if bc.stock_left is not None else 0,
                'filled': float(bc.meat_filled) if bc.meat_filled is not None else 0,
                'waste': float(bc.container_waste) if bc.container_waste is not None else 0,
                'waste_factor': float(bc.waste_factor) if bc.waste_factor is not None else 0,
                'source_type': getattr(bc, 'source_type', 'import'),
                'defrost_documents': [
                    {
                        'id': d.id,
                        'filename': d.file.name.split('/')[-1],
                        'url': d.file.url,
                    }
                    for d in bc.defrost_documents.all()
                ],
            })
    

    
    pouch_waste = Waste.objects.filter(batch=batch).first()
    # ✅ Get Sauce record - always load, don't gate on containers
    sauce = Sauce.objects.filter(production_date=batch.production_date).first()
    

    # ⭐ STEP 1: GET CERTIFICATION DATA
    cert_data_dict = {}
    for b in all_batches:
        cert_data_dict[b.batch_number] = {
            'status': b.status or '',
            'incubation_start': b.incubation_start.strftime('%Y-%m-%d') if b.incubation_start else '',
            'incubation_end': b.incubation_end.strftime('%Y-%m-%d') if b.incubation_end else '',
            'nsi_submission_date': b.nsi_submission_date.strftime('%Y-%m-%d') if b.nsi_submission_date else '',
            'certification_date': b.certification_date.strftime('%Y-%m-%d') if b.certification_date else '',
        }

    # ⭐ STEP 2: GET SAUCE DATA
    sauce_data_dict = {}
    if sauce:
        # ✅ GET OPENING FROM PREVIOUS PRODUCTION
        previous_sauce = Sauce.objects.filter(
            production_date__lt=batch.production_date
        ).order_by('-production_date').first()
        
        sauce_data_dict = {
            'opening_balance': float(previous_sauce.closing_balance) if previous_sauce else 0,
            'amended_opening_balance': float(sauce.amended_opening_balance) if sauce.amended_opening_balance else 0,
            'cancel_opening_balance': sauce.cancel_opening_balance,
            'amended_reason': sauce.amended_reason or '',
            'sauce_mixed': float(sauce.sauce_mixed) if sauce.sauce_mixed else 0,
            'closing_balance': float(sauce.closing_balance) if sauce.closing_balance else 0,
        }

    meat_summary_dict = {}
    # ✅ Get Meat Production Summary - always load, don't gate on containers
    meat_summary = MeatProductionSummary.objects.filter(
        production_date=batch.production_date,
        site=current_site
    ).first()
    if meat_summary:
        meat_summary_dict = {
            'total_meat_filled': float(meat_summary.total_meat_filled) if meat_summary.total_meat_filled else 0,
            'total_waste': float(meat_summary.total_waste) if meat_summary.total_waste else 0,
            'filling_weight_per_pouch': float(meat_summary.filling_weight_per_pouch) if meat_summary.filling_weight_per_pouch else 0.277,
        }
    else:
        # ✅ Even if no meat_summary exists yet, show default filling weight
        meat_summary_dict = {
            'total_meat_filled': 0,
            'total_waste': 0,
            'filling_weight_per_pouch': 0.277,
        }

    pouch_waste_dict = {}
    if pouch_waste:
        pouch_waste_dict = {
            'machine_count': pouch_waste.machine_count or 0,
            'seal_creeps': pouch_waste.seal_creeps or 0,
            'unsealed_poor_seal': pouch_waste.unsealed_poor_seal or 0,
            'screwed_and_undated': pouch_waste.screwed_and_undated or 0,
            'over_weight': pouch_waste.over_weight or 0,
            'under_weight': pouch_waste.under_weight or 0,
            'empty_pouches': pouch_waste.empty_pouches or 0,
            'metal_detection': pouch_waste.metal_detection or 0,
            'retort_count': pouch_waste.retort_count or 0,
            'total_unclear_coding': pouch_waste.total_unclear_coding or 0,  # ✅ CHANGED
            'retort_seal_creap': pouch_waste.retort_seal_creap or 0,
            'retort_under_weight': pouch_waste.retort_under_weight or 0,
            'poor_ceiling_destroyed': pouch_waste.poor_ceiling_destroyed or 0,
            'pouches_withdrawn': pouch_waste.pouches_withdrawn or 0,
            'total_returned': pouch_waste.total_returned or 0,
            'packed': pouch_waste.packed or 0,
            'total_down_time': float(pouch_waste.total_down_time) if pouch_waste.total_down_time else 0,
            'reasons_for_down_time': pouch_waste.reasons_for_down_time or '',
            'nsi_sample_per_batch': pouch_waste.nsi_sample_per_batch or {},
            'retention_sample_per_batch': pouch_waste.retention_sample_per_batch or {},
            'unclear_coding_per_batch': pouch_waste.unclear_coding_per_batch or {},  # ✅ ALWAYS include
        }
    
    # ===== STEP 5: GET PACKAGING BALANCE DATA =====
    packaging_balances_for_json = PackagingBalance.objects.filter(production_date=batch.production_date)
    packaging_data_dict = {}
    for pb in packaging_balances_for_json:
        packaging_data_dict[str(pb.stock_item.id)] = {
            'closing_balance': float(pb.closing_balance) if pb.closing_balance else 0,
            'amended_reason': pb.amended_reason or '',
            'cancel_opening_use_bookout': pb.cancel_opening_use_bookout or False,
        }

    # ===== STEP 5B: GET COMPLETE PACKAGING DATA (FOR RENDERING) =====
    complete_packaging_data = get_packaging_data(batch, current_site, packaging_category)
    
    # ===== STEP 5C: GET PACKAGING OPENINGS (PREVIOUS CLOSING BALANCES) =====
    packaging_openings = get_packaging_openings(batch, current_site, packaging_category)

    # ===== STEP 5D: GET MEAT CONTAINER OPENING BALANCES =====
    # Always include opening balances (from previous production)
    meat_container_openings = meat_openings

    # ⭐ STEP 6: GET PRODUCT USAGE DATA
    product_usage_dict = {}
    for usage in BatchProductInventoryUsed.objects.filter(batch=batch):
        product_usage_dict[str(usage.stock_item.id)] = {
            'qty_used': float(usage.qty_used) if usage.qty_used else 0,
            'waste_qty': float(usage.waste_qty) if usage.waste_qty else 0,
            'ref_number': usage.ref_number or '',
        }
        
    # ⭐ STEP 7: GET AVAILABLE STOCK TRANSACTIONS (LOCAL)
    available_stock_transactions = get_available_stock_transactions_with_stock(batch, current_site)


    requires_nsi_nrcs_certification = getattr(batch.product, "requires_nsi_nrcs_certification", True)   
  
    batch_data = {
        'production_date': batch.production_date.strftime('%d/%m/%Y') if batch.production_date else '',
        'requires_certification': bool(requires_nsi_nrcs_certification),
        'main_component_category': main_component_category,
        'sauce_tab_name': sauce_tab_name,
        'packaging_tab_name': packaging_tab_name,
        'pouch_tab_name': pouch_tab_name,
        'all_batches': [
            {
                'id': b.pk,
                'batch_number': b.batch_number,
                'a_no': b.a_no,
                'shift_total': float(b.shift_total) if b.shift_total else 0,
                'nsi_documents': [
                    {
                        'id': d.id,
                        'filename': d.file.name.split('/')[-1],
                        'url': d.file.url,
                    }
                    for d in b.nsi_documents.all()   
                ],
            }
            for b in all_batches
        ],
        'available_containers': [
            {
                'pk': str(c['pk']),
                'container_number': str(c['container_number']),  
                'net_weight': float(c['net_weight']),
                'available_stock': float(c['available_stock'])
            } for c in available_containers_list
        ],
        'available_stock_transactions': [
            {
                'pk': str(t['pk']),
                'batch_ref': str(t['batch_ref']),
                'reference': str(t['reference']),  
                'net_weight': float(t['net_weight']),
                'available_stock': float(t['available_stock']),
                'source_type': 'local'
            } for t in available_stock_transactions
        ],

        'saved_batch_containers': batch_containers_data,
        'between_out_qty_map': between_out_qty_map,  # ✅ Pass map to frontend for instant population
        'meat_container_openings': meat_container_openings,
        'saved_cert_data': cert_data_dict,
        'saved_sauce_data': sauce_data_dict,
        'saved_meat_summary_data': meat_summary_dict,
        'saved_pouch_waste_data': pouch_waste_dict,
        'saved_packaging_data': complete_packaging_data,
        'saved_product_usage_data': product_usage_dict,
        
        'saved_recipe_documents': [
            {
                'id': doc.get('id'),
                'filename': doc.get('filename'),
                'url': f"/media/{doc.get('file')}",
            }
            for doc in (sauce.recipe_documents if sauce and sauce.recipe_documents else [])
        ],

        'saved_nsi_sample_log_documents': [
            {
                'id': doc.get('id'),
                'filename': doc.get('filename'),
                'url': f"/media/{doc.get('file')}",
            }
            for doc in (pouch_waste.nsi_sample_log_documents if pouch_waste and pouch_waste.nsi_sample_log_documents else [])
        ],

        'saved_machine_production_documents': [
            {
                'id': doc.get('id'),
                'filename': doc.get('filename'),
                'url': f"/media/{doc.get('file')}",
            }
            for doc in (pouch_waste.machine_production_documents if pouch_waste and pouch_waste.machine_production_documents else [])
        ],

        'saved_retort_control_documents': [
            {
                'id': doc.get('id'),
                'filename': doc.get('filename'),
                'url': f"/media/{doc.get('file')}",
            }
            for doc in (pouch_waste.retort_control_documents if pouch_waste and pouch_waste.retort_control_documents else [])
        ],
        
        'saved_final_packaging_documents': [
            {
                'id': doc.get('id'),
                'filename': doc.get('filename'),
                'url': f"/media/{doc.get('file')}",
            }
            for doc in (pouch_waste.final_product_packaging_documents if pouch_waste and pouch_waste.final_product_packaging_documents else [])
        ],

        'saved_inventory_bookout_documents': pouch_waste.inventory_book_out_documents if pouch_waste and pouch_waste.inventory_book_out_documents else {},

        'stock_transactions': [
            {
                'batch_ref': st.batch_ref,
                'quantity': float(st.quantity) if st.quantity else 0,
                'transaction_type': st.transaction_type,
                'transaction_date': st.transaction_date.strftime('%Y-%m-%d') if st.transaction_date else None,
            }
            for st in StockTransaction.objects.filter(transaction_type='OUT')
        ],
    }

    def get_all_product_stock_items(product):
        """Collect ALL stock items linked to a product from all sources"""
        all_items = {
            'main_product_components': {},
            'components': {},
            'recipes': {},
        }
        
        # 1. MAIN PRODUCT COMPONENTS
        for comp in product.main_product_components.all():
            all_items['main_product_components'][str(comp.id)] = {
                'id': comp.id,
                'stock_item_id': comp.stock_item.id,
                'stock_item_name': comp.stock_item.name,
                'unit_of_measure_name': comp.unit_of_measure.name if comp.unit_of_measure else 'Unit',
                'standard_usage': float(comp.standard_usage_per_production_unit),
            }
        
        # 2. PRODUCT COMPONENTS (ALL categories)
        for comp in product.components.all():
            all_items['components'][str(comp.id)] = {
                'id': comp.id,
                'stock_item_id': comp.stock_item.id,
                'stock_item_name': comp.stock_item.name,
                'unit_of_measure_name': comp.unit_of_measure.name if comp.unit_of_measure else 'Unit',
                'standard_usage': float(comp.standard_usage_per_production_unit),
            }
        
        # 3. RECIPES & RECIPE ITEMS
        for recipe in product.recipes.all():
            recipe_items = {}
            for item in ProductRecipeItem.objects.filter(recipe=recipe):
                recipe_items[str(item.id)] = {
                    'id': item.id,
                    'stock_item_id': item.stock_item.id,
                    'stock_item_name': item.stock_item.name,
                    'unit_of_measure_name': item.unit_of_measure.name if item.unit_of_measure else 'Unit',
                    'standard_usage': float(item.standard_usage_per_production_unit),
                }
            
            all_items['recipes'][str(recipe.id)] = {
                'id': recipe.id,
                'recipe_name': recipe.recipe_name,
                'recipe_items': recipe_items,
            }
        
        return all_items

    product_stock_data = get_all_product_stock_items(batch.product)

    packaging_info = ProductComponent.get_packaging_info(batch.product)

    batch_data['main_product_components'] = product_stock_data['main_product_components']
    batch_data['components'] = product_stock_data['components']
    batch_data['recipes'] = product_stock_data['recipes']
    batch_data['packaging_info'] = packaging_info
    
    
    summary_sauce_bookouts = filter_batch_refs_by_flag(sauce_recipe_bookouts)
    summary_packaging_data = filter_batch_refs_by_flag(complete_packaging_data)
       
    batch_data['sauce_recipe_bookouts'] = sauce_recipe_bookouts
    batch_data['sauce_recipe_openings'] = sauce_recipe_openings
    batch_data['packaging_data'] = complete_packaging_data
    batch_data['packaging_openings'] = packaging_openings
    batch_data['packaging_recipe_openings'] = packaging_openings
    
    batch_data['summary_sauce_bookouts'] = summary_sauce_bookouts
    batch_data['summary_packaging_data'] = summary_packaging_data
    
    # ✅ ADD RECIPE ITEM BALANCES TO BATCH DATA
    saved_recipe_items = {}  # ✅ CHANGE TO DICT

    # ✅ Always load RecipeStockItemBalance, don't gate on containers
    for item in RecipeStockItemBalance.objects.filter(production_date=batch.production_date):
            saved_recipe_items[str(item.stock_item.id)] = {
                'stock_item_id': item.stock_item.id,
                'stock_item_name': item.stock_item.name,
                'closing_balance': float(item.closing_balance) if item.closing_balance else 0,
                'batch_ref': item.batch_ref or '',
                'amended_reason': item.amended_reason or '',  
                'cancel_opening_use_bookout': item.cancel_opening_use_bookout or False,  
            }

    batch_data['saved_sauce_recipe_items'] = saved_recipe_items
    
    batch_data['saved_recipe_documents'] = []
    if sauce and sauce.recipe_documents:
        batch_data['saved_recipe_documents'] = [
            {
                'id': doc.get('id'),
                'filename': doc.get('filename'),
                'url': f"/media/{doc.get('file')}",
            }
            for doc in sauce.recipe_documents
        ]
    


   
    data_json = json.dumps(batch_data)

    # Build minimal HTML
    csrf_token = request.META.get('CSRF_COOKIE', '')
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Production Date: {batch.production_date.strftime('%d/%m/%Y')} - All Forms</title>
    <link rel="stylesheet" href="/static/admin/css/base.css">
    <link rel="stylesheet" href="/static/css/manufacturing-batch-tracker.css">
</head>
<body>
    <div class="batch-detail-wrapper">
        <form id="mainform" method="post" enctype="multipart/form-data">
            <input type="hidden" name="csrfmiddlewaretoken" value="{csrf_token}">
            <input type="hidden" name="active_tab" id="active_tab_input" value="cert">
            
            <!-- TOP BUTTONS WITH HISTORY -->
            <div class="button-bar" style="position: relative; padding-right: 150px;">
                <button type="submit" name="save_action" value="save" class="btn-save">💾 Save & Continue</button>
                <button type="submit" name="save_action" value="save_exit" class="btn-save-exit">✓ Save & Exit</button>
                <a href="/admin/manufacturing/production/" class="btn-return">↶ Return</a>
                <a href="/admin/" class="btn-home">🏠 Home</a>
                
                <a href="/admin/manufacturing/production/{production.pk}/history/"
                   class="btn-history"
                   style="background: #6c757d; color: white; border: none;
                          padding: 8px 16px; border-radius: 4px; cursor: pointer;
                          font-size: 13px; font-weight: 500; margin-left: 10px;
                          text-decoration: none; display: inline-block;">
                    History
                </a>
            </div>

            <!-- Simple modal container -->
            <div id="history-modal"
                 style="display:none; position:fixed; inset:0; background:rgba(0,0,0,.4); z-index:9999;">
              <div style="background:white; margin:50px auto; padding:20px;
                          width:80%; max-width:800px; border-radius:4px;">
                <button type="button"
                        onclick="document.getElementById('history-modal').style.display='none';"
                        style="float:right;">Close</button>
                <h2>Change History</h2>
                <div id="history-body"></div>
              </div>
            </div>

            <!-- PRODUCTION DATE -->
            <div style="text-align: center; padding: 10px 0; font-size: 14px; font-weight: bold; color: #333;">
                Production Date: {batch.production_date.strftime('%d/%m/%Y')}
            </div>

            <!-- TABS -->
            <div class="tab-bar">
                <button type="button" class="tab-btn active" onclick="showTab(event, 'cert')">Certification</button>
                <button type="button" class="tab-btn" onclick="showTab(event, 'meat')">{main_component_category}</button>
                <button type="button" class="tab-btn" onclick="showTab(event, 'sauce')">{sauce_tab_name}</button>
                <button type="button" class="tab-btn" onclick="showTab(event, 'processing')">Processing</button>
                <button type="button" class="tab-btn" onclick="showTab(event, 'packaging')">Packaging</button>
                <button type="button" class="tab-btn" onclick="showTab(event, 'downtime')">Down Time</button>
                <button type="button" class="tab-btn" onclick="showTab(event, 'product')">Summary</button>
            </div>

            <!-- TAB CONTENTS - MINIMAL -->
            <div id="cert" class="tab-content active"></div>
            <div id="meat" class="tab-content"></div>
            <div id="sauce" class="tab-content"></div>
            <div id="processing" class="tab-content"></div>
            <div id="packaging" class="tab-content"></div>
            <div id="downtime" class="tab-content"></div>
            <div id="product" class="tab-content"></div>
        </form>
    </div>

    <script src="/static/js/manufacturing-batch-tracker.js"></script>
    <script>
        window.BATCH_DATA = {data_json};
        window.complete_packaging_data = window.BATCH_DATA.saved_packaging_data || {{}};
        window.recipe_bookouts = window.BATCH_DATA.sauce_recipe_bookouts || {{}};
        console.log('✅ Manufacturing Batch Tracker - Data injected');
    </script>
</body>
</html>
"""
    
    # Return HttpResponse directly
    return HttpResponse(html_content, content_type='text/html')


@require_http_methods(["POST"])
def delete_batch_ajax(request, batch_id):
    """Delete a single batch via AJAX (immediate deletion, no save needed)"""
    from django.views.decorators.csrf import csrf_exempt
    
    try:
        # Use ID (primary key) instead of batch_number which is only unique per site
        batch = Batch.objects.get(id=batch_id)
        
        # Check if user has permission to delete
        if not request.user.is_staff:
            return JsonResponse({
                'success': False,
                'error': 'Permission denied'
            }, status=403)
        
        batch_number = batch.batch_number
        batch.delete()
        return JsonResponse({
            'success': True,
            'message': f'Batch {batch_number} (ID: {batch_id}) deleted successfully'
        })
    except Batch.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'Batch with ID {batch_id} not found'
        }, status=404)
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'error': f'{str(e)}',
            'traceback': traceback.format_exc()
        }, status=500)

