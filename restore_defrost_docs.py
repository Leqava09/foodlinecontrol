#!/usr/bin/env python
"""
Restore defrost documents for 01/10/25 BatchContainer records
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'foodlinecontrol.settings')
django.setup()

from manufacturing.models import DefrostDocument, BatchContainer
from django.core.files.base import ContentFile

# Data from dump.sql for defrost documents linked to 01/10/25 batch containers
defrost_docs_to_restore = [
    {
        'id': 58,
        'file_path': 'manufacturing/defrost_sheets/Quote_67859.pdf',
        'batch_container_id': 895,
        'uploaded_at': '2026-02-12 03:30:28.74641-05',
    },
    {
        'id': 59,
        'file_path': 'manufacturing/defrost_sheets/test_3_1ebWYp1.pdf',
        'batch_container_id': 896,
        'uploaded_at': '2026-02-12 03:30:28.7561-05',
    },
    {
        'id': 60,
        'file_path': 'manufacturing/defrost_sheets/test_1_5Av47ie.pdf',
        'batch_container_id': 897,
        'uploaded_at': '2026-02-12 03:30:28.757723-05',
    },
]

for doc_data in defrost_docs_to_restore:
    try:
        batch_container = BatchContainer.objects.get(id=doc_data['batch_container_id'])
        
        # Create a placeholder document record (files may not exist on disk)
        # The field just stores the file path, doesn't need the actual file
        doc, created = DefrostDocument.objects.update_or_create(
            id=doc_data['id'],
            defaults={
                'file': doc_data['file_path'],
                'batch_container': batch_container,
            }
        )
        
        action = "Updated" if not created else "Created"
        print(f"{action} DefrostDocument {doc_data['id']}")
        print(f"  File: {doc_data['file_path']}")
        print(f"  Batch Container: {batch_container.id} ({batch_container.production_date})")
        
    except BatchContainer.DoesNotExist:
        print(f"Error: BatchContainer {doc_data['batch_container_id']} not found")

print("\nDefrost document restore complete!")
