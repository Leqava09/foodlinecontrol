# inventory/views.py

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_GET
from django.contrib.admin.views.decorators import staff_member_required
from django.db import models
from django.urls import reverse
from manufacturing.models import Waste, Batch
from inventory.models import StockItem, StockTransaction, Amendment, FinishedProductTransaction
from commercial.models import Supplier
from decimal import Decimal
from datetime import datetime
import json

def get_batch_qty(request):
    batch_id = request.GET.get("batch_id")
    qty = ""
    if batch_id:
        try:
            batch = Batch.objects.get(pk=batch_id)
            qty = batch.shift_total
        except Batch.DoesNotExist:
            qty = ""
    return JsonResponse({"qty": qty})


@require_http_methods(["GET"])
def get_unit(request, stock_item_id):
    """Get unit of measure for a stock item"""
    try:
        stock_item = StockItem.objects.get(id=stock_item_id)
        unit = stock_item.unit_of_measure
        category_name = stock_item.category.name if stock_item.category else ''

        if unit:
            return JsonResponse({
                'unit_id': unit.id,
                'unit_name': unit.name,
                'unit_abbreviation': unit.abbreviation or unit.name,
                'category_name': category_name,
            })
        else:
            return JsonResponse({
                'unit_id': '',
                'unit_name': '',
                'unit_abbreviation': '',
                'category_name': category_name,
            })
    except StockItem.DoesNotExist:
        return JsonResponse({
            'error': 'Stock item not found',
            'unit_id': '',
            'unit_name': '',
            'unit_abbreviation': '',
            'category_name': '',
        }, status=404)


@staff_member_required
@require_http_methods(["GET"])
def get_stockitem(request, pk):
    """Return stock item details including category and sub_category"""
    try:
        stock_item = StockItem.objects.get(pk=pk)
        return JsonResponse({
            'id': stock_item.pk,
            'name': stock_item.name,
            'category': stock_item.category.name if hasattr(stock_item.category, 'name') else str(stock_item.category),
            'sub_category': stock_item.sub_category.name if stock_item.sub_category and hasattr(stock_item.sub_category, 'name') else '',
            'unit_of_measure': str(stock_item.unit_of_measure) if stock_item.unit_of_measure else None
        })
    except StockItem.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

@require_http_methods(["GET"])
def get_stockitem_by_batch(request):
    """Get stock_item by batch_ref - handles '/' separator for 2-LINE MODE"""
    batch_ref = request.GET.get('batch_ref', '').strip()
    
    if not batch_ref:
        return JsonResponse({
            'id': None,
            'name': None,
            'items': [],
            'count': 0,
        })
    
    items = []
    seen_ids = set()
    
    # ==================== HANDLE "/" SEPARATOR ====================
    if "/" in batch_ref:
        # 2-LINE MODE: "ref1 / ref2"
        refs_to_search = [ref.strip() for ref in batch_ref.split("/")]
    else:
        # 1-LINE MODE: "ref"
        refs_to_search = [batch_ref]
    
    # ==================== SEARCH EACH REF ====================
    for ref_to_search in refs_to_search:
        stock_trans = StockTransaction.objects.filter(
            batch_ref=ref_to_search
        ).select_related('stock_item')
        
        for tx in stock_trans:
            if tx.stock_item and tx.stock_item.id not in seen_ids:
                items.append({
                    'id': tx.stock_item.id,
                    'name': str(tx.stock_item),
                    'source': 'StockTransaction',
                    'transaction_id': tx.id,
                    'batch_ref': ref_to_search,
                })
                seen_ids.add(tx.stock_item.id)
    
    # ==================== RETURN ====================
    first_item = items[0] if items else {'id': None, 'name': None}
    
    return JsonResponse({
        'id': first_item.get('id'),
        'name': first_item.get('name'),
        'items': items,
        'count': len(items),
    })

@staff_member_required
@require_http_methods(["GET"])
def get_prod_batches(request, date_string):
    """Get production batches for a specific date (YYYY-MM-DD format)"""
    try:
        from datetime import datetime
        
        date_obj = datetime.strptime(date_string, '%Y-%m-%d').date()
        batches = Batch.objects.filter(
            production_date=date_obj
        ).values('batch_number', 'shift_total').order_by('batch_number')
        
        return JsonResponse({'batches': list(batches)})
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

# ============= NEW ENDPOINTS FOR MANUFACTURING & COSTING =============

