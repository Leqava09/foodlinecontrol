"""
Management command to create component snapshots for existing batches.

Run this once after deploying the snapshot feature to backfill snapshots
for all existing batches that don't have them yet.

Usage:
    python manage.py create_batch_snapshots
    python manage.py create_batch_snapshots --batch A014-1234  # Specific batch only
    python manage.py create_batch_snapshots --dry-run          # Preview only
"""

from django.core.management.base import BaseCommand
from manufacturing.models import Batch, BatchComponentSnapshot


class Command(BaseCommand):
    help = 'Create component snapshots for existing batches that do not have them'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch',
            type=str,
            help='Specific batch number to create snapshots for',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be done without making changes',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Recreate snapshots even if they already exist',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        batch_number = options.get('batch')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be made'))

        # Get batches to process
        if batch_number:
            batches = Batch.objects.filter(batch_number=batch_number)
            if not batches.exists():
                self.stdout.write(self.style.ERROR(f'Batch {batch_number} not found'))
                return
        else:
            batches = Batch.objects.all()

        total = batches.count()
        created_count = 0
        skipped_count = 0
        error_count = 0

        self.stdout.write(f'Processing {total} batches...')

        for batch in batches:
            if not batch.product:
                self.stdout.write(f'  {batch.batch_number}: No product assigned, skipping')
                skipped_count += 1
                continue

            # Check if snapshots already exist
            existing = BatchComponentSnapshot.objects.filter(batch=batch).exists()
            if existing and not force:
                self.stdout.write(f'  {batch.batch_number}: Snapshots already exist, skipping')
                skipped_count += 1
                continue

            if force and existing:
                if not dry_run:
                    BatchComponentSnapshot.objects.filter(batch=batch).delete()
                self.stdout.write(f'  {batch.batch_number}: Deleted existing snapshots')

            try:
                if not dry_run:
                    snapshots = BatchComponentSnapshot.create_snapshots_for_batch(batch)
                    snapshot_count = len(snapshots)
                else:
                    # Count what would be created
                    snapshot_count = (
                        batch.product.components.count() +
                        batch.product.main_product_components.count() +
                        sum(r.items.count() for r in batch.product.recipes.all())
                    )

                self.stdout.write(
                    self.style.SUCCESS(f'  {batch.batch_number}: {snapshot_count} snapshots created')
                )
                created_count += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  {batch.batch_number}: Error - {e}')
                )
                error_count += 1

        self.stdout.write('')
        self.stdout.write(f'Summary:')
        self.stdout.write(f'  Total batches: {total}')
        self.stdout.write(self.style.SUCCESS(f'  Created snapshots: {created_count}'))
        self.stdout.write(f'  Skipped: {skipped_count}')
        if error_count:
            self.stdout.write(self.style.ERROR(f'  Errors: {error_count}'))
