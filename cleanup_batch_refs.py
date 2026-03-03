#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'foodlinecontrol.settings')
django.setup()

from manufacturing.models import BatchContainer
from inventory.models import Container, PackagingBalance, StockTransaction

print("="*70)
print("BATCH REFERENCE CLEANUP - DATABASE AUDIT")
print("="*70)

# Step 1: Check BatchContainer for orphaned containers
orphaned_batch_containers = BatchContainer.objects.filter(container__isnull=True)
print(f"\n1. BATCH CONTAINERS with NULL container:")
print(f"   Found: {orphaned_batch_containers.count()}")
if orphaned_batch_containers.exists():
    for bc in orphaned_batch_containers:
        print(f"     - {bc.production_date} - Batch Ref: {bc.batch_ref}")

# Step 2: Check StockTransaction for deleted container references
print(f"\n2. STOCK TRANSACTIONS - checking for batch refs from 16/02/2026:")
stock_trans_16feb = StockTransaction.objects.filter(
    transaction_date='2026-02-16'
).values('batch_ref').distinct()
print(f"   Unique batch_refs on 16/02/2026: {stock_trans_16feb.count()}")
for trans in stock_trans_16feb:
    print(f"     - {trans['batch_ref']}")

# Step 3: Check vs Container numbers
deleted_containers = ['Test 123', 'TCLU1331172']  # Containers we deleted
print(f"\n3. CHECKING for references to DELETED CONTAINERS:")
print(f"   Looking for: {deleted_containers}")

for ref in deleted_containers:
    # Find in PackagingBalance
    pb_refs = PackagingBalance.objects.filter(batch_ref=ref)
    if pb_refs.exists():
        print(f"\n   ❌ Found {pb_refs.count()} PackagingBalance records with batch_ref='{ref}':")
        for pb in pb_refs:
            print(f"      - {pb.production_date} - Stock Item: {pb.stock_item.name}")
    
    # Find in StockTransaction
    st_refs = StockTransaction.objects.filter(batch_ref=ref)
    if st_refs.exists():
        print(f"\n   ❌ Found {st_refs.count()} StockTransaction records with batch_ref='{ref}':")
        for st in st_refs[:5]:  # Show first 5
            print(f"      - {st.transaction_date}: {st.transaction_type} - {st.quantity} {st.stock_item.name}")
        if st_refs.count() > 5:
            print(f"      ... and {st_refs.count() - 5} more")
    
    # Find in BatchContainer
    bc_refs = BatchContainer.objects.filter(batch_ref=ref)
    if bc_refs.exists():
        print(f"\n   ❌ Found {bc_refs.count()} BatchContainer records with batch_ref='{ref}':")
        for bc in bc_refs:
            print(f"      - {bc.production_date}")

print("\n" + "="*70)
print("SUMMARY: Ready to clean up deleted container batch refs")
print("="*70)
