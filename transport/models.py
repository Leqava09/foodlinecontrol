# transport/models.py

from decimal import Decimal
from django.db import models
from django.utils import timezone
from commercial.models import Transporter, Client
from costing.models import BillingDocumentHeader


class TransportLoad(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        related_name='transport_loads',
        null=True,
        blank=True,
        help_text="Site this transport load belongs to"
    )
    billing_document = models.ForeignKey(
        BillingDocumentHeader,
        on_delete=models.PROTECT,
        related_name="transport_loads",
        verbose_name="Billing Document",
        null=True,
        blank=True,
    )
    client = models.ForeignKey(
        Client,
        on_delete=models.PROTECT,
        related_name="transport_loads",
        verbose_name="Client",
        editable=False,
        null=True,
        blank=True,
    )
    delivery_institution = models.ForeignKey(
        'transport.DeliverySite',
        on_delete=models.SET_NULL,
        related_name="transport_loads",
        verbose_name="Delivery Institution",
        editable=False,
        null=True,
        blank=True,
    )
    billing_date = models.DateField(
        editable=False,
        verbose_name="Billing Date",
        null=True,
        blank=True,
    )
    released_date = models.DateField(
        editable=False,
        verbose_name="Released Date",
        null=True,
        blank=True,
    )
    transport_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        editable=False,
        verbose_name="Transport Cost (R)",
    )
    batch_data = models.JSONField(
        default=dict,
        editable=False,
        verbose_name="Batch Details",
    )
    load_number = models.CharField(
        max_length=50,
        unique=True,
        editable=True,
        verbose_name="Load Number",
        default='',
    )
    
    date_loaded = models.DateField(
        editable=False,
        default=timezone.now,
        verbose_name="Date Loaded",
    )
    
    # ============= DOCUMENTS: MULTIPLE FILES PER TYPE =============
    delivery_note_documents = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Delivery Note Documents",
    )
    
    namra_documents = models.JSONField(
        default=list,
        blank=True,
        verbose_name="NAMRA Documents",
    )
    
    daff_documents = models.JSONField(
        default=list,
        blank=True,
        verbose_name="DAFF Documents",
    )
    
    meat_board_documents = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Meat Board Documents",
    )
    
    import_permit_documents = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Import Permit Documents",
    )
    
    other_documents = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Other Documents",
    )
    
    transporter = models.ForeignKey(
        Transporter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="loads",
        verbose_name="Transporter",
        help_text="Select transporter responsible for delivery"
    )
    
    # Import tracking fields (for HQ imports from sites)
    import_source_site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.SET_NULL,
        related_name='imported_transport_loads',
        null=True,
        blank=True,
        verbose_name="Import Source Site",
        help_text="Site this transport load was imported from (HQ only)"
    )
    import_source_load_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Import Source Load Number",
        help_text="Original load number from source site"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_archived = models.BooleanField(default=False, db_index=True)
    class Meta:
        verbose_name = "Transport Load"
        verbose_name_plural = "Transport Loads"
        ordering = ['-date_loaded', '-load_number']
        indexes = [
            models.Index(fields=['billing_document']),
            models.Index(fields=['load_number']),
            models.Index(fields=['released_date']),
        ]
    
    def __str__(self):
        if self.import_source_site:
            return f"Load {self.load_number} (Import from {self.import_source_site.name} #{self.import_source_load_number})"
        return f"Load {self.load_number}"
    
    def get_batch_summary(self):
        if not self.batch_data:
            return "-"
        
        if not isinstance(self.batch_data, list):
            return "-"
        
        batches = [f"{b['batch_number']}" for b in self.batch_data if 'batch_number' in b]
        return ", ".join(batches) if batches else "-"
    
    def get_total_quantity(self):
        if not self.batch_data or not isinstance(self.batch_data, list):
            return Decimal('0')

        total = sum(
            Decimal(str(b.get('qty_for_invoice', 0)))
            for b in self.batch_data
        )
        return total

    @property
    def load_total_quantity(self):
        return self.get_total_quantity()
       
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        return form
    
    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        context['adminform'].form.auto_id = 'transportload_form_%s'
        return super().render_change_form(request, context, add, change, form_url, obj)

class DeliverySite(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        related_name='delivery_sites',
        null=True,
        blank=True,
        help_text="Site this delivery site belongs to"
    )
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="delivery_sites",
        verbose_name="Client",
    )

    institutionname = models.CharField("Institution name", max_length=255, blank=True)
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True, default="South Africa")

    contact_person = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    
    is_archived = models.BooleanField(default=False, db_index=True)

    class Meta:
        verbose_name = "Delivery site"
        verbose_name_plural = "Delivery sites"

    def __str__(self):
        return self.institutionname or f"{self.client} delivery site"