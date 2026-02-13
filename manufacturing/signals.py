from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from manufacturing.models import Production, Batch
from costing.models import BatchCosting, OverheadCosting, SalaryCosting


@receiver(post_save, sender=Batch)
def auto_create_batch_component_snapshots(sender, instance, created, **kwargs):
    """
    Create component snapshots when a batch is first created.
    This preserves product usage values so they don't change if product details are updated.
    """
    # Skip signal during loaddata (raw=True)
    if kwargs.get('raw', False):
        return
    
    # Only create snapshots on initial creation and if batch has a product
    if created and instance.product:
        from manufacturing.models import BatchComponentSnapshot
        try:
            BatchComponentSnapshot.create_snapshots_for_batch(instance)
        except Exception as e:
            # Log error but don't fail the batch save
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to create component snapshots for batch {instance.batch_number}: {e}")


@receiver(post_save, sender=Production)
def auto_create_batch_costing(sender, instance, created, **kwargs):
    # Skip signal during loaddata (raw=True)
    if kwargs.get('raw', False):
        return
    
    # Always check if BatchCosting exists, create if missing
    # This handles both new productions AND updated productions
    from costing.models import BatchCosting, BatchPriceApproval
    from manufacturing.models import Batch
    
    # ✅ Get or create BatchCosting with site
    batch_costing, bc_created = BatchCosting.objects.get_or_create(
        production_date=instance,
        defaults={'site': instance.site}  # ✅ Set site from Production
    )
    
    if bc_created or created:
        # ✅ Ensure site is set
        if not batch_costing.site:
            batch_costing.site = instance.site
        
        # ✅ Set default costing records if new - filtered by site
        if not batch_costing.overhead_costing_id:
            # Try to get a default overhead costing for this site
            from costing.models import OverheadCosting
            try:
                overhead_qs = OverheadCosting.objects.filter(use_as_default=True)
                if instance.site:
                    overhead_qs = overhead_qs.filter(site=instance.site)
                default_overhead = overhead_qs.first()
                if default_overhead:
                    batch_costing.overhead_costing = default_overhead
            except:
                pass
        
        if not batch_costing.salary_costing_id:
            # Try to get a default salary costing for this site
            from costing.models import SalaryCosting
            try:
                salary_qs = SalaryCosting.objects.filter(use_as_default=True)
                if instance.site:
                    salary_qs = salary_qs.filter(site=instance.site)
                default_salary = salary_qs.first()
                if default_salary:
                    batch_costing.salary_costing = default_salary
            except:
                pass
        
        batch_costing.save()
    
    # ✅ Create BatchPriceApproval for each batch if it doesn't exist - filtered by site
    batches = Batch.objects.filter(production_date=instance.production_date)
    if instance.site:
        batches = batches.filter(site=instance.site)
    for batch in batches:
        BatchPriceApproval.objects.get_or_create(
            batch=batch,
            defaults={
                'batch_costing': batch_costing
            }
        )
