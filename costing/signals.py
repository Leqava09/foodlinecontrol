# costing/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from decimal import Decimal, InvalidOperation
from io import BytesIO
import os
import tempfile
import urllib.parse
from subprocess import run

from django.core.files.base import ContentFile
from django.utils import timezone

from docxtpl import DocxTemplate

from inventory.models import FinishedProductTransaction, PickingSlip
from manufacturing.models import Batch
from commercial.models import CompanyDetails
from .models import BillingDocumentHeader
from costing.models import BatchPriceApproval
from product_details.models import ProductComponent

@receiver(post_save, sender='costing.BillingDocumentHeader')
def auto_create_dispatch_transactions(sender, instance, created, **kwargs):
    '''Auto-create DISPATCH transactions when billing is saved'''
    
    # Skip signal during loaddata (raw=True)
    if kwargs.get('raw', False):
        return
    
    if not created or not instance.qty_for_invoice_data:
        return
    
    # Defer to after transaction commits to avoid database lock
    def create_transactions():
        for batch_number, qty in instance.qty_for_invoice_data.items():
            # Skip if qty is None, empty, null, or zero
            if qty is None or qty == '' or qty == 'null' or str(qty).strip() == '':
                continue
            
            try:
                qty_decimal = Decimal(str(qty))
                
                # Skip zero or negative quantities
                if qty_decimal <= 0:
                    continue
                
                batch = Batch.objects.get(batch_number=batch_number)
                
                # Auto-create DISPATCH transaction (site-scoped to billing's site)
                FinishedProductTransaction.objects.create(
                    site=instance.site,
                    batch=batch,
                    transaction_type='DISPATCH',
                    quantity=qty_decimal,
                    date=instance.billing_date,
                    stock_released=False,
                    stock_released_date=None,
                    client=instance.client,
                    notes=f"Auto-created from Billing {instance.base_number}",
                )
            
            except Batch.DoesNotExist:
                pass
            except (ValueError, TypeError, InvalidOperation):
                pass
    
    transaction.on_commit(create_transactions)


