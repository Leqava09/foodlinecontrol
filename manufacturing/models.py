from django.db import models
from decimal import Decimal
from smart_selects.db_fields import ChainedForeignKey
from product_details.models import Product, ProductCategory
from simple_history.models import HistoricalRecords

class Production(models.Model):
    """
    Production header - groups batches by production date
    """
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.PROTECT,
        related_name='productions',
        null=True,
        blank=True,
        help_text="Manufacturing site for this production"
    )
    production_date = models.DateField(verbose_name="Production Date")
    expiry_date = models.DateField(verbose_name="Expiry Date", blank=True, null=True, editable=False)
    is_archived = models.BooleanField(default=False, db_index=True)
    
    class Meta:
        verbose_name = "Production"
        verbose_name_plural = "Production"
        ordering = ['-production_date']
        unique_together = [['site', 'production_date']]  # Unique per site

    def save(self, *args, **kwargs):
        from dateutil.relativedelta import relativedelta
        if self.production_date:
            self.expiry_date = self.production_date + relativedelta(years=3)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Production {self.production_date.strftime('%d/%m/%Y')}"

class Batch(models.Model):
    STATUS_CHOICES = [
        ('Manufactured', 'Manufactured'),
        ('In Incubation', 'In Incubation'),
        ('Awaiting Certification', 'Awaiting Certification'),
        ('Certified', 'Certified'),
        ('Ready for Dispatch', 'Ready for Dispatch'),
        ('Dispatched', 'Dispatched'),
        ('Failed Drainmass', 'Failed Drainmass'),
        ('Failed 37°C Micro Test', 'Failed 37°C Micro Test'),
        ('Failed 55°C Micro Test', 'Failed 55°C Micro Test'),
    ]
    
    # ✅ PRIMARY KEY: auto-incrementing id
    id = models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')
    
    # Batch number - unique per site via application validation
    batch_number = models.CharField(max_length=150, verbose_name="Production Code")
    
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.PROTECT,
        related_name='batches',
        null=True,
        blank=True,
        help_text="Manufacturing site for this batch"
    )
    
    size = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Size"
    )

    sku = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="SKU"
    )

    production = models.ForeignKey(
        Production,
        on_delete=models.SET_NULL,  # ✅ Allow deletion, set to NULL (fixes HistoricalBatch FK constraint)
        related_name='batch_items',
        verbose_name="Production",
        null=True,  
        blank=True  
    )
    production_date = models.DateField(verbose_name="Production Date", null=True, blank=True) 
    a_no = models.CharField(max_length=100, blank=True, verbose_name="A-NO")
    expiry_date = models.DateField(blank=True, null=True, verbose_name="Expiry Date", editable=False)
    category = models.ForeignKey(
        ProductCategory,
        on_delete=models.PROTECT,
        verbose_name="Category",
        null=True,
        blank=True
    )
    product = ChainedForeignKey(
        Product,
        chained_field="category",
        chained_model_field="category",
        show_all=False,
        auto_choose=True,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Product Name"
    )
    
    shift_total = models.IntegerField(default=0, verbose_name="Shift Total")
    incubation_start = models.DateField(blank=True, null=True, verbose_name="Incubation Start")
    incubation_end = models.DateField(blank=True, null=True, verbose_name="Incubation End")
    certification_date = models.DateField(blank=True, null=True, verbose_name="Certification Date")
    dispatch_date = models.DateField(blank=True, null=True, verbose_name="Dispatch Date")
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Manufactured', verbose_name="Status")
    nsi_submission_date = models.DateField(blank=True, null=True, verbose_name="NSI Submission Date")
    
    def get_formatted_status(self):
        """Return status with underscores removed and properly formatted"""
        if not self.status:
            return 'N/A'
        # Replace underscore with space and apply title case
        text = str(self.status).replace('_', ' ').replace('-', ' ')
        return text.title()
    
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Production Batch"
        verbose_name_plural = "Production Batches"
        constraints = [
            models.UniqueConstraint(fields=['site', 'batch_number'], name='unique_batch_number_per_site')
        ]
        # Note: Unique constraint defined above for Django's model state
        # However, it cannot be enforced at DB level due to existing duplicate data
        # Uniqueness is validated at application level via the clean() method below

    def clean(self):
        """Validate batch_number is unique within the same site"""
        from django.core.exceptions import ValidationError
        
        if not self.batch_number or not self.site:
            return  # Skip validation if missing required fields
        
        # Check if this batch_number already exists in the same site (excluding current instance if editing)
        query = Batch.objects.filter(
            batch_number=self.batch_number,
            site=self.site
        )
        
        # When editing, exclude the current batch by id
        if self.id:
            query = query.exclude(id=self.id)
        
        if query.exists():
            raise ValidationError(
                f"Production Code '{self.batch_number}' already exists for site '{self.site.name}'. "
                f"Please use a different Production Code or select a different site."
            )

    def save(self, *args, **kwargs):
        from dateutil.relativedelta import relativedelta
        if self.production_date:
            # Expiry date
            self.expiry_date = self.production_date + relativedelta(years=3)
        
            # Incubation Start = Production Date + 1 day
            if not self.incubation_start:
                self.incubation_start = self.production_date + relativedelta(days=1)
        
            # Incubation End = Incubation Start + 14 days
            if self.incubation_start and not self.incubation_end:
                self.incubation_end = self.incubation_start + relativedelta(days=14)
        
            # NSI Sub Date = same as Incubation End
            if self.incubation_end and not self.nsi_submission_date:
                self.nsi_submission_date = self.incubation_end
        
            # Auto-create/get Production record (handle duplicates gracefully)
            if self.site:
                # Use filter().first() to avoid MultipleObjectsReturned error
                production = Production.objects.filter(
                    production_date=self.production_date,
                    site=self.site
                ).first()
                
                # If doesn't exist, create it
                if not production:
                    production = Production.objects.create(
                        production_date=self.production_date,
                        site=self.site
                    )
            else:
                # Fallback for no site
                production = Production.objects.filter(
                    production_date=self.production_date
                ).first()
                if not production:
                    production = Production.objects.create(
                        production_date=self.production_date
                    )
            
            self.production = production
    
        super().save(*args, **kwargs)

    def __str__(self):
        return self.batch_number
        
    def get_ready_to_dispatch(self):
        """Calculate ready-to-dispatch using same logic as batch_ready_dispatch_api"""
        from decimal import Decimal
        
        shift_total = Decimal(str(self.shift_total or 0))
        
        master_waste = Waste.objects.filter(
            batch__production_date=self.production_date
        ).order_by('pk').first()
        
        if not master_waste:
            return shift_total
        
        key = self.batch_number
        
        nsi_dict = master_waste.nsi_sample_per_batch or {}
        retention_dict = master_waste.retention_sample_per_batch or {}
        unclear_dict = master_waste.unclear_coding_per_batch or {}
        
        if not isinstance(nsi_dict, dict):
            nsi_dict = {}
        if not isinstance(retention_dict, dict):
            retention_dict = {}
        if not isinstance(unclear_dict, dict):
            unclear_dict = {}
        
        nsi = Decimal(str(nsi_dict.get(key, 0) or 0))
        retention = Decimal(str(retention_dict.get(key, 0) or 0))
        unclear = Decimal(str(unclear_dict.get(key, 0) or 0))
        
        ready = max(Decimal('0'), shift_total - nsi - retention - unclear)
        
        return ready

    class Meta:
        # ✅ Allow same batch_number across different sites
        constraints = [
            models.UniqueConstraint(fields=['site', 'batch_number'], name='unique_batch_number_per_site'),
        ]

