# incident_management/signals.py
from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import Incident
from manufacturing.models import Production


@receiver(pre_save, sender=Incident)
def set_production_from_date(sender, instance, **kwargs):
    """
    Auto-populate production FK when production_date is selected.
    This ensures the ChainedForeignKey for batch works correctly.
    """
    if instance.production_date and instance.site and not instance.production:
        # Find Production matching the date and site
        production = Production.objects.filter(
            production_date=instance.production_date,
            site=instance.site
        ).first()
        if production:
            instance.production = production