def decimal_encoder(obj):
    """JSON encoder for Decimal values"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

@require_http_methods(["GET"])
def api_stock_item_available(request, stock_item_id):
    """
    Get available stock for a stock item
    Used by: Manufacturing (check stock before production), Costing (calculate cost)
    """
    try:
        stock_item = StockItem.objects.get(id=stock_item_id)
    except StockItem.DoesNotExist:
        return JsonResponse({'error': 'Stock item not found'}, status=404)
    
    # Calculate IN quantity
    in_qty = StockTransaction.objects.filter(
        stock_item=stock_item,
        transaction_type='IN'
    ).aggregate(
        total=models.Sum('quantity')
    )['total'] or Decimal('0')
    
    # Calculate OUT quantity (excluding production)
    out_qty = StockTransaction.objects.filter(
        stock_item=stock_item,
        transaction_type='OUT',
        batch__isnull=True  # Exclude production bookings
    ).aggregate(
        total=models.Sum('quantity')
    )['total'] or Decimal('0')
    
    # Calculate amendments
    amend_in = Amendment.objects.filter(
        stock_item=stock_item,
        amendment_type='IN'
    ).aggregate(
        total=models.Sum('quantity')
    )['total'] or Decimal('0')
    
    amend_out = Amendment.objects.filter(
        stock_item=stock_item,
        amendment_type='OUT'
    ).aggregate(
        total=models.Sum('quantity')
    )['total'] or Decimal('0')
    
    # Calculate available
    available = float(in_qty) - float(out_qty) + float(amend_in) - float(amend_out)
    
    return JsonResponse({
        'stock_item_id': stock_item.id,
        'stock_item_name': stock_item.name,
        'category': stock_item.category.name if stock_item.category else None,
        'unit_of_measure': stock_item.unit_of_measure.abbreviation if stock_item.unit_of_measure else None,
        'in_qty': float(in_qty),
        'out_qty': float(out_qty),
        'amendments_in': float(amend_in),
        'amendments_out': float(amend_out),
        'available_stock': available,
        'reorder_level': float(stock_item.reorder_level) if stock_item.reorder_level else 0,
    }, default=decimal_encoder)


@require_http_methods(["GET"])
def api_stock_item_costing(request, stock_item_id):
    """
    Get latest costing data for a stock item
    Used by: Costing (calculate product cost)
    """
    try:
        stock_item = StockItem.objects.get(id=stock_item_id)
    except StockItem.DoesNotExist:
        return JsonResponse({'error': 'Stock item not found'}, status=404)
    
    # Get latest IN transaction (most recent purchase)
    latest_trans = StockTransaction.objects.filter(
        stock_item=stock_item,
        transaction_type='IN'
    ).order_by('-transaction_date').first()
    
    if not latest_trans:
        return JsonResponse({
            'stock_item_id': stock_item.id,
            'stock_item_name': stock_item.name,
            'has_costing': False,
            'message': 'No purchase history'
        })
    
    # Calculate cost per unit
    total_cost = float(latest_trans.total_invoice_amount_excl or 0)
    transport_cost = float(latest_trans.transport_cost or 0)
    quantity = float(latest_trans.quantity or 1)
    
    cost_per_unit = (total_cost + transport_cost) / quantity if quantity > 0 else 0
    
    return JsonResponse({
        'stock_item_id': stock_item.id,
        'stock_item_name': stock_item.name,
        'has_costing': True,
        'latest_purchase': {
            'transaction_id': latest_trans.id,
            'supplier': latest_trans.supplier.name if latest_trans.supplier else None,
            'transaction_date': latest_trans.transaction_date.isoformat(),
            'quantity': float(latest_trans.quantity),
            'unit_of_measure': stock_item.unit_of_measure.abbreviation if stock_item.unit_of_measure else None,
        },
        'costing': {
            'invoice_amount_excl': total_cost,
            'transport_cost': transport_cost,
            'total_cost': total_cost + transport_cost,
            'cost_per_unit': cost_per_unit,
            'currency': latest_trans.currency,
        }
    }, default=decimal_encoder)


@require_http_methods(["GET"])
def api_batch_stock_usage(request, batch_id):
    """
    Get all stock items used in a specific batch
    Used by: Manufacturing (view materials used in batch)
    """
    try:
        batch = Batch.objects.get(id=batch_id)
    except Batch.DoesNotExist:
        return JsonResponse({'error': 'Batch not found'}, status=404)
    
    # Get all stock transactions linked to this batch
    transactions = StockTransaction.objects.filter(
        batch=batch
    ).select_related('stock_item', 'stock_item__category', 'stock_item__unit_of_measure')
    
    items_used = []
    for trans in transactions:
        items_used.append({
            'stock_item_id': trans.stock_item.id,
            'stock_item_name': trans.stock_item.name,
            'category': trans.stock_item.category.name if trans.stock_item.category else None,
            'quantity': float(trans.quantity),
            'unit_of_measure': trans.stock_item.unit_of_measure.abbreviation if trans.stock_item.unit_of_measure else None,
            'transaction_type': trans.transaction_type,
            'transaction_date': trans.transaction_date.isoformat(),
            'price_per': float(trans.price_per) if trans.price_per else 0,
            'total_cost': float(trans.total_invoice_amount_excl or 0) + float(trans.transport_cost or 0),
            'currency': trans.currency,
        })
    
    return JsonResponse({
        'batch_id': batch.id,
        'batch_number': batch.batch_number,
        'production_date': batch.production_date.isoformat(),
        'shift_total': float(batch.shift_total),
        'items_used': items_used,
        'total_items': len(items_used),
    }, default=decimal_encoder)


@require_http_methods(["GET"])
def api_all_stock_summary(request):
    """
    Get summary of all stock items with available quantities
    Used by: Dashboard, Reports, Manufacturing (quick stock check)
    """
    from django.db.models import Sum, Q
    
    stock_items = StockItem.objects.select_related(
        'category', 'sub_category', 'unit_of_measure'
    ).all()
    
    summary = []
    
    for item in stock_items:
        in_qty = StockTransaction.objects.filter(
            stock_item=item,
            transaction_type='IN'
        ).aggregate(Sum('quantity'))['quantity__sum'] or Decimal('0')
        
        out_qty = StockTransaction.objects.filter(
            stock_item=item,
            transaction_type='OUT',
            batch__isnull=True
        ).aggregate(Sum('quantity'))['quantity__sum'] or Decimal('0')
        
        amend_in = Amendment.objects.filter(
            stock_item=item,
            amendment_type='IN'
        ).aggregate(Sum('quantity'))['quantity__sum'] or Decimal('0')
        
        amend_out = Amendment.objects.filter(
            stock_item=item,
            amendment_type='OUT'
        ).aggregate(Sum('quantity'))['quantity__sum'] or Decimal('0')
        
        available = float(in_qty) - float(out_qty) + float(amend_in) - float(amend_out)
        
        # Flag if below reorder level
        below_reorder = available < float(item.reorder_level or 0)
        
        summary.append({
            'stock_item_id': item.id,
            'stock_item_name': item.name,
            'category': item.category.name if item.category else None,
            'sub_category': item.sub_category.name if item.sub_category else None,
            'unit_of_measure': item.unit_of_measure.abbreviation if item.unit_of_measure else None,
            'available_stock': available,
            'reorder_level': float(item.reorder_level) if item.reorder_level else 0,
            'below_reorder': below_reorder,
        })
    
    return JsonResponse({
        'total_items': len(summary),
        'items': summary,
    }, default=decimal_encoder)


@require_http_methods(["GET"])
def api_stock_category_summary(request):
    """
    Get stock summary grouped by category
    Used by: Dashboard, Reports
    """
    from django.db.models import Sum
    
    categories = StockItem.objects.values(
        'category__id',
        'category__name'
    ).distinct()
    
    summary = []
    
    for cat in categories:
        if not cat['category__id']:
            continue
            
        items = StockItem.objects.filter(category__id=cat['category__id'])
        
        total_available = 0
        total_in = 0
        total_out = 0
        
        for item in items:
            in_qty = StockTransaction.objects.filter(
                stock_item=item,
                transaction_type='IN'
            ).aggregate(Sum('quantity'))['quantity__sum'] or Decimal('0')
            
            out_qty = StockTransaction.objects.filter(
                stock_item=item,
                transaction_type='OUT',
                batch__isnull=True
            ).aggregate(Sum('quantity'))['quantity__sum'] or Decimal('0')
            
            total_in += float(in_qty)
            total_out += float(out_qty)
            total_available += float(in_qty) - float(out_qty)
        
        summary.append({
            'category_id': cat['category__id'],
            'category_name': cat['category__name'],
            'total_in': total_in,
            'total_out': total_out,
            'total_available': total_available,
            'item_count': items.count(),
        })
    
    return JsonResponse({
        'categories': summary,
    }, default=decimal_encoder)

@staff_member_required
@require_http_methods(["GET"])
def get_finished_batches_for_date(request):
    """
    Return batches for a given production_date (YYYY-MM-DD) for Finished Product.
    """
    date_str = request.GET.get('production_date')
    if not date_str:
        return JsonResponse([], safe=False)

    try:
        prod_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse([], safe=False)

    qs = (
        Batch.objects
        .filter(production_date=prod_date)
        .values('batch_number', 'shift_total')  # primary key is batch_number
        .order_by('batch_number')
    )

    data = [
        {
            "id": b["batch_number"],          # use batch_number as ID (PK)
            "batch_number": b["batch_number"],
            "shift_total": b["shift_total"],
        }
        for b in qs
    ]
    return JsonResponse(data, safe=False)

def decimal_encoder(obj):
    """JSON encoder for Decimal values"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