class NSIDocument(models.Model):
    batch = models.ForeignKey(
        Batch,
        on_delete=models.CASCADE,
        related_name='nsi_documents'
    )
    file = models.FileField(
        upload_to='manufacturing/nsi_documents/',
        verbose_name="NSI Document (PDF)"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"NSI Document for {self.batch.batch_number}"


class Waste(models.Model):
    production_date = models.DateField(verbose_name="Production Date", primary_key=False)
    batch = models.OneToOneField(
        Batch,
        on_delete=models.CASCADE,
        related_name='pouch_waste',
        verbose_name="Batch",
        null=True,
        blank=True
    )
    nsi_sample_per_batch = models.JSONField(default=dict, blank=True, verbose_name="NSI Sample Per Batch")
    retention_sample_per_batch = models.JSONField(default=dict, blank=True, verbose_name="Retention Sample Per Batch")
    unclear_coding_per_batch = models.JSONField(default=dict, blank=True, verbose_name="Unclear Coding Per Batch")
    machine_count = models.IntegerField(default=0, verbose_name="Machine Count")
    seal_creeps = models.IntegerField(default=0, verbose_name="Seal Creeps")
    unsealed_poor_seal = models.IntegerField(default=0, verbose_name="Unsealed/Poor Seal")
    screwed_and_undated = models.IntegerField(default=0, verbose_name="Screwed and Undated")
    over_weight = models.IntegerField(default=0, verbose_name="Over Weight")
    under_weight = models.IntegerField(default=0, verbose_name="Under Weight")
    empty_pouches = models.IntegerField(default=0, verbose_name="Empty Pouches")
    metal_detection = models.IntegerField(default=0, verbose_name="Metal Detection")
    machine_waste_total = models.IntegerField(default=0, verbose_name="Machine Waste Total", editable=False)
    retort_count = models.IntegerField(default=0, verbose_name="Retort Count")
    damage_boxes = models.IntegerField(default=0, verbose_name="Damage Boxes")
    unclear_coding = models.IntegerField(default=0, verbose_name="Unclear Coding")
    total_unclear_coding = models.IntegerField(default=0, verbose_name="Total Unclear Coding")
    retort_seal_creap = models.IntegerField(default=0, verbose_name="Seal Creap")
    retort_under_weight = models.IntegerField(default=0, verbose_name="Under Weight")
    poor_ceiling_destroyed = models.IntegerField(default=0, verbose_name="Poor Ceiling Destroyed")
    retort_waste_total = models.IntegerField(default=0, verbose_name="Retort Waste Total", editable=False)
    filling_sheet = models.FileField(upload_to='sheets/', blank=True, null=True, verbose_name="Filling Sheet")
    retort_sheet = models.FileField(upload_to='sheets/', blank=True, null=True, verbose_name="Retort Sheet")
    pouches_withdrawn = models.IntegerField(default=0, verbose_name="Pouches Withdrawn")
    total_returned = models.IntegerField(default=0, verbose_name="Total Returned")
    balance_pouches = models.IntegerField(default=0, verbose_name="Balance Pouches", editable=False)
    packed = models.IntegerField(default=0, verbose_name="Packed")
    nsi_sample_pouches = models.IntegerField(default=0, verbose_name="NSI Sample Pouches")
    pouches_packed = models.IntegerField(default=0, verbose_name="Pouches Packed")
    pallets_packed = models.IntegerField(default=0, verbose_name="Pallets Packed")
    boxes_packed = models.IntegerField(default=0, verbose_name="Boxes Packed")
    retention_sample_qty = models.IntegerField(default=0, verbose_name="Retention Sample QTY")
    nsi_sample_log = models.FileField(upload_to='nsi/', blank=True, null=True, verbose_name="NSI Sample Log")
    final_product_packaging = models.FileField(upload_to='packaging/', blank=True, null=True, verbose_name="Final Product Packaging")
    total_down_time = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Total Down Time (Hours)")
    reasons_for_down_time = models.TextField(blank=True, null=True, verbose_name="Reasons for Down Time")
    
    machine_production_documents = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Machine Production Documents",
    )
    
    retort_control_documents = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Retort Control Sheet Documents",
    )
    
    nsi_sample_log_documents = models.JSONField(
        default=list,
        blank=True,
        verbose_name="NSI Sample Log Documents",
    )
    final_product_packaging_documents = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Final Product Packaging Documents",
    )
    inventory_book_out_documents = models.JSONField(
        default=dict,  
        blank=True,
        verbose_name="Inventory Book Out Sheet",
    )
    
    machine_production_document = models.FileField(upload_to='pouch_docs/', blank=True, null=True, verbose_name="Machine Production Document")
    retort_control_sheet = models.FileField(upload_to='pouch_docs/', blank=True, null=True, verbose_name="Retort Control Sheet")
    
    class Meta:
        verbose_name = "Pouch Waste"
        verbose_name_plural = "Pouch Waste Records"

    def save(self, *args, **kwargs):
        self.machine_waste_total = (
            self.seal_creeps + self.unsealed_poor_seal + self.screwed_and_undated +
            self.over_weight + self.under_weight + self.empty_pouches + self.metal_detection
        )
        self.retort_waste_total = (
            self.damage_boxes + self.unclear_coding + self.retort_seal_creap +
            self.retort_under_weight + self.poor_ceiling_destroyed
        )
        self.balance_pouches = self.pouches_withdrawn - self.total_returned
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Pouch Waste for {self.batch.batch_number if self.batch else self.production_date}"

