# inventory/signals.py

import re
import logging
from decimal import Decimal

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.db.models import Q  # ✅ ADD THIS

from inventory.models import FinishedProductTransaction, PickingSlip

logger = logging.getLogger(__name__)


def _next_load_number():
    from transport.models import TransportLoad

    max_load = (
        TransportLoad.objects.order_by("-load_number")
        .values_list("load_number", flat=True)
        .first()
    )
    return (int(max_load) + 1) if max_load else 1


@receiver(post_save, sender=PickingSlip)
def create_or_update_transport_on_picking_completed(sender, instance, created, **kwargs):
    """
    When a PickingSlip is marked completed=True:
    - Build TransportLoad for its Billing
    - Auto-release ALL dispatch transactions for that billing
    - Sync Released By and Notes to dispatches
    
    When completed is False:
    - Remove TransportLoad
    - Un-release all dispatches
    """
    # Skip signal during loaddata (raw=True)
    if kwargs.get('raw', False):
        return
        
    from costing.models import BatchCosting, BatchPriceApproval
    from transport.models import TransportLoad

    billing = instance.billing
    billing_number = billing.base_number

    # ✅ Find all dispatch transactions for this billing (handle empty notes too)
    # SITE-SCOPED: Only find dispatches that belong to THIS billing's site
    # Get all batches that should be on this billing from qty_for_invoice_data
    if billing.qty_for_invoice_data:
        batch_numbers = list(billing.qty_for_invoice_data.keys())
    else:
        batch_numbers = []
    
    # Base filter: site-scoped to the billing's site
    site_filter = Q(site=billing.site) if billing.site else Q(site__isnull=True)
    
    # Find dispatches by:
    # 1. Notes containing "Billing {number}" OR
    # 2. Batch number in the invoice AND empty/minimal notes
    if batch_numbers:
        dispatches = FinishedProductTransaction.objects.filter(
            site_filter,
            transaction_type="DISPATCH"
        ).filter(
            Q(notes__contains=f"Billing {billing_number}") |
            Q(batch__batch_number__in=batch_numbers, notes__in=['', f"Billing {billing_number}"])
        )
    else:
        dispatches = FinishedProductTransaction.objects.filter(
            site_filter,
            transaction_type="DISPATCH",
            notes__contains=f"Billing {billing_number}"
        )

    if not dispatches.exists():
        logger.warning(f"⚠️ No dispatches found for billing {billing_number}")
        return

    # ✅ If completed is FALSE, un-release dispatches and remove TransportLoad
    if not instance.completed:
        dispatches.update(
            stock_released=False,
            stock_released_date=None,
            status='PENDING',
            authorized_person='',
            notes=f"Billing {billing_number}",
        )
        
        TransportLoad.objects.filter(billing_document=billing).delete()
        
        logger.info(
            "🗑️ TransportLoad removed and %d dispatches un-released for billing %s",
            dispatches.count(),
            billing.base_number,
        )
        return

    # ✅ If completed is TRUE, release dispatches and create/update TransportLoad
    
    release_date = instance.date_completed.date() if instance.date_completed else timezone.now().date()
    
    # Build notes with picking slip notes
    release_notes = f"Billing {billing_number}"
    if instance.notes:
        release_notes = f"{release_notes}\n{instance.notes}"
    
    dispatches.update(
        stock_released=True,
        stock_released_date=release_date,
        status='RELEASED',
        authorized_person=instance.released_by or '',
        notes=release_notes,
    )
    
    logger.info(
        "✅ Auto-released %d dispatch transactions for billing %s",
        dispatches.count(),
        billing_number,
    )

    # Build batch_data for TransportLoad
    dispatches_with_batch = dispatches.select_related("batch", "batch__product")
    
    if not dispatches_with_batch.exists():
        return

    batch_data = []
    for dispatch in dispatches_with_batch:
        batch = dispatch.batch
        if not batch:
            continue

        # Extract qty from qty_for_invoice_data - handle nested structure with qty_mapping
        qty = 0
        if billing.qty_for_invoice_data:
            if isinstance(billing.qty_for_invoice_data, dict) and 'qty_mapping' in billing.qty_for_invoice_data:
                # New format: {'qty_mapping': {batch_number: qty}, ...}
                qty = billing.qty_for_invoice_data['qty_mapping'].get(batch.batch_number, 0)
            elif isinstance(billing.qty_for_invoice_data, dict):
                # Old format: {batch_number: qty}
                qty = billing.qty_for_invoice_data.get(batch.batch_number, 0)

        batch_costing = None
        if batch.production:
            # Use the FK relationship if available
            batch_costing = BatchCosting.objects.filter(production_date=batch.production).first()
        elif batch.production_date and batch.site:
            # Fall back to finding Production by date, then BatchCosting
            from manufacturing.models import Production
            production = Production.objects.filter(
                production_date=batch.production_date, 
                site=batch.site
            ).first()
            if production:
                batch_costing = BatchCosting.objects.filter(production_date=production).first()
        
        price_per_unit = Decimal("0")

        if batch_costing:
            approval = BatchPriceApproval.objects.filter(
                batch_costing=batch_costing,
                batch=batch,
                is_approved=True,
            ).first()
            if approval:
                price_per_unit = approval.batch_price_per_unit

        production_date_str = ""
        if batch.production_date:
            production_date_str = batch.production_date.strftime("%d/%m/%Y")

        batch_data.append({
            "batch_number": batch.batch_number,
            "product": str(batch.product) if batch.product else "",
            "size": batch.size or "",
            "production_date": production_date_str,
            "qty_for_invoice": float(qty),
            "price_per_unit": float(price_per_unit),
        })

    latest_date = (
        dispatches_with_batch.exclude(date__isnull=True)
        .order_by("-date")
        .values_list("date", flat=True)
        .first()
    ) or timezone.now().date()

    # CREATE or UPDATE TransportLoad
    if not TransportLoad.objects.filter(billing_document=billing).exists():
        next_load_number = _next_load_number()

        transport_load = TransportLoad.objects.create(
            site=instance.site or billing.site,
            billing_document=billing,
            client=billing.client,
            delivery_institution=billing.delivery_institution,
            billing_date=billing.billing_date,
            released_date=latest_date,
            transport_cost=billing.transport_cost or Decimal("0"),
            transporter=billing.transporters,
            batch_data=batch_data,
            load_number=str(next_load_number),
            date_loaded=latest_date,
        )
    else:
        transport_load = TransportLoad.objects.filter(billing_document=billing).first()
        transport_load.billing_date = billing.billing_date
        transport_load.released_date = latest_date
        transport_load.date_loaded = latest_date
        transport_load.transport_cost = billing.transport_cost or transport_load.transport_cost
        transport_load.transporter = billing.transporters
        transport_load.batch_data = batch_data
        transport_load.delivery_institution = billing.delivery_institution
        transport_load.save(update_fields=[
            "billing_date",
            "released_date",
            "transport_cost",
            "transporter",
            "batch_data",
            "date_loaded",
            "delivery_institution",
        ])

    logger.info(
        "✅ TransportLoad created/updated for billing %s (load %s)",
        billing_number,
        transport_load.load_number,
    )
