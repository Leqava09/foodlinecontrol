import os
import re
from pathlib import Path

workspace_root = Path(__file__).parent

# Find all migrations directories
migrations_dirs = workspace_root.glob('*/migrations')

deletion_count = 0
for migrations_dir in migrations_dirs:
    if not migrations_dir.is_dir():
        continue
    
    # Get all migration files except __init__.py and 0001_initial.py
    for migration_file in migrations_dir.glob('*.py'):
        if migration_file.name in ['__init__.py', '0001_initial.py']:
            continue
        
        # Check if it's a migration file (starts with 4 digits)
        if re.match(r'^\d{4}_.+\.py$', migration_file.name):
            try:
                migration_file.unlink()
                print(f"✓ Deleted {migrations_dir.name}/{migration_file.name}")
                deletion_count += 1
            except Exception as e:
                print(f"✗ Error deleting {migration_file.name}: {e}")

print(f"\nTotal migrations deleted: {deletion_count}")