from django.db import models
from django.core.exceptions import ValidationError
from datetime import date

class BatchContainer(models.Model):
    production_date = models.DateField()  
    container = models.ForeignKey(
        'inventory.Container',
        on_delete=models.CASCADE,
        related_name='container_production_dates',
        null=True, 
        blank=True  
    )
    kg_frozen_meat_used = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Kg Frozen Meat Used"
    )
    meat_filled = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Meat Filled (kg)"
    )
    container_waste = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Container Waste (kg)"
    )
    waste_factor = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, verbose_name="Waste Factor (%)"
    )
    defrost_sheet = models.FileField(upload_to='batch_documents/defrost/', null=True, blank=True, verbose_name="Defrost Sheet")
    batch_ref = models.CharField(max_length=100, null=True, blank=True, verbose_name="Batch Reference")  
    
    book_out_qty = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, null=True, blank=True,
        verbose_name="Book Out Qty (kg)"
    )
    stock_left = models.DecimalField(max_digits=10, decimal_places=2, default=0)  
    balance_from_prev_shift = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name="Balance from Previous Shift (kg)"
    )
    source_type = models.CharField(
        max_length=10,
        choices=[('import', 'Import'), ('local', 'Local')],
        default='import',
        verbose_name="Source Type"
    )
    
    class Meta:
        unique_together = ('production_date', 'container')
        verbose_name = "Production Container Usage"
        verbose_name_plural = "Production Container Usage"
    
    def __str__(self):
        return f"{self.production_date} - {self.container.container_number} ({self.kg_frozen_meat_used} kg)"
 
    def clean(self):
        """✅ SAFETY CHECK: Validate all critical fields"""
        
        if self.production_date:
            if not isinstance(self.production_date, date):
                raise ValidationError(
                    f"Production date must be a valid date, got {type(self.production_date)}"
                )
        
        if not self.container or self.kg_frozen_meat_used is None:
            return
        
        net_weight = self.container.net_weight
        used_qs = BatchContainer.objects.filter(container=self.container)
        if self.pk:
            used_qs = used_qs.exclude(pk=self.pk)
        
        total_used = (used_qs.aggregate(total=models.Sum('kg_frozen_meat_used'))['total'] or 0) + (self.kg_frozen_meat_used or 0)
        if total_used > net_weight:
            raise ValidationError(f"Total frozen meat used ({total_used:.2f}) exceeds net weight of this container ({net_weight:.2f})!")
    
    def save(self, *args, **kwargs):
        """✅ FORCE VALIDATION before saving to database"""
        self.clean()
        super().save(*args, **kwargs)