@receiver(post_save, sender=BillingDocumentHeader)
def create_picking_slip_on_billing_save(sender, instance, created, **kwargs):
    """
    Sync PickingSlip with BillingDocumentHeader.create_picking_slip.
    - If checkbox False → delete any existing PickingSlip.
    - If checkbox True  → generate/update PDF and PickingSlip.
    Uses transaction.on_commit() to avoid database lock issues with SQLite.
    """
    # Skip signal during loaddata (raw=True)
    if kwargs.get('raw', False):
        return
    
    from inventory.models import PickingSlip

    # 1) If unchecked: remove picking slip and stop (this is quick, can run inline)
    if not instance.create_picking_slip:
        def delete_picking_slip():
            PickingSlip.objects.filter(billing=instance).delete()
        transaction.on_commit(delete_picking_slip)
        return

    # 2) If checked: generate/update PDF (deferred to after transaction commits)
    # Store instance pk to refetch fresh data after commit
    instance_pk = instance.pk
    
    def generate_picking_slip():
        # Refetch instance to ensure we have fresh data after transaction commit
        try:
            billing_instance = BillingDocumentHeader.objects.get(pk=instance_pk)
        except BillingDocumentHeader.DoesNotExist:
            return
        
        # For multi-tenant isolation: ALWAYS determine company from site (ignore stored company field)
        # This ensures existing records with wrong company values still use correct templates
        if billing_instance.site:
            company = CompanyDetails.objects.filter(site=billing_instance.site, is_active=True).first()
        else:
            # HQ documents (site=NULL) use HQ company (site__isnull=True)
            company = CompanyDetails.objects.filter(site__isnull=True, is_active=True).first()
        
        if not company or not company.billing_template:
            return

        # --------- 1. Build table_rows exactly like billing_document_preview, but doc_type=PICKING ---------
        doc_type_upper = "PICKING"

        # Only use approved prices from batch_costings linked to this billing
        if billing_instance.batch_costings.exists():
            approvals = BatchPriceApproval.objects.filter(
                batch_costing__in=billing_instance.batch_costings.all(),
                is_approved=True,
            ).select_related("batch", "batch__product", "batch_costing")
        else:
            approvals = BatchPriceApproval.objects.none()

        table_rows = []
        total_amount = Decimal("0.00")

        for approval in approvals:
            batch = approval.batch
            product = batch.product

            entered_qty = (
                billing_instance.qty_for_invoice_data.get(batch.batch_number, 0)
                if billing_instance.qty_for_invoice_data
                else 0
            )

            price_per_unit = approval.batch_price_per_unit or Decimal("0.00")

            # Packaging info
            packaging_info = ProductComponent.get_packaging_info(product)

            product_description = batch.product.product_name if batch.product else ""
            product_sku = batch.product.sku if batch.product and batch.product.sku else ""

            display_qty = Decimal(str(entered_qty))
            display_price = price_per_unit

            if billing_instance.bill_per_primary:
                if packaging_info["primary"]:
                    product_description = f"{product_description} - {packaging_info['primary']['name']}"
                display_qty = Decimal(str(entered_qty))
                display_price = price_per_unit

            elif billing_instance.bill_per_secondary:
                if packaging_info["primary"] and packaging_info["secondary"]:
                    primary_usage = Decimal(str(packaging_info["primary"]["usage_per_pallet"]))
                    secondary_usage_per_pallet = Decimal(str(packaging_info["secondary"]["usage_per_pallet"]))
                    pouches_per_box = primary_usage / secondary_usage_per_pallet
                    product_description = f"{product_description} - {packaging_info['secondary']['name']}"
                    display_qty = Decimal(str(entered_qty)) / pouches_per_box
                    display_price = price_per_unit * pouches_per_box

            elif billing_instance.bill_per_pallet:
                if packaging_info["primary"] and packaging_info["pallet"]:
                    pouches_per_pallet = Decimal(str(packaging_info["primary"]["usage_per_pallet"]))
                    product_description = f"{product_description} - {packaging_info['pallet']['name']}"
                    display_qty = Decimal(str(entered_qty)) / pouches_per_pallet
                    display_price = price_per_unit * pouches_per_pallet

            # For picking slip we still compute line_total in case template needs it
            line_total = Decimal(str(entered_qty)) * price_per_unit
            total_amount += line_total

            table_rows.append(
                {
                    "batch_number": batch.batch_number,
                    "sku": product_sku,
                    "product": product_description,
                    "size": batch.size or "",
                    "qty": f"{display_qty:.2f}",
                }
            )

        # --------- 2. Build context (subset of billing_document_preview) ---------
        
        client = billing_instance.client
        
        company_address = ""
        if company:
            address_parts = [
                company.address_line1,
                company.address_line2,
                company.city,
                company.postal_code,
                company.country,
            ]
            company_address = ", ".join([p for p in address_parts if p])

        context = {
            "company_name": company.name if company else "",
            "company_legal_name": company.legal_name if company else "",
            "company_address_line1": company.address_line1 if company else "",
            "company_address_line2": company.address_line2 if company else "",
            "company_city": company.city if company else "",
            "company_province": company.province if company else "",
            "company_postal_code": company.postal_code if company else "",
            "company_country": company.country if company else "",
            "company_address": company_address,
            "company_phone": company.phone if company else "",
            "company_email": company.email if company else "",
            "company_vat_number": company.vat_number if company else "",
            "company_registration_number": company.registration_number if company else "",
            "bank_name": company.bank_name if company else "",
            "bank_account_name": company.bank_account_name if company else "",
            "bank_account_number": company.bank_account_number if company else "",
            "bank_branch_code": company.bank_branch_code if company else "",
            "client_legal_name": client.legal_name if client else "",
            "client_address_line1": client.address_line1 if client else "",
            "client_address_line2": client.address_line2 if client else "",
            "client_city": client.city if client else "",
            "client_province": client.province if client else "",
            "client_postal_code": client.postal_code if client else "",
            "client_country": client.country if client else "",
            "client_vat_number": client.vat_number if client else "",
            "client_payment_terms": client.payment_terms if client else "",
            "client_contact_person": client.contact_person if client else "",
            "client_phone": client.phone if client else "",
            "client_email": client.email if client else "",
            "delivery_address_line1": "",
            "delivery_address_line2": "",
            "delivery_city": "",
            "delivery_province": "",
            "delivery_postal_code": "",
            "delivery_country": "",
            "document_type": "Picking Slip",
            "document_prefix": "PS",
            "document_number": f"PS {billing_instance.base_number}",
            "date": billing_instance.billing_date.strftime("%d %B %Y") if billing_instance.billing_date else "",
            "due_date": billing_instance.due_date.strftime("%d %B %Y") if billing_instance.due_date else "",
            # For picking slip we usually hide prices, so leave these blank:
            "currency": "",
            "transport_cost": "",
            "table_rows": table_rows,
            "sub_total": "",
            "total_amount": "",
            "total_tax": "",
            "total_incl_tax": "",
        }

        # --------- 3. Render DOCX and convert to PDF (same as billing_document_preview) ---------
        try:
            from inventory.views import fix_docx_jinja_tags
            fixed_template_path = fix_docx_jinja_tags(company.billing_template.path)
            doc = DocxTemplate(fixed_template_path)
            doc.render(context)

            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_docx:
                docx_path = tmp_docx.name
                doc.save(docx_path)

            pdf_path = docx_path.replace(".docx", ".pdf")
            libreoffice_path = r"C:\Program Files\LibreOffice\program\soffice.exe"

            cmd = [
                libreoffice_path,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                os.path.dirname(pdf_path),
                docx_path,
            ]
            result = run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                os.unlink(docx_path)
                return

            with open(pdf_path, "rb") as pdf_file:
                pdf_content = pdf_file.read()

            os.unlink(docx_path)
            os.unlink(pdf_path)

            # --------- 4. Save PDF into PickingSlip model ---------
            picking_slip, _ = PickingSlip.objects.update_or_create(
                billing=billing_instance,
                defaults={
                    "site": billing_instance.site,
                    "billing_date": billing_instance.billing_date,
                    "due_date": billing_instance.due_date,
                },
            )

            filename = f"picking_slip_{billing_instance.base_number}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            picking_slip.picking_slip_pdf.save(
                filename,
                ContentFile(pdf_content),
                save=True,
            )

        except Exception:
            pass
    
    # Defer heavy PDF generation until after transaction commits
    transaction.on_commit(generate_picking_slip)


def _next_hq_load_number():
    """Generate next HQ load number (HQ-LOAD-001, HQ-LOAD-002, etc.)"""
    from transport.models import TransportLoad
    import re
    
    # Find highest HQ load number
    hq_loads = TransportLoad.objects.filter(
        site__isnull=True,
        load_number__startswith='HQ-LOAD-'
    ).values_list('load_number', flat=True)
    
    max_num = 0
    for load_num in hq_loads:
        match = re.search(r'HQ-LOAD-(\d+)', load_num)
        if match:
            num = int(match.group(1))
            if num > max_num:
                max_num = num
    
    return f"HQ-LOAD-{max_num + 1:03d}"


@receiver(post_save, sender=BillingDocumentHeader)
def create_hq_transport_on_dispatched(sender, instance, created, **kwargs):
    """
    When HQ BillingDocumentHeader is marked dispatched=True:
    - Create TransportLoad for HQ (site=NULL)
    - If imported from site, copy import tracking info
    - Use HQ load number format (HQ-LOAD-001)
    
    When dispatched=False:
    - Remove TransportLoad
    """
    # Skip signal during loaddata (raw=True)
    if kwargs.get('raw', False):
        return
    
    # Only for HQ billing documents (site=NULL)
    if instance.site is not None:
        return
    
    # Store billing pk to refetch after commit
    billing_pk = instance.pk
    dispatched_status = instance.dispatched
    
    def process_transport():
        # Refetch billing to ensure we have committed data
        try:
            billing = BillingDocumentHeader.objects.get(pk=billing_pk)
        except BillingDocumentHeader.DoesNotExist:
            return
        
        print(f"🔔 HQ Transport Signal: Billing {billing.base_number}, dispatched={billing.dispatched}")
        
        from transport.models import TransportLoad
        from costing.models import BatchCosting, BatchPriceApproval
        
        # If dispatched is FALSE, remove TransportLoad
        if not dispatched_status:
            deleted_count = TransportLoad.objects.filter(billing_document=billing).delete()[0]
            print(f"❌ Removed {deleted_count} transport loads for billing {billing.base_number}")
            return
        
        print(f"✅ Creating transport load for billing {billing.base_number}...")
        
        # Build batch_data based on billing type
        batch_data = []
        
        # Check if Direct Billing or Imported Billing
        if billing.import_source_site:
            # === IMPORTED BILLING: Extract from qty_for_invoice_data ===
            if billing.qty_for_invoice_data:
                # Extract qty_mapping from the nested structure - it contains batch_number: qty pairs
                qty_mapping = billing.qty_for_invoice_data.get('qty_mapping', {}) if isinstance(billing.qty_for_invoice_data, dict) else billing.qty_for_invoice_data
                
                for batch_number, qty in qty_mapping.items() if isinstance(qty_mapping, dict) else billing.qty_for_invoice_data.items():
                    if qty is None or qty == '' or qty == 'null' or str(qty).strip() == '':
                        continue
                    
                    try:
                        qty_decimal = Decimal(str(qty))
                        if qty_decimal <= 0:
                            continue
                        
                        # Try to find batch (may not exist in HQ if imported)
                        try:
                            batch = Batch.objects.get(batch_number=batch_number)
                            
                            # Try to find price
                            batch_costing = None
                            if batch.production:
                                batch_costing = BatchCosting.objects.filter(production_date=batch.production).first()
                            
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
                        except Batch.DoesNotExist:
                            # Batch doesn't exist in HQ (imported) - add minimal data
                            batch_data.append({
                                "batch_number": batch_number,
                                "product": "",
                                "size": "",
                                "production_date": "",
                                "qty_for_invoice": float(qty),
                                "price_per_unit": 0,
                            })
                    except (ValueError, TypeError, InvalidOperation):
                        continue
        else:
            # === DIRECT BILLING: Extract from BillingLineItem records ===
            from costing.models import BillingLineItem
            
            line_items = BillingLineItem.objects.filter(billing_document=billing).select_related('batch', 'batch__product', 'batch__production')
            
            for line_item in line_items:
                batch = line_item.batch
                if not batch:
                    continue
                
                qty = line_item.qty_for_invoice or 0
                if qty <= 0:
                    continue
                
                # Try to find price
                batch_costing = None
                if batch.production:
                    batch_costing = BatchCosting.objects.filter(production_date=batch.production).first()
                
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
        
        # Check if TransportLoad already exists
        transport_load = TransportLoad.objects.filter(billing_document=billing).first()
        
        if not transport_load:
            # Create new HQ transport load
            load_number = _next_hq_load_number()
            
            transport_load = TransportLoad.objects.create(
                site=None,  # HQ transport
                billing_document=billing,
                client=billing.client,
                delivery_institution=billing.delivery_institution,
                billing_date=billing.billing_date,
                released_date=billing.billing_date,  # Use billing date as release date for HQ
                transport_cost=billing.transport_cost or Decimal("0"),
                transporter=billing.transporters,
                batch_data=batch_data,
                load_number=load_number,
                date_loaded=billing.billing_date,
                # Copy import tracking if billing was imported
                import_source_site=billing.import_source_site,
                import_source_load_number=None,  # Will be set if we can find it
            )
            
            # If billing was imported from site, try to find the original transport load
            if billing.import_source_site and billing.import_source_invoice_number:
                try:
                    # Find transport load from source site with matching billing document
                    site_transport = TransportLoad.objects.filter(
                        site=billing.import_source_site,
                        billing_document__base_number=billing.import_source_invoice_number
                    ).first()
                    
                    if site_transport:
                        transport_load.import_source_load_number = site_transport.load_number
                        transport_load.save(update_fields=['import_source_load_number'])
                        print(f"📍 Linked to site transport: {billing.import_source_site.name} Load {site_transport.load_number}")
                except Exception as e:
                    print(f"⚠️ Could not find site transport: {e}")
            
            print(f"✅ Created HQ transport load {load_number} for billing {billing.base_number}")
        else:
            print(f"🔄 Updating existing transport load for billing {billing.base_number}")
            transport_load.billing_date = billing.billing_date
            transport_load.released_date = billing.billing_date
            transport_load.date_loaded = billing.billing_date
            transport_load.transport_cost = billing.transport_cost or transport_load.transport_cost
            transport_load.transporter = billing.transporters
            transport_load.batch_data = batch_data
            transport_load.client = billing.client
            transport_load.delivery_institution = billing.delivery_institution
            transport_load.import_source_site = billing.import_source_site
            
            # Update import source load number if billing was imported
            if billing.import_source_site and billing.import_source_invoice_number:
                try:
                    site_transport = TransportLoad.objects.filter(
                        site=billing.import_source_site,
                        billing_document__base_number=billing.import_source_invoice_number
                    ).first()
                    
                    if site_transport:
                        transport_load.import_source_load_number = site_transport.load_number
                except:
                    pass
            
            transport_load.save(update_fields=[
                "billing_date",
                "released_date",
                "transport_cost",
                "transporter",
                "batch_data",
                "date_loaded",
                "client",
                "delivery_institution",
                "import_source_site",
                "import_source_load_number",
            ])
            print(f"✅ Updated transport load {transport_load.load_number} for billing {billing.base_number}")
    
    # Use transaction.on_commit to defer transport creation until billing is committed
    transaction.on_commit(process_transport)