@require_http_methods(["GET"])
def api_stock_item_available(request, stock_item_id):
    """
    Get available stock for a stock item
    Used by: Manufacturing (check stock before production), Costing (calculate cost)
    """
    try:
        stock_item = StockItem.objects.get(id=stock_item_id)
    except StockItem.DoesNotExist:
        return JsonResponse({'error': 'Stock item not found'}, status=404)
    
    # Calculate IN quantity
    in_qty = StockTransaction.objects.filter(
        stock_item=stock_item,
        transaction_type='IN'
    ).aggregate(
        total=models.Sum('quantity')
    )['total'] or Decimal('0')
    
    # Calculate OUT quantity (excluding production)
    out_qty = StockTransaction.objects.filter(
        stock_item=stock_item,
        transaction_type='OUT',
        batch__isnull=True  # Exclude production bookings
    ).aggregate(
        total=models.Sum('quantity')
    )['total'] or Decimal('0')
    
    # Calculate amendments
    amend_in = Amendment.objects.filter(
        stock_item=stock_item,
        amendment_type='IN'
    ).aggregate(
        total=models.Sum('quantity')
    )['total'] or Decimal('0')
    
    amend_out = Amendment.objects.filter(
        stock_item=stock_item,
        amendment_type='OUT'
    ).aggregate(
        total=models.Sum('quantity')
    )['total'] or Decimal('0')
    
    # Calculate available
    available = float(in_qty) - float(out_qty) + float(amend_in) - float(amend_out)
    
    return JsonResponse({
        'stock_item_id': stock_item.id,
        'stock_item_name': stock_item.name,
        'category': stock_item.category.name if stock_item.category else None,
        'unit_of_measure': stock_item.unit_of_measure.abbreviation if stock_item.unit_of_measure else None,
        'in_qty': float(in_qty),
        'out_qty': float(out_qty),
        'amendments_in': float(amend_in),
        'amendments_out': float(amend_out),
        'available_stock': available,
        'reorder_level': float(stock_item.reorder_level) if stock_item.reorder_level else 0,
    }, default=decimal_encoder)


@require_http_methods(["GET"])
def api_stock_item_costing(request, stock_item_id):
    """
    Get latest costing data for a stock item
    Used by: Costing (calculate product cost)
    """
    try:
        stock_item = StockItem.objects.get(id=stock_item_id)
    except StockItem.DoesNotExist:
        return JsonResponse({'error': 'Stock item not found'}, status=404)
    
    # Get latest IN transaction (most recent purchase)
    latest_trans = StockTransaction.objects.filter(
        stock_item=stock_item,
        transaction_type='IN'
    ).order_by('-transaction_date').first()
    
    if not latest_trans:
        return JsonResponse({
            'stock_item_id': stock_item.id,
            'stock_item_name': stock_item.name,
            'has_costing': False,
            'message': 'No purchase history'
        })
    
    # Calculate cost per unit
    total_cost = float(latest_trans.total_invoice_amount_excl or 0)
    transport_cost = float(latest_trans.transport_cost or 0)
    quantity = float(latest_trans.quantity or 1)
    
    cost_per_unit = (total_cost + transport_cost) / quantity if quantity > 0 else 0
    
    return JsonResponse({
        'stock_item_id': stock_item.id,
        'stock_item_name': stock_item.name,
        'has_costing': True,
        'latest_purchase': {
            'transaction_id': latest_trans.id,
            'supplier': latest_trans.supplier.name if latest_trans.supplier else None,
            'transaction_date': latest_trans.transaction_date.isoformat(),
            'quantity': float(latest_trans.quantity),
            'unit_of_measure': stock_item.unit_of_measure.abbreviation if stock_item.unit_of_measure else None,
        },
        'costing': {
            'invoice_amount_excl': total_cost,
            'transport_cost': transport_cost,
            'total_cost': total_cost + transport_cost,
            'cost_per_unit': cost_per_unit,
            'currency': latest_trans.currency,
        }
    }, default=decimal_encoder)


@require_http_methods(["GET"])
def api_batch_stock_usage(request, batch_id):
    """
    Get all stock items used in a specific batch
    Used by: Manufacturing (view materials used in batch)
    """
    try:
        batch = Batch.objects.get(id=batch_id)
    except Batch.DoesNotExist:
        return JsonResponse({'error': 'Batch not found'}, status=404)
    
    # Get all stock transactions linked to this batch
    transactions = StockTransaction.objects.filter(
        batch=batch
    ).select_related('stock_item', 'stock_item__category', 'stock_item__unit_of_measure')
    
    items_used = []
    for trans in transactions:
        items_used.append({
            'stock_item_id': trans.stock_item.id,
            'stock_item_name': trans.stock_item.name,
            'category': trans.stock_item.category.name if trans.stock_item.category else None,
            'quantity': float(trans.quantity),
            'unit_of_measure': trans.stock_item.unit_of_measure.abbreviation if trans.stock_item.unit_of_measure else None,
            'transaction_type': trans.transaction_type,
            'transaction_date': trans.transaction_date.isoformat(),
            'price_per': float(trans.price_per) if trans.price_per else 0,
            'total_cost': float(trans.total_invoice_amount_excl or 0) + float(trans.transport_cost or 0),
            'currency': trans.currency,
        })
    
    return JsonResponse({
        'batch_id': batch.id,
        'batch_number': batch.batch_number,
        'production_date': batch.production_date.isoformat(),
        'shift_total': float(batch.shift_total),
        'items_used': items_used,
        'total_items': len(items_used),
    }, default=decimal_encoder)


@require_http_methods(["GET"])
def api_all_stock_summary(request):
    """
    Get summary of all stock items with available quantities
    Used by: Dashboard, Reports, Manufacturing (quick stock check)
    """
    from django.db.models import Sum, Q
    
    stock_items = StockItem.objects.select_related(
        'category', 'sub_category', 'unit_of_measure'
    ).all()
    
    summary = []
    
    for item in stock_items:
        in_qty = StockTransaction.objects.filter(
            stock_item=item,
            transaction_type='IN'
        ).aggregate(Sum('quantity'))['quantity__sum'] or Decimal('0')
        
        out_qty = StockTransaction.objects.filter(
            stock_item=item,
            transaction_type='OUT',
            batch__isnull=True
        ).aggregate(Sum('quantity'))['quantity__sum'] or Decimal('0')
        
        amend_in = Amendment.objects.filter(
            stock_item=item,
            amendment_type='IN'
        ).aggregate(Sum('quantity'))['quantity__sum'] or Decimal('0')
        
        amend_out = Amendment.objects.filter(
            stock_item=item,
            amendment_type='OUT'
        ).aggregate(Sum('quantity'))['quantity__sum'] or Decimal('0')
        
        available = float(in_qty) - float(out_qty) + float(amend_in) - float(amend_out)
        
        # Flag if below reorder level
        below_reorder = available < float(item.reorder_level or 0)
        
        summary.append({
            'stock_item_id': item.id,
            'stock_item_name': item.name,
            'category': item.category.name if item.category else None,
            'sub_category': item.sub_category.name if item.sub_category else None,
            'unit_of_measure': item.unit_of_measure.abbreviation if item.unit_of_measure else None,
            'available_stock': available,
            'reorder_level': float(item.reorder_level) if item.reorder_level else 0,
            'below_reorder': below_reorder,
        })
    
    return JsonResponse({
        'total_items': len(summary),
        'items': summary,
    }, default=decimal_encoder)


@require_http_methods(["GET"])
def api_stock_category_summary(request):
    """
    Get stock summary grouped by category
    Used by: Dashboard, Reports
    """
    from django.db.models import Sum
    
    categories = StockItem.objects.values(
        'category__id',
        'category__name'
    ).distinct()
    
    summary = []
    
    for cat in categories:
        if not cat['category__id']:
            continue
            
        items = StockItem.objects.filter(category__id=cat['category__id'])
        
        total_available = 0
        total_in = 0
        total_out = 0
        
        for item in items:
            in_qty = StockTransaction.objects.filter(
                stock_item=item,
                transaction_type='IN'
            ).aggregate(Sum('quantity'))['quantity__sum'] or Decimal('0')
            
            out_qty = StockTransaction.objects.filter(
                stock_item=item,
                transaction_type='OUT',
                batch__isnull=True
            ).aggregate(Sum('quantity'))['quantity__sum'] or Decimal('0')
            
            total_in += float(in_qty)
            total_out += float(out_qty)
            total_available += float(in_qty) - float(out_qty)
        
        summary.append({
            'category_id': cat['category__id'],
            'category_name': cat['category__name'],
            'total_in': total_in,
            'total_out': total_out,
            'total_available': total_available,
            'item_count': items.count(),
        })
    
    return JsonResponse({
        'categories': summary,
    }, default=decimal_encoder)

@staff_member_required
@require_http_methods(["GET"])
def get_finished_batches_for_date(request):
    """
    Return batches for a given production_date (YYYY-MM-DD) for Finished Product.
    """
    date_str = request.GET.get('production_date')
    if not date_str:
        return JsonResponse([], safe=False)

    try:
        prod_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse([], safe=False)

    qs = (
        Batch.objects
        .filter(production_date=prod_date)
        .select_related("product")                # so product is fetched efficiently
        .values(
            "batch_number",
            "shift_total",
            "product__product_name",              # adjust field name to your model
            "size",                               # if size is on Batch; otherwise product__size
        )
        .order_by("batch_number")
    )

    data = [
        {
            "id": b["batch_number"],
            "batch_number": b["batch_number"],
            "shift_total": b["shift_total"],
            "product_name": b["product__product_name"] or "",
            "size": b["size"] or "",
        }
        for b in qs
    ]
    return JsonResponse(data, safe=False)

@staff_member_required
@require_GET
def batch_ready_dispatch_api(request):
    batch_id = request.GET.get('batch_id')
    if not batch_id:
        return JsonResponse({'error': 'Missing batch_id'}, status=400)

    try:
        batch = Batch.objects.get(batch_number=batch_id)
    except Batch.DoesNotExist:
        return JsonResponse({'ready': 0})

    shift_total = float(batch.shift_total or 0)

    # 🔑 Always use the “master” Waste row (currently for A00825CH02A)
    # adjust this filter to whatever identifies the shared pouch waste record
    master_waste = Waste.objects.filter(batch__production_date=batch.production_date).order_by('pk').first()
    if master_waste:
        key = batch.batch_number

        nsi_dict       = master_waste.nsi_sample_per_batch or {}
        retention_dict = master_waste.retention_sample_per_batch or {}
        unclear_dict   = master_waste.unclear_coding_per_batch or {}

        if not isinstance(nsi_dict, dict):
            nsi_dict = {}
        if not isinstance(retention_dict, dict):
            retention_dict = {}
        if not isinstance(unclear_dict, dict):
            unclear_dict = {}

        nsi       = float(nsi_dict.get(key, 0) or 0)
        retention = float(retention_dict.get(key, 0) or 0)
        unclear   = float(unclear_dict.get(key, 0) or 0)

        ready = max(0, shift_total - nsi - retention - unclear)
    else:
        ready = shift_total

    return JsonResponse({'ready': ready})

@require_http_methods(["GET"])
def api_finished_product_available(request, batch_id):
    """
    Get available finished product for billing
    Returns: shift_total, cumulative_balance (available_for_billing)
    """
    try:
        batch = Batch.objects.get(batch_number=batch_id)
    except Batch.DoesNotExist:
        return JsonResponse({'error': 'Batch not found'}, status=404)
    
    available = batch.available_qty_for_billing
    
    return JsonResponse({
        'batch_id': batch.batch_number,
        'shift_total': float(batch.shift_total),
        'available_for_billing': float(available),
    }, default=decimal_encoder)