class DefrostDocument(models.Model):
    batch_container = models.ForeignKey(
        BatchContainer,
        on_delete=models.CASCADE,
        related_name='defrost_documents'
    )
    file = models.FileField(
        upload_to='manufacturing/defrost_sheets/',
        verbose_name="Defrost Sheet"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Defrost sheet for {self.batch_container.container or self.batch_container.batch_ref}"

class MeatWaste(models.Model):
    production_date = models.DateField(verbose_name="Production Date", primary_key=False)
    batch = models.OneToOneField(
        Batch,
        on_delete=models.CASCADE,
        related_name='meat_waste',
        verbose_name="Batch",
        null=True,
        blank=True
    )
    total_meat_defrosted = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Total Meat Defrosted (kg)")
    meat_waste = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Meat Waste (kg)")

    class Meta:
        verbose_name = "Meat Waste"
        verbose_name_plural = "Meat Waste Records"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Meat Waste for {self.batch.batch_number if self.batch else self.production_date}"


class ProductionDateDocument(models.Model):
    production_date = models.DateField(verbose_name="Production Date")
    file = models.FileField(upload_to='manufacturing/production_docs/', verbose_name="Production Document")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Document for {self.production_date} ({self.file.name.split('/')[-1]})"


class BatchProductInventoryUsed(models.Model):
    batch = models.ForeignKey('manufacturing.Batch', on_delete=models.CASCADE, related_name='product_inventory_used')
    product = models.ForeignKey('product_details.Product', on_delete=models.SET_NULL, null=True, blank=True)
    stock_item = models.ForeignKey('inventory.StockItem', on_delete=models.SET_NULL, null=True, blank=True)
    is_packaging = models.BooleanField(default=False)
    qty_used = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    waste_qty = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    ref_number = models.CharField(max_length=100, blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from inventory.models import StockTransaction
        if self.batch and self.stock_item:
            StockTransaction.objects.update_or_create(
                batch=self.batch,
                stock_item=self.stock_item,
                transaction_type='OUT',
                batch_ref=self.ref_number,
                defaults={
                    'quantity': self.qty_used + self.waste_qty,
                    'waste_per_production_batch': self.waste_qty,
                    'amount_used': self.qty_used,
                    'category': self.stock_item.category,
                    'transaction_date': self.batch.production_date,
                }
            )

    def unit_of_measure(self):
        return self.stock_item.unit_of_measure if self.stock_item else '-'
    
    def __str__(self):
        return f"{self.batch.batch_number} - {self.stock_item.name}"

class Sauce(models.Model):
    production_date = models.DateField(unique=True)
    opening_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amended_opening_balance = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    amended_reason = models.CharField(max_length=255, blank=True)
    cancel_opening_balance = models.BooleanField(default=False, verbose_name="Cancel Opening Balance")
    sauce_mixed = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    closing_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    reference_file = models.FileField(upload_to='sauce_references/', null=True, blank=True)  # ADD THIS
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    recipe_documents = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Recipe Documents",
    )
    
    class Meta:
        ordering = ['-production_date']
        verbose_name = "Sauce Usage"
        verbose_name_plural = "Sauce Usage"

    def __str__(self):
        return f"Sauce {self.production_date.strftime('%d/%m/%Y')}"

    @property
    def usage_for_day(self):
        """Calculate Usage for Day = Opening/Amended + Mixed - Closing"""
        opening = self.amended_opening_balance if self.amended_opening_balance else self.opening_balance
        return opening + self.sauce_mixed - self.closing_balance

class MeatProductionSummary(models.Model):
    production_date = models.DateField(verbose_name="Production Date", unique=True)
    total_meat_filled = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, 
        verbose_name="Total Meat Filled (kg)"
    )
    total_waste = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, 
        verbose_name="Total Waste (kg)"
    )
    filling_weight_sheet = models.FileField(
        upload_to='batch_documents/filling_weight/',
        null=True, blank=True,
        verbose_name="Filling Weight Sheet"
    )
    filling_weight_per_pouch = models.DecimalField(
        max_digits=5, decimal_places=3, default=0.277,
        null=True, blank=True,
        verbose_name="Filling Weight per Pouch (kg)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Meat Production Summary"
        verbose_name_plural = "Meat Production Summaries"
        ordering = ['-production_date']

    def __str__(self):
        return f"Meat Summary - {self.production_date.strftime('%d/%m/%Y')}"

class ProductionSummaryItem(models.Model):
    """
    Captures Summary data shown in the batch detail Summary tab.
    Aggregates data from:
    - Main product components (meat)
    - Product components (packaging)
    - Recipe items (sauce/ingredients)
    """
    production_date = models.DateField(verbose_name="Production Date")
    stock_item = models.ForeignKey(
        'inventory.StockItem',
        on_delete=models.CASCADE,
        related_name='production_summaries'
    )
    component_type = models.CharField(
        max_length=20,
        choices=[
            ('main', 'Main Component (Meat)'),
            ('component', 'Product Component (Packaging)'),
            ('recipe', 'Recipe Item (Sauce)'),
        ],
        verbose_name="Component Type"
    )
    ideal = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=0,
        verbose_name="Ideal (Supposed Usage)"
    )
    used = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=0,
        verbose_name="Used (Actual)"
    )
    difference = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=0,
        verbose_name="Difference (Ideal - Used)"
    )
    batch_ref = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Batch Reference"
    )
    
    class Meta:
        unique_together = ('production_date', 'stock_item', 'component_type')
        verbose_name = "Production Summary Item"
        verbose_name_plural = "Production Summary Items"
        ordering = ['production_date', 'component_type', 'stock_item__name']
        indexes = [
            models.Index(fields=['production_date', 'stock_item']),
        ]
    
    def __str__(self):
        return f"{self.production_date} - {self.get_component_type_display()} - {self.stock_item.name}"


class BatchComponentSnapshot(models.Model):
    """
    Snapshot of product component usage values at the time of batch creation.
    This preserves the standard_usage_per_production_unit values so that
    if product details change, existing batches keep their original values.
    """
    COMPONENT_TYPE_CHOICES = [
        ('component', 'Product Component (Packaging)'),
        ('main', 'Main Component (Meat)'),
        ('recipe', 'Recipe Item (Sauce)'),
    ]
    
    batch = models.ForeignKey(
        'manufacturing.Batch',
        on_delete=models.CASCADE,
        related_name='component_snapshots',
        verbose_name="Batch"
    )
    stock_item = models.ForeignKey(
        'inventory.StockItem',
        on_delete=models.CASCADE,
        related_name='batch_snapshots',
        verbose_name="Stock Item"
    )
    component_type = models.CharField(
        max_length=20,
        choices=COMPONENT_TYPE_CHOICES,
        verbose_name="Component Type"
    )
    standard_usage_per_production_unit = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=0,
        verbose_name="Standard Usage per Production Unit (Snapshot)"
    )
    usage_per_pallet = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Usage per Pallet (Snapshot)"
    )
    is_primary_packaging = models.BooleanField(default=False)
    is_secondary_packaging = models.BooleanField(default=False)
    is_pallet = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('batch', 'stock_item', 'component_type')
        verbose_name = "Batch Component Snapshot"
        verbose_name_plural = "Batch Component Snapshots"
        ordering = ['batch', 'component_type', 'stock_item']
        indexes = [
            models.Index(fields=['batch', 'stock_item']),
        ]
    
    def __str__(self):
        return f"{self.batch.batch_number} - {self.stock_item.name} ({self.get_component_type_display()})"
    
    @classmethod
    def create_snapshots_for_batch(cls, batch):
        """
        Create component snapshots for a batch based on its product's current components.
        Only creates if snapshots don't already exist for this batch.
        """
        if not batch.product:
            return []
        
        # Check if snapshots already exist
        if cls.objects.filter(batch=batch).exists():
            return []
        
        snapshots = []
        
        # 1. Product Components (packaging)
        for comp in batch.product.components.all():
            if comp.stock_item:
                snapshot = cls(
                    batch=batch,
                    stock_item=comp.stock_item,
                    component_type='component',
                    standard_usage_per_production_unit=comp.standard_usage_per_production_unit or Decimal('0'),
                    usage_per_pallet=comp.usage_per_pallet,
                    is_primary_packaging=comp.is_primary_packaging,
                    is_secondary_packaging=comp.is_secondary_packaging,
                    is_pallet=comp.is_pallet,
                )
                snapshots.append(snapshot)
        
        # 2. Main Product Components (meat)
        for main_comp in batch.product.main_product_components.all():
            if main_comp.stock_item:
                snapshot = cls(
                    batch=batch,
                    stock_item=main_comp.stock_item,
                    component_type='main',
                    standard_usage_per_production_unit=main_comp.standard_usage_per_production_unit or Decimal('0'),
                )
                snapshots.append(snapshot)
        
        # 3. Recipe Items (sauce ingredients)
        for recipe in batch.product.recipes.all():
            for item in recipe.items.all():
                if item.stock_item:
                    snapshot = cls(
                        batch=batch,
                        stock_item=item.stock_item,
                        component_type='recipe',
                        standard_usage_per_production_unit=item.standard_usage_per_production_unit or Decimal('0'),
                    )
                    snapshots.append(snapshot)
        
        # Bulk create all snapshots
        if snapshots:
            cls.objects.bulk_create(snapshots, ignore_conflicts=True)
        
        return snapshots
    
    @classmethod
    def get_usage_for_batch(cls, batch, stock_item, component_type=None):
        """
        Get the snapshotted usage value for a batch/stock_item.
        Returns None if no snapshot exists (caller should fall back to current value).
        """
        qs = cls.objects.filter(batch=batch, stock_item=stock_item)
        if component_type:
            qs = qs.filter(component_type=component_type)
        snapshot = qs.first()
        return snapshot.standard_usage_per_production_unit if snapshot else None
        

class ManufacturingReport(Batch):
    """
    Proxy model for Manufacturing Report view.
    Shows aggregated batch certification status and dates.
    """
    class Meta:
        proxy = True
        verbose_name = "Manufacturing Report"
        verbose_name_plural = "Manufacturing Report"


class StockUsageReport(Batch):
    """
    Proxy model for Stock Usage Report view.
    Shows main stock item (Meat/Beans) usage per container with loss calculations.
    Aggregates: batch ref, book in qty, % loss from frozen, % loss from pouch, total losses.
    """
    class Meta:
        proxy = True
        verbose_name = "Stock Usage Report"
        verbose_name_plural = "Stock Usage Report"
