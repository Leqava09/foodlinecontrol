#!/usr/bin/env python
"""
Restore 01/10/25 BatchContainer records from database dump
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'foodlinecontrol.settings')
django.setup()

from manufacturing.models import BatchContainer
from inventory.models import Container
from datetime import date
from decimal import Decimal

# Data from dump.sql for 2025-10-01 (records 895, 896, 897)
containers_to_restore = [
    {
        'id': 895,
        'production_date': date(2025, 10, 1),
        'kg_frozen_meat_used': Decimal('7890.00'),
        'meat_filled': Decimal('5214.50'),
        'container_waste': Decimal('2675.50'),
        'waste_factor': Decimal('33.91'),
        'defrost_sheet': None,
        'batch_ref': None,
        'book_out_qty': Decimal('8200.00'),
        'stock_left': Decimal('310.00'),
        'balance_from_prev_shift': Decimal('0.00'),
        'source_type': 'import',
        'container_number': 'TCLU1331172',
    },
    {
        'id': 896,
        'production_date': date(2025, 10, 1),
        'kg_frozen_meat_used': Decimal('4268.00'),
        'meat_filled': Decimal('2820.72'),
        'container_waste': Decimal('1447.28'),
        'waste_factor': Decimal('33.91'),
        'defrost_sheet': None,
        'batch_ref': None,
        'book_out_qty': Decimal('4500.00'),
        'stock_left': Decimal('232.00'),
        'balance_from_prev_shift': Decimal('0.00'),
        'source_type': 'import',
        'container_number': 'TTNU8099285',
    },
    {
        'id': 897,
        'production_date': date(2025, 10, 1),
        'kg_frozen_meat_used': Decimal('3881.00'),
        'meat_filled': Decimal('2564.95'),
        'container_waste': Decimal('1316.05'),
        'waste_factor': Decimal('33.91'),
        'defrost_sheet': None,
        'batch_ref': 'Rain2045',
        'book_out_qty': Decimal('4000.00'),
        'stock_left': Decimal('119.00'),
        'balance_from_prev_shift': Decimal('0.00'),
        'source_type': 'local',
        'container_number': None,
    },
]

for data in containers_to_restore:
    container_number = data.pop('container_number')
    
    # Find the container if it's an import
    container_obj = None
    if container_number:
        try:
            container_obj = Container.objects.get(container_number=container_number)
        except Container.DoesNotExist:
            print(f"Warning: Container {container_number} not found, will create record with container_id=None")
    
    # Create or update the BatchContainer
    bc, created = BatchContainer.objects.update_or_create(
        id=data['id'],
        defaults={
            'production_date': data['production_date'],
            'kg_frozen_meat_used': data['kg_frozen_meat_used'],
            'meat_filled': data['meat_filled'],
            'container_waste': data['container_waste'],
            'waste_factor': data['waste_factor'],
            'defrost_sheet': data['defrost_sheet'],
            'batch_ref': data['batch_ref'],
            'book_out_qty': data['book_out_qty'],
            'stock_left': data['stock_left'],
            'balance_from_prev_shift': data['balance_from_prev_shift'],
            'source_type': data['source_type'],
            'container': container_obj,
        }
    )
    
    action = "Updated" if not created else "Created"
    print(f"{action} BatchContainer {data['id']} for {data['production_date']}")
    if container_number:
        print(f"  Container: {container_number}")
    else:
        print(f"  Batch Ref: {data['batch_ref']}")
    print(f"  Meat Filled: {data['meat_filled']} kg")

print("\nRestore complete!")
