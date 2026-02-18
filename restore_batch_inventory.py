#!/usr/bin/env python
"""
Restore ProductInventoryUsed records for batch A00725CH02A
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'foodlinecontrol.settings')
django.setup()

from manufacturing.models import BatchProductInventoryUsed, Batch
from product_details.models import Product
from inventory.models import StockItem
from decimal import Decimal

# Data from dump.sql for batch_id 1
inventory_records = [
    {'id': 27, 'is_packaging': False, 'qty_used': Decimal('0.0000'), 'waste_qty': Decimal('0.0000'), 'ref_number': '', 'product_id': 1, 'stock_item_id': 4, 'batch_id': 1},
    {'id': 28, 'is_packaging': False, 'qty_used': Decimal('0.0000'), 'waste_qty': Decimal('0.0000'), 'ref_number': '', 'product_id': 1, 'stock_item_id': 3, 'batch_id': 1},
    {'id': 29, 'is_packaging': False, 'qty_used': Decimal('0.0000'), 'waste_qty': Decimal('0.0000'), 'ref_number': '', 'product_id': 1, 'stock_item_id': 2, 'batch_id': 1},
    {'id': 30, 'is_packaging': False, 'qty_used': Decimal('0.0000'), 'waste_qty': Decimal('0.0000'), 'ref_number': '', 'product_id': 1, 'stock_item_id': 10, 'batch_id': 1},
    {'id': 31, 'is_packaging': False, 'qty_used': Decimal('0.0000'), 'waste_qty': Decimal('0.0000'), 'ref_number': '', 'product_id': 1, 'stock_item_id': 11, 'batch_id': 1},
]

batch = Batch.objects.get(id=1)
product = Product.objects.get(id=1)

print(f"\nRestoring ProductInventoryUsed records for batch {batch.batch_number}:\n")

for record_data in inventory_records:
    try:
        stock_item = StockItem.objects.get(id=record_data['stock_item_id'])
        
        inv, created = BatchProductInventoryUsed.objects.update_or_create(
            id=record_data['id'],
            defaults={
                'is_packaging': record_data['is_packaging'],
                'qty_used': record_data['qty_used'],
                'waste_qty': record_data['waste_qty'],
                'ref_number': record_data['ref_number'],
                'product': product,
                'stock_item': stock_item,
                'batch': batch,
            }
        )
        
        action = "Updated" if not created else "Created"
        print(f"✓ {action} Record {record_data['id']}: {stock_item.name}")
        
    except StockItem.DoesNotExist:
        print(f"❌ Error: StockItem with ID {record_data['stock_item_id']} not found!")

print(f"\n✓ All ProductInventoryUsed records restored!")