@staff_member_required
@require_GET
def available_stock(request):
    """
    Get available stock for a batch_ref (Container or StockTransaction)
    Returns: available, total_in, total_out
    """
    from django.db.models import Sum
    
    batch_ref = request.GET.get('batch_ref', '')
    
    if not batch_ref:
        return JsonResponse({'error': 'No batch_ref provided'}, status=400)
    
    try:
        from inventory.models import Container
        
        # Calculate total IN for this batch_ref
        container = Container.objects.filter(container_number=batch_ref).first()
        stock_in = container.total_weight_container if container else Decimal('0')
        
        # Also check StockTransaction IN
        tx_in = StockTransaction.objects.filter(
            batch_ref=batch_ref, transaction_type='IN'
        ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
        
        total_in = stock_in + tx_in
        
        # Add amendments IN (Booking Back In)
        amendments_in = Amendment.objects.filter(
            batch_ref=batch_ref, amendment_type='IN'
        ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
        
        total_in += amendments_in
        
        # Calculate total OUT
        tx_out = StockTransaction.objects.filter(
            batch_ref=batch_ref, transaction_type='OUT'
        ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
        
        amendments_out = Amendment.objects.filter(
            batch_ref=batch_ref, amendment_type='OUT'
        ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
        
        total_out = tx_out + amendments_out
        
        # Available = IN - OUT
        available = total_in - total_out
        
        return JsonResponse({
            'batch_ref': batch_ref,
            'total_in': float(total_in),
            'total_out': float(total_out),
            'available': float(available),
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def api_delivery_sites(request):
    """
    Get delivery sites (institutions) for a given client.
    Query parameters:
        client_id (int, required): The Client ID to filter by
    
    Returns JSON with:
        sites: [
            {
                id: <site_id>,
                name: <institution_name>
            },
            ...
        ]
    """
    client_id = request.GET.get('client_id')
    
    if not client_id:
        return JsonResponse({'error': 'client_id parameter is required'}, status=400)
    
    try:
        client_id = int(client_id)
    except ValueError:
        return JsonResponse({'error': 'client_id must be an integer'}, status=400)
    
    from transport.models import DeliverySite
    
    # Get all delivery sites for this client
    sites = DeliverySite.objects.filter(client_id=client_id).order_by('institutionname')
    
    sites_data = [
        {
            'id': site.id,
            'name': site.institutionname,
        }
        for site in sites
    ]
    
    return JsonResponse({
        'sites': sites_data
    })


# =============================================================================
# PURCHASE ORDER DOCUMENT VIEWS
# =============================================================================

from django.shortcuts import get_object_or_404, redirect
from django.http import HttpResponse, FileResponse
from commercial.models import CompanyDetails
from inventory.models import PurchaseOrder
import tempfile
import os
from subprocess import run


def fix_docx_jinja_tags(docx_path):
    """
    Fix jinja2 tags that are split across Word's formatting runs AND fix
    structural issues where {% for %} is inside a table but {% endfor %} 
    is a body paragraph outside the table.
    
    When Word applies formatting to {{ }} or {% %}, it splits the tag across XML elements.
    This creates a working copy with rejoined tags before rendering.
    """
    import zipfile
    import re
    import os
    import shutil
    
    try:
        # Create a temp copy to work with
        temp_path = docx_path + ".fixed.docx"
        shutil.copy2(docx_path, temp_path)
        
        # Read the document.xml
        with zipfile.ZipFile(temp_path, 'r') as zip_ref:
            xml_content = zip_ref.read('word/document.xml')
        
        xml_str = xml_content.decode('utf-8')
        original_xml = xml_str
        
        print("\n=== TEMPLATE TAG FIXING ===")
        
        def get_text_from_xml(xml_fragment):
            """Extract concatenated text from w:t tags in an XML fragment"""
            parts = re.findall(r'<w:t[^>]*>([^<]*)</w:t>', xml_fragment)
            return ''.join(parts)
        
        
        # ============================================================
        # STEP 1: STRUCTURAL FIX - Handle {% endfor %} outside table
        # ============================================================
        structural_fixes = 0
        
        # Find </w:tbl> followed by a body paragraph containing {% endfor %}
        tbl_endfor_pattern = re.compile(
            r'(</w:tbl>)(\s*)(<w:p\b[^>]*>.*?</w:p>)',
            re.DOTALL
        )
        
        matches = list(tbl_endfor_pattern.finditer(xml_str))
        for match in reversed(matches):
            para_xml = match.group(3)
            para_text = get_text_from_xml(para_xml).strip()
            
            if 'endfor' in para_text and '{%' in para_text:
                tbl_close_pos = match.start()
                
                all_tbl_opens = [m.start() for m in re.finditer(r'<w:tbl\b', xml_str[:tbl_close_pos])]
                if all_tbl_opens:
                    tbl_open_pos = all_tbl_opens[-1]
                    table_xml = xml_str[tbl_open_pos:tbl_close_pos]
                    table_text = get_text_from_xml(table_xml)
                    
                    if '{%' in table_text and ' for ' in table_text:
                        # Move {% endfor %} into the table as new row
                        print(f"  STRUCTURAL FIX: Moving {{% endfor %}} from body paragraph into table")
                        endfor_row = '<w:tr><w:tc><w:p><w:r><w:t xml:space="preserve">{% endfor %}</w:t></w:r></w:p></w:tc></w:tr>'
                        replacement = endfor_row + '</w:tbl>' + match.group(2)
                        xml_str = xml_str[:match.start()] + replacement + xml_str[match.end():]
                        structural_fixes += 1
        
        if structural_fixes > 0:
            print(f"Applied {structural_fixes} structural fix(es)")
        
        # ============================================================
        # STEP 2: Fix jinja tags split across Word formatting runs
        # ============================================================
        def fix_jinja_in_runs(paragraph_xml):
            """Fix jinja tags within a single paragraph's runs"""
            text_parts = re.findall(r'<w:t[^>]*>([^<]*)</w:t>', paragraph_xml)
            full_text = ''.join(text_parts)
            
            if '{{' not in full_text and '{%' not in full_text:
                return paragraph_xml
            
            jinja_patterns = []
            for match in re.finditer(r'\{\{[^}]+\}\}', full_text):
                jinja_patterns.append((match.start(), match.end(), match.group(0)))
            for match in re.finditer(r'\{%[^%]+%\}', full_text):
                jinja_patterns.append((match.start(), match.end(), match.group(0)))
            
            if not jinja_patterns:
                return paragraph_xml
            
            print(f"  Found jinja in paragraph: {[p[2] for p in jinja_patterns]}")
            
            p_open_match = re.match(r'(<w:p\b[^>]*>)', paragraph_xml)
            p_open = p_open_match.group(1) if p_open_match else '<w:p>'
            
            pPr_match = re.search(r'<w:pPr>.*?</w:pPr>', paragraph_xml, re.DOTALL)
            pPr = pPr_match.group(0) if pPr_match else ''
            
            # Extract run properties (font size, bold, etc.) from the original
            # runs so rebuilt runs preserve the template's text formatting.
            # Look for <w:rPr> inside <w:r> elements (not inside <w:pPr>).
            run_rPr = ''
            # First try: find rPr from actual runs (with or without w:r attributes)
            run_matches = re.finditer(r'<w:r\b[^>]*>(.*?)</w:r>', paragraph_xml, re.DOTALL)
            for rm in run_matches:
                run_content = rm.group(1)
                rPr_in_run = re.search(r'<w:rPr>(.*?)</w:rPr>', run_content, re.DOTALL)
                if rPr_in_run:
                    run_rPr = f'<w:rPr>{rPr_in_run.group(1)}</w:rPr>'
                    break
            # Fallback: use paragraph-level default rPr if no run-level rPr found
            if not run_rPr and pPr:
                pPr_rPr_match = re.search(r'<w:rPr>(.*?)</w:rPr>', pPr, re.DOTALL)
                if pPr_rPr_match:
                    run_rPr = f'<w:rPr>{pPr_rPr_match.group(1)}</w:rPr>'
            
            new_runs = []
            last_end = 0
            
            for start, end, jinja_text in sorted(jinja_patterns):
                if start > last_end:
                    before_text = full_text[last_end:start]
                    if before_text:  # Preserve whitespace-only text (e.g. space between variables)
                        new_runs.append(f'<w:r>{run_rPr}<w:t xml:space="preserve">{before_text}</w:t></w:r>')
                new_runs.append(f'<w:r>{run_rPr}<w:t xml:space="preserve">{jinja_text}</w:t></w:r>')
                last_end = end
            
            if last_end < len(full_text):
                after_text = full_text[last_end:]
                if after_text:  # Preserve whitespace-only trailing text
                    new_runs.append(f'<w:r>{run_rPr}<w:t xml:space="preserve">{after_text}</w:t></w:r>')
            
            return f'{p_open}{pPr}{"".join(new_runs)}</w:p>'
        
        changes = 0
        paragraphs = list(re.finditer(r'<w:p\b[^>]*>.*?</w:p>', xml_str, flags=re.DOTALL))
        
        for para_match in paragraphs:
            original_para = para_match.group(0)
            fixed_para = fix_jinja_in_runs(original_para)
            
            if fixed_para != original_para:
                xml_str = xml_str.replace(original_para, fixed_para, 1)
                changes += 1
        
        print(f"Fixed {changes} paragraphs with split jinja tags")
        
        # If nothing changed, return original
        if xml_str == original_xml:
            print("No jinja tags needed fixing - template is clean")
            return docx_path
        
        print(f"Creating fixed template...")
        
        # Write back to docx
        with zipfile.ZipFile(temp_path, 'r') as zip_ref:
            file_list = zip_ref.namelist()
        
        with zipfile.ZipFile(temp_path + '.new', 'w', zipfile.ZIP_DEFLATED) as zip_out:
            for file_name in file_list:
                if file_name == 'word/document.xml':
                    zip_out.writestr(file_name, xml_str.encode('utf-8'))
                else:
                    with zipfile.ZipFile(temp_path, 'r') as zip_ref:
                        zip_out.writestr(file_name, zip_ref.read(file_name))
        
        # Replace temp with fixed version
        os.remove(temp_path)
        os.rename(temp_path + '.new', temp_path)
        
        print(f"[OK] Fixed template saved to: {temp_path}\n")
        return temp_path
            
    except Exception as e:
        print(f"[WARNING] Could not fix DOCX tags: {e}")
        import traceback
        traceback.print_exc()
        return docx_path


@staff_member_required
def po_document_preview(request, pk):
    """
    Generate and preview a Purchase Order document as PDF.
    Uses the PO template from CompanyDetails and fills placeholders.
    Converts to PDF using LibreOffice (same as billing documents).
    """
    from docxtpl import DocxTemplate
    import tempfile
    
    po = get_object_or_404(PurchaseOrder, pk=pk)
    # For multi-tenant isolation: ALWAYS determine company based on who created the PO
    # HQ orders (is_hq_order=True) use HQ company even if they have a site assigned
    if po.is_hq_order:
        # HQ PO: use HQ company (site__isnull=True)
        company = CompanyDetails.objects.filter(site__isnull=True, is_active=True).first()
    elif po.site:
        # Site PO: use site's company
        company = CompanyDetails.objects.filter(site=po.site, is_active=True).first()
    else:
        # Fallback to HQ company
        company = CompanyDetails.objects.filter(site__isnull=True, is_active=True).first()
    
    if not company:
        return HttpResponse("No active company details found. Please configure Company Details first.", status=400)
    
    if not company.po_template:
        return HttpResponse("No PO template uploaded. Please upload a PO template in Company Details.", status=400)
    
    # Get the TARGET SITE's company info (for "To:" section on PO)
    site_company = None
    if po.site:
        site_company = CompanyDetails.objects.filter(site=po.site, is_active=True).first()
    
    # Currency symbols
    currency_symbols = {
        'R': 'R',
        'NAD': 'N$',
        'USD': '$',
        'EUR': '€',
    }
    currency_symbol = currency_symbols.get(po.currency, po.currency)
    
    # Prepare line items with proper structure for template access
    # Check if this is HQ PO (uses hq_line_items) or regular PO (uses line_items)
    line_items = []
    
    # Try HQ line items first (has SKU and size)
    hq_items = po.hq_line_items.all()
    if hq_items.exists():
        for idx, item in enumerate(hq_items, start=1):
            # Try to get SKU from multiple sources: line item, product.sku, product.product_code
            sku = item.sku or ''
            if not sku and item.product:
                if hasattr(item.product, 'sku'):
                    sku = item.product.sku or ''
                elif hasattr(item.product, 'product_code'):
                    sku = item.product.product_code or ''
            
            # Try to get size from line item or product
            size = item.size or ''
            if not size and item.product and hasattr(item.product, 'size'):
                size = item.product.size or ''
            
            line_items.append({
                'no': idx,
                'name': item.product.product_name if item.product else (sku or ''),
                'item_name': item.product.product_name if item.product else (sku or ''),
                'stock_item_name': item.product.product_name if item.product else (sku or ''),
                'sku': sku,
                'size': size,
                'category': item.category.name if item.category else '',
                'unit': 'Unit',  # HQ items don't have UOM
                'quantity': f"{item.quantity:,.2f}",
                'unit_price': f"{item.unit_price:,.2f}",
                'unit_price_with_currency': f"{currency_symbol} {item.unit_price:,.2f}",
                'line_total': f"{item.line_total:,.2f}",
                'line_total_with_currency': f"{currency_symbol} {item.line_total:,.2f}",
            })
    else:
        # Regular site PO line items (stock items - no SKU/size in model)
        for idx, item in enumerate(po.line_items.all(), start=1):
            line_items.append({
                'no': idx,
                'name': item.stock_item.name if item.stock_item else '',
                'item_name': item.stock_item.name if item.stock_item else '',
                'stock_item_name': item.stock_item.name if item.stock_item else '',
                'sku': '',  # Stock items don't have SKU
                'size': '',  # Stock items don't have size
                'category': item.category.name if item.category else '',
                'sub_category': item.sub_category.name if item.sub_category else '',
                'stock_item': item.stock_item.name if item.stock_item else '',
                'unit': str(item.unit_of_measure),
                'quantity': f"{item.quantity:,.2f}",
                'unit_price': f"{item.unit_price:,.2f}",
                'unit_price_with_currency': f"{currency_symbol} {item.unit_price:,.2f}",
                'line_total': f"{item.line_total:,.2f}",
                'line_total_with_currency': f"{currency_symbol} {item.line_total:,.2f}",
            })
    
    # Calculate totals - need to handle both HQ and regular line items
    if hq_items.exists():
        subtotal = sum(item.line_total for item in hq_items)
        total_qty = sum(item.quantity for item in hq_items)
    else:
        subtotal = sum(item.line_total for item in po.line_items.all())
        total_qty = sum(item.quantity for item in po.line_items.all())
    
    vat_rate = Decimal('0.15')  # 15% VAT
    vat_amount = subtotal * vat_rate
    grand_total = subtotal + vat_amount
    
    # Current date for document generation
    from datetime import date
    current_date = date.today().strftime('%d-%m-%Y')
    
    # Build context with BOTH flat variables AND nested po dict (templates use both)
    po_dict = {
        'vat_percentage': '15.00',
        'vat_amount': f"{vat_amount:,.2f}",
        'vat_amount_calculated': f"{vat_amount:,.2f}",  # Both names for compatibility
        'grand_total': f"{grand_total:,.2f}",
        'subtotal': f"{subtotal:,.2f}",
    }
    
    context = {
        # Nested PO object (for po.vat_percentage, po.grand_total, etc.)
        'po': po_dict,
        
        # Basic PO info - flat variables
        'po_number': f"PO-{po.po_number}",
        'order_date': po.order_date.strftime('%d-%m-%Y') if po.order_date else '',
        'due_date': po.due_date.strftime('%d-%m-%Y') if po.due_date else '',
        'current_date': current_date,
        'document_date': current_date,
        'today': current_date,
        'order_type': po.order_type,
        'currency': po.currency or 'R',
        'currency_symbol': currency_symbols.get(po.currency, po.currency),
        'status': po.get_status_display(),
        'notes': po.notes or '',
        'date': current_date,
        
        # Supplier Info (TO: section on PO)
        'supplier_name': po.supplier.name if po.supplier else '',
        'supplier_legal_name': po.supplier.legal_name if po.supplier and hasattr(po.supplier, 'legal_name') else (po.supplier.name if po.supplier else ''),
        'supplier_contact': po.supplier.contact_person if po.supplier else '',
        'supplier_email': po.supplier.email if po.supplier else '',
        'supplier_phone': po.supplier.phone if po.supplier else '',
        'supplier_address': po.supplier.address if po.supplier else '',
        'supplier_address_line1': po.supplier.address_line1 if po.supplier and hasattr(po.supplier, 'address_line1') else '',
        'supplier_address_line2': po.supplier.address_line2 if po.supplier and hasattr(po.supplier, 'address_line2') else '',
        'supplier_city': po.supplier.city if po.supplier and hasattr(po.supplier, 'city') else '',
        'supplier_province': po.supplier.province if po.supplier and hasattr(po.supplier, 'province') else '',
        'supplier_postal_code': po.supplier.postal_code if po.supplier and hasattr(po.supplier, 'postal_code') else '',
        'supplier_country': po.supplier.country if po.supplier and hasattr(po.supplier, 'country') else '',
        'supplier_vat_number': po.supplier.vat_number if po.supplier and hasattr(po.supplier, 'vat_number') else '',
        
        # TARGET SITE Info (TO: section on PO - the site receiving this PO from HQ)
        'site_name': site_company.name if site_company else '',
        'site_legal_name': site_company.legal_name if site_company else '',
        'site_address_line1': site_company.address_line1 if site_company else '',
        'site_address_line2': site_company.address_line2 if site_company else '',
        'site_city': site_company.city if site_company else '',
        'site_province': site_company.province if site_company else '',
        'site_postal_code': site_company.postal_code if site_company else '',
        'site_country': site_company.country if site_company else '',
        'site_phone': site_company.phone if site_company else '',
        'site_email': site_company.email if site_company else '',
        'site_vat_number': site_company.vat_number if site_company else '',
        'site_registration_number': site_company.registration_number if site_company else '',
        
        # Company Info (FROM: section - HQ creating the PO)
        'company_name': company.name or '',
        'company_legal_name': company.legal_name or '',
        'company_address_line1': company.address_line1 or '',
        'company_address_line2': company.address_line2 or '',
        'company_city': company.city or '',
        'company_province': company.province or '',
        'company_postal_code': company.postal_code or '',
        'company_country': company.country or '',
        'company_phone': company.phone or '',
        'company_email': company.email or '',
        'company_vat_number': company.vat_number or '',
        'company_registration_number': company.registration_number or '',
        
        # Line Items - use table_rows like billing docs (not items/rows)
        'table_rows': line_items,
        'rows': line_items,              # Alternative name
        'items': line_items,             # Alternative name
        
        # Totals - as formatted strings (also provided flat for templates that need it)
        'subtotal': f"{subtotal:,.2f}",
        'subtotal_with_currency': f"{currency_symbols.get(po.currency, po.currency)} {subtotal:,.2f}",
        'vat_rate': '15.00',
        'vat_percentage': '15.00',
        'vat_amount': f"{vat_amount:,.2f}",
        'vat_amount_with_currency': f"{currency_symbol} {vat_amount:,.2f}",
        'grand_total': f"{grand_total:,.2f}",
        'grand_total_with_currency': f"{currency_symbol} {grand_total:,.2f}",
        'total_amount': f"{currency_symbol} {subtotal:,.2f}",
        'total_amount_with_currency': f"{currency_symbol} {subtotal:,.2f}",
        'total_qty': f"{total_qty:,.2f}",
        
        # Extra fields
        'external_order_no': '',
        'our_reference': po.po_number or '',
    }
    
    try:
        # 1. Load and render template - FIX broken tags first
        template_path = company.po_template.path
        
        # Fix for Word templates with split formatting:
        # Word breaks {{ }} and {% %} across formatting runs when formatting is applied
        # E.g., "{{" + "company_name" + "}}" becomes split XML tags
        # Apply fix before loading with DocxTemplate
        fixed_template_path = fix_docx_jinja_tags(template_path)
        
        # Load template
        doc = DocxTemplate(fixed_template_path)
        
        # Debug: Log what variables are being sent
        print(f"\n=== PO DOCUMENT GENERATION DEBUG ===")
        print(f"Template: {template_path}")
        print(f"\nContext variables being passed:")
        for key in sorted(context.keys()):
            value = context[key]
            if isinstance(value, list):
                if value:
                    print(f"  {key}: LIST with {len(value)} items")
                    if value and isinstance(value[0], dict):
                        print(f"    First item keys: {list(value[0].keys())}")
                else:
                    print(f"  {key}: EMPTY LIST")
            elif isinstance(value, dict):
                print(f"  {key}: DICT with {len(value)} keys - {list(value.keys())[:5]}")
            else:
                val_str = str(value)[:60]
                print(f"  {key}: {val_str}")
        print(f"\nTotal variables: {len(context)}")
        print(f"=== END DEBUG ===\n")
        
        # Render the document with the context
        doc.render(context)
        
        # 2. Save to temp DOCX file
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_docx:
            docx_path = tmp_docx.name
            doc.save(docx_path)

        # 3. Convert DOCX to PDF using Python libraries (no LibreOffice needed)
        try:
            from costing.docx_to_pdf import docx_to_pdf_bytes
            import sys
            
            # Log to both console and file
            log_msg = f"\n{'='*60}\nATTEMPTING PO PDF CONVERSION\nDOCX Path: {docx_path}\nDOCX exists: {os.path.exists(docx_path)}\n{'='*60}\n"
            print(log_msg, flush=True)
            sys.stdout.flush()
            with open('debug_pdf.log', 'a', encoding='utf-8') as f:
                f.write(log_msg)
            
            pdf_content = docx_to_pdf_bytes(docx_path)
            
            log_success = f"\n{'='*60}\n[OK] PO PDF CONVERSION SUCCESSFUL!\nPDF size: {len(pdf_content)} bytes\n{'='*60}\n"
            print(log_success, flush=True)
            sys.stdout.flush()
            with open('debug_pdf.log', 'a', encoding='utf-8') as f:
                f.write(log_success)
            
            # Clean up temp DOCX file
            os.unlink(docx_path)
            
        except Exception as conversion_error:
            import traceback
            import sys
            error_trace = traceback.format_exc()
            
            log_error = f"\n{'='*60}\n[X] PO PDF CONVERSION FAILED!\nError: {str(conversion_error)}\nFull traceback:\n{error_trace}\nFalling back to DOCX...\n{'='*60}\n"
            print(log_error, flush=True)
            sys.stdout.flush()
            with open('debug_pdf.log', 'a', encoding='utf-8') as f:
                f.write(log_error)
            
            # Fallback: return DOCX if conversion fails
            with open(docx_path, 'rb') as f:
                docx_content = f.read()
            os.unlink(docx_path)
            response = HttpResponse(
                docx_content,
                content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )
            response['Content-Disposition'] = f'attachment; filename="PO-{po.po_number}.docx"'
            response['X-PDF-Error'] = str(conversion_error)[:200]  # Add error in header for debugging
            return response

        # 4. Return PDF
        response = HttpResponse(pdf_content, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="PO-{po.po_number}.pdf"'
        return response
        
    except Exception as e:
        import traceback
        error_msg = str(e)
        
        # Provide helpful error messages for common template issues
        if "'item' is undefined" in error_msg or "UndefinedError" in error_msg:
            help_msg = (
                f"<h2>Template Error: {error_msg}</h2>"
                f"<p><strong>Problem:</strong> The PO template has jinja2 syntax errors, likely due to Word formatting applied inside template fields.</p>"
                f"<p><strong>Solution:</strong> The template needs to be recreated without formatting inside {{{{ }}}} and {{% %}} placeholders.</p>"
                f"<p><strong>Steps:</strong><ol>"
                f"<li>Open the template in Microsoft Word: {template_path}</li>"
                f"<li>Find all template fields like {{{{ item.quantity }}}} that have bold, italic, or colored text</li>"
                f"<li>Remove the formatting from inside the template fields (select the {{% for %}} and {{{{ }}}} text and click 'Clear Formatting')</li>"
                f"<li>Save and reload to test</li>"
                f"</ol></p>"
                f"<p><strong>Or:</strong> Contact support to get a corrected template.</p>"
            )
            return HttpResponse(help_msg, status=500, content_type='text/html')
        
        elif "XMLSyntaxError" in error_msg:
            help_msg = (
                f"<h2>Template Corruption Error</h2>"
                f"<p>The Word template file appears to be corrupted. This can happen when Word applies extensive formatting to jinja2 fields.</p>"
                f"<p><strong>Solution:</strong> Please restore the template from backup or request a new template.</p>"
            )
            return HttpResponse(help_msg, status=500, content_type='text/html')
        
        else:
            traceback.print_exc()
            return HttpResponse(f"Error generating PO document: {error_msg}", status=500)


@staff_member_required
def email_po_document(request, pk):
    """
    Opens email with the PDF document (same workflow as billing):
    1. First downloads the PDF file
    2. Then opens mailto with pre-filled subject/body
    User just needs to attach the downloaded file.
    """
    import urllib.parse
    
    po = get_object_or_404(PurchaseOrder, pk=pk)
    # For multi-tenant isolation: ALWAYS determine company based on who created the PO
    # HQ orders (is_hq_order=True) use HQ company even if they have a site assigned
    if po.is_hq_order:
        # HQ PO: use HQ company (site__isnull=True)
        company = CompanyDetails.objects.filter(site__isnull=True, is_active=True).first()
    elif po.site:
        # Site PO: use site's company
        company = CompanyDetails.objects.filter(site=po.site, is_active=True).first()
    else:
        # Fallback to HQ company
        company = CompanyDetails.objects.filter(site__isnull=True, is_active=True).first()
    
    if not company:
        return HttpResponse("No active company details found.", status=400)
    
    # Get supplier email
    supplier_email = po.supplier.email if po.supplier and po.supplier.email else ""
    
    if not supplier_email:
        return HttpResponse(
            "<html><body><h2>No supplier email address found</h2>"
            "<p>Please add an email address to the supplier record.</p>"
            "<script>setTimeout(function(){ window.close(); }, 3000);</script></body></html>",
            content_type="text/html"
        )
    
    # Currency symbols
    currency_symbols = {'R': 'R', 'NAD': 'N$', 'USD': '$', 'EUR': '€'}
    currency_symbol = currency_symbols.get(po.currency, po.currency)
    
    # Build the PDF preview URL (to download)
    pdf_url = reverse("inventory:po_document_preview", args=[pk])
    
    # Build filename
    filename = f"PO-{po.po_number}.pdf"
    
    # Build mailto link
    subject = f"Purchase Order PO-{po.po_number}"
    body = f"""Dear {po.supplier.contact_person or po.supplier.name or 'Supplier'},

Please find attached Purchase Order PO-{po.po_number}.

Order Date: {po.order_date.strftime('%d-%m-%Y') if po.order_date else 'N/A'}
Due Date: {po.due_date.strftime('%d-%m-%Y') if po.due_date else 'N/A'}
Total Amount: {currency_symbol} {po.total_amount:,.2f}

Please confirm receipt and acceptance of this order.

Kind regards,
{company.name}"""
    
    mailto_url = f"mailto:{supplier_email}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
    
    # Return HTML that:
    # 1. Downloads the PDF via hidden link click
    # 2. Opens the mailto link
    # 3. Shows instructions
    return HttpResponse(
        f"""
        <html>
        <head>
            <title>Email Purchase Order</title>
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
                <h2>📧 Email Purchase Order</h2>
                <p>Your email client is opening with the PO details.</p>
                
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

