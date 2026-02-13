# inventory/templatetags/inventory_tags.py
from django import template
from decimal import Decimal
from inventory.models import Amendment
from manufacturing.models import BatchProductInventoryUsed

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary (for amendments or similar dict access)"""
    if dictionary:
        return dictionary.get(key, [])
    return []

@register.simple_tag
def calculate_totals(transactions, amendments):
    # ONLY count Booking IN transactions
    total_in = sum(t.quantity for t in transactions if t.transaction_type == 'IN')
    
    # ONLY count Booking OUT (without batch FK) - NOT production out
    total_out = sum(t.quantity for t in transactions if t.transaction_type == 'OUT' and not t.batch)
    
    amend_in = sum(a.quantity for a in amendments if a.amendment_type == 'IN')
    amend_out = sum(a.quantity for a in amendments if a.amendment_type == 'OUT')
    
    booking_in = total_in + amend_in
    total_used = total_out + amend_out
    balance = booking_in - total_used
    
    return {
        'booking_in': f"+{booking_in:.2f}",
        'total_used': f"-{total_used:.2f}",
        'balance': f"{balance:.2f}",
        'trans_count': len(list(transactions)),
        'amend_count': len(list(amendments)),
    }

@register.simple_tag
def calculate_reconciliation(transactions, amendments):
    """
    Calculate reconciliation for production vs. booking out:
    - Morning Booking Out: Sum of OUT transactions WITHOUT batch FK + OUT amendments
    - Production Qty Used: Sum of qty_used + waste_qty from BatchProductInventoryUsed
    - Difference: Booking Out - Production Qty Used
    """
    booking_out_qty = Decimal('0')
    production_qty_used = Decimal('0')
    
    if not transactions:
        transactions = []
    if not amendments:
        amendments = []
    
    # Calculate Morning Booking Out (regular OUT without batch FK) + amendments OUT
    for transaction in transactions:
        if transaction.transaction_type == 'OUT' and not transaction.batch:
            booking_out_qty += Decimal(str(transaction.quantity or 0))
    
    # Add amendment OUT amounts
    for amendment in amendments:
        if amendment.amendment_type == 'OUT':
            booking_out_qty += Decimal(str(amendment.quantity or 0))
    
    # Calculate Production Qty Used (OUT with batch FK)
    for transaction in transactions:
        if transaction.transaction_type == 'OUT' and transaction.batch:
            try:
                prod_usage = BatchProductInventoryUsed.objects.filter(
                    batch=transaction.batch,
                    stock_item=transaction.stock_item
                ).first()
                if prod_usage:
                    qty_used = Decimal(str(prod_usage.qty_used or 0))
                    waste_qty = Decimal(str(prod_usage.waste_qty or 0))
                    production_qty_used += qty_used + waste_qty
                else:
                    # If no BatchProductInventoryUsed record, use transaction quantity
                    production_qty_used += Decimal(str(transaction.quantity or 0))
            except Exception:
                # Fallback to transaction quantity if error
                production_qty_used += Decimal(str(transaction.quantity or 0))
    
    difference = booking_out_qty - production_qty_used
    
    return {
        'booking_out_qty': f"-{booking_out_qty:.2f}",
        'production_qty_used': f"-{production_qty_used:.2f}",
        'difference': f"{difference:.2f}",
    }
    
@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key - handles production_usage dict"""
    if dictionary is None:
        return None
    if not isinstance(dictionary, dict):
        return None
    
    # Try exact match first
    if key in dictionary:
        return dictionary.get(key)
    
    # Try converting key to string
    key_str = str(key)
    if key_str in dictionary:
        return dictionary.get(key_str)
    
    # If still not found, return None (which becomes "-" with default filter)
    return None

@register.filter
def make_key(date_str, item_id):
    """Create a key from date and item_id: '2025-10-01' + 4 = '2025-10-01_4'"""
    return f"{date_str}_{item_id}"