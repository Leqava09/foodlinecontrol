 # models.py
from django.db import models
from django.core.validators import FileExtensionValidator
from decimal import Decimal
from django.db.models import Sum
from manufacturing.models import Batch
from smart_selects.db_fields import ChainedForeignKey
from django.utils import timezone

class Container(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='containers'
    )
    # Choices
    PAYMENT_TERMS_CHOICES = [
        ('30% Deposit Balance on Arrival', '30% Deposit Balance on Arrival'),
        ('10% Deposit Balance on Arrival', '10% Deposit Balance on Arrival'),
        ('Payment on Arrival', 'Payment on Arrival'),
        ('COD', 'COD'),
        ('30 Days After Arrival', '30 Days After Arrival'),
    ]
    PAYMENT_STATUS_CHOICES = [
        ('Deposit Paid', 'Deposit Paid'),
        ('Unpaid', 'Unpaid'),
        ('Paid', 'Paid'),
    ]
    EXCHANGE_RATE_FROM_CHOICES = [
        ('USD', 'USD ($)'),
        ('EUR', 'EUR (€)'),
        ('NAD', 'NAD (N$)'),
        ('ZAR', 'ZAR (R)'),
    ]
    EXCHANGE_RATE_TO_CHOICES = [
        ('NAD', 'NAD (N$)'),
        ('ZAR', 'ZAR (R)'),
    ]
    CLEARING_CURRENCY_CHOICES = [
        ('ZAR', 'ZAR (R)'),
        ('NAD', 'NAD (N$)'),
    ]
    CONTAINER_STATUS_CHOICES = [
        ('Ordered', 'Ordered'),
        ('Shipped', 'Shipped'),
        ('Docked', 'Docked'),
        ('Available', 'Available'),
        ('Processed', 'Processed'),
    ]
    SHIP_OWNER_CHOICES = [
        ('MSC', 'MSC'),
        ('MAERSK', 'MAERSK'),
        ('HAPAG', 'HAPAG'),
        ('OTHER', 'OTHER'),
    ]
    SOURCE_CHOICES = [
        ('Local', 'Local'),
        ('Import', 'Import'),
    ]
     
    @property
    def price_per_unit_display(self):
        """Calculate price per unit of the stock item"""
        try:
            if not self.stock_item or not self.stock_item.unit_of_measure:
                return "-"
            
            unit_str = str(self.stock_item.unit_of_measure)
            qty = float(self.net_weight or 0)  # Use net_weight as total quantity
            
            if qty <= 0:
                return f"NAD 0.00 per {unit_str}"
            
            # Total cost includes all costs
            total_cost = float(self.total_cost_nad or 0)
            price_per = total_cost / qty
            
            return f"NAD {price_per:,.2f} per {unit_str}"
        except Exception as e:
            return f"Error: {str(e)}"
    
    @property
    def total_cost_display(self):
        """Already have total_cost_nad, but format it for display"""
        try:
            total = float(self.total_cost_nad or 0)
            return f"NAD {total:,.2f}"
        except Exception as e:
            return f"Error: {str(e)}"
            
    @property
    def total_qty_for_booking_in(self):
        """Calculate total qty from packaging config"""
        if self.kg_per_box and self.total_boxes:
            return self.kg_per_box * self.total_boxes
        return self.net_weight or 0        
     
    # Core
    container_number = models.CharField(max_length=50, primary_key=True, verbose_name="Container Number")
    status = models.CharField(max_length=20, choices=CONTAINER_STATUS_CHOICES, default='Ordered', verbose_name="Status")
    etd = models.DateField(blank=True, null=True, verbose_name="ETD")
    eta = models.DateField(blank=True, null=True, verbose_name="ETA")
    booking_in_date = models.DateField(blank=True, null=True, verbose_name="Booking In Date (Site Arrival)")
    expiry_date = models.DateField(blank=True, null=True, verbose_name="Expiry Date")
    authorized_person = models.CharField(max_length=100, blank=True, verbose_name="Authorized Person")
    updated = models.DateTimeField(auto_now=True, verbose_name="Updated Date/Time")
    current_location = models.CharField(max_length=200, blank=True, verbose_name="Current Location")
    next_location = models.CharField(max_length=200, blank=True, verbose_name="Next Location")
 
    # Deposit fields
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Deposit Amount")
    deposit_currency_from = models.CharField(max_length=3, choices=EXCHANGE_RATE_FROM_CHOICES, default='USD', verbose_name="Deposit Currency From")
    deposit_currency_to = models.CharField(max_length=3, choices=EXCHANGE_RATE_TO_CHOICES, default='NAD', verbose_name="Deposit Currency To")
    deposit_exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, default=18.0000, verbose_name="Deposit Exchange Rate")
    deposit_doc = models.FileField(
        upload_to='container_docs/', blank=True, null=True,
        verbose_name="Proforma/Quote/PO",
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png'])],
    )

    # Final payment fields
    final_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Final Payment Amount")
    final_currency_from = models.CharField(max_length=3, choices=EXCHANGE_RATE_FROM_CHOICES, default='USD', verbose_name="Final Payment Currency From")
    final_currency_to = models.CharField(max_length=3, choices=EXCHANGE_RATE_TO_CHOICES, default='NAD', verbose_name="Final Payment Currency To")
    final_exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, default=18.0000, verbose_name="Final Payment Exchange Rate")
    final_payment_doc = models.FileField(upload_to='container_docs/', blank=True, null=True, verbose_name="Invoice", validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png'])])

    # Transport fields
    transport_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Transport Value")
    transport_currency_from = models.CharField(
    max_length=3, choices=EXCHANGE_RATE_FROM_CHOICES, default='USD', verbose_name="Transport Currency From")
    transport_currency_to = models.CharField(
    max_length=3, choices=EXCHANGE_RATE_TO_CHOICES, default='NAD', verbose_name="Transport Currency To")
    transport_exchange_rate = models.DecimalField(
    max_digits=10, decimal_places=4, default=18.0000, verbose_name="Transport Exchange Rate"
    )
    transport_doc = models.FileField(
        upload_to='container_docs/', blank=True, null=True,
        verbose_name="Transport Document",
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png'])],
    )
    supplier = ChainedForeignKey(
        'commercial.Supplier',
        chained_field="sub_category",      
        chained_model_field="sub_category", 
        show_all=False,
        auto_choose=True,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Supplier"
    )
    item_category = models.ForeignKey(
        'inventory.StockCategory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Item Category"
    )
    sub_category = ChainedForeignKey(
        'inventory.StockSubCategory',
        chained_field="item_category",
        chained_model_field="category",
        show_all=False,
        auto_choose=True,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Sub category"
    )
    stock_item = ChainedForeignKey(
        'inventory.StockItem',
        chained_field="sub_category",  
        chained_model_field="sub_category",  
        show_all=False,
        auto_choose=True,
        sort=True,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Stock Item"
    )
    warehouse = models.ForeignKey(
        'commercial.Warehouse',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Warehouse"
    )
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default='Import',
        verbose_name="Source (Local/Import)"
    )
    # Commission fields
    commission = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Commission Amount")
    commission_currency_from = models.CharField(
    max_length=3, choices=EXCHANGE_RATE_FROM_CHOICES, default='USD', verbose_name="Commission Currency From")
    commission_currency_to = models.CharField(
    max_length=3, choices=EXCHANGE_RATE_TO_CHOICES, default='NAD', verbose_name="Commission Currency To")
    commission_exchange_rate = models.DecimalField(
    max_digits=10, decimal_places=4, default=18.0000, verbose_name="Commission Exchange Rate"
    )
    commission_doc = models.FileField(
        upload_to='container_docs/', blank=True, null=True,
        verbose_name="Commission Document",
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png'])],
    )

    price_per_ton_calculated = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Price per Ton (calculated)", editable=False
    )
    
    # Pricing & Exchange for CIF
    price_per_ton_cif = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=0, 
        verbose_name="Price/Ton"   # Remove 'CIF'
    )
    price_per_ton_cif_doc = models.FileField(
        upload_to='container_docs/', blank=True, null=True,
        verbose_name="Purchase Order Document"  # Change from 'Price CIF Document'
    )
    exchange_cif_from = models.CharField(
        max_length=3, choices=EXCHANGE_RATE_FROM_CHOICES, default='USD',
        verbose_name="Exchange From"  # Remove 'CIF'
    )
    exchange_cif_to = models.CharField(
        max_length=3, choices=EXCHANGE_RATE_TO_CHOICES, default='NAD',
        verbose_name="Exchange To"  # Remove 'CIF'
    )
    exchange_cif_rate = models.DecimalField(
        max_digits=10, decimal_places=4, default=18.0000,
        verbose_name="Exchange Rate"  # Remove 'CIF'
    )
    
    fob_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Total FOB Value")
    fob_price_currency = models.CharField(max_length=3, choices=EXCHANGE_RATE_FROM_CHOICES, default='USD', verbose_name="FOB Currency")
    fob_price_doc = models.FileField(
        upload_to='container_docs/', blank=True, null=True,
    verbose_name="Invoice",
    validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png'])],
    )

    # Duty & Exchange
    duty = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Duty")
    duty_currency = models.CharField(
        max_length=3,
        choices=CLEARING_CURRENCY_CHOICES,
        default='NAD',
        verbose_name="Duty Currency"
    )
    duty_doc = models.FileField(
        upload_to='container_docs/', blank=True, null=True,
        verbose_name="Duty Document",
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png'])],
    )

    # Clearing (no exchange rate; only NAD/ZAR)
    clearing = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Clearing")
    clearing_currency = models.CharField(max_length=3, choices=CLEARING_CURRENCY_CHOICES, default='NAD', verbose_name="Clearing Currency")
    clearing_doc = models.FileField(upload_to='container_docs/', blank=True, null=True, verbose_name="Clearing Document", validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png'])])
    
    kg_per_box = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="kg/Box")
    total_boxes = models.IntegerField(default=0, verbose_name="Total Amount of Boxes")
    total_weight_container = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Total Weight for Container (kg)", editable=True)
    gross_weight = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Gross Weight (kg)")
    net_weight = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Net Weight (kg)")
    estimated_pouches = models.IntegerField(default=0, verbose_name="Estimated Pouches", editable=False)
    total_cost_nad = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Total Cost", editable=False)

    payment_terms = models.CharField(max_length=100, choices=PAYMENT_TERMS_CHOICES, blank=True, verbose_name="Payment Terms")
    payment_status = models.CharField(max_length=50, choices=PAYMENT_STATUS_CHOICES, default='Unpaid', verbose_name="Payment Status")
    permit_number = models.CharField(max_length=100, blank=True, verbose_name="Permit Number")
    permit_doc = models.FileField(upload_to='container_docs/', blank=True, null=True, verbose_name="Permit Document", validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png'])])
    invoice = models.CharField(max_length=100, blank=True, verbose_name="INVOICE")
    invoice_doc = models.FileField(upload_to='container_docs/', blank=True, null=True, verbose_name="Invoice Document", validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png'])])
    po_number = models.CharField(max_length=100, blank=True, verbose_name="PO Number")
    po_doc = models.FileField(upload_to='container_docs/', blank=True, null=True, verbose_name="PO Document", validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png'])])
    vessel = models.CharField(max_length=100, blank=True, verbose_name="Vessel")
    booking = models.CharField(max_length=100, blank=True, verbose_name="BOOKING")
    ship_owner = models.CharField(max_length=50, choices=SHIP_OWNER_CHOICES, blank=True, verbose_name="SHIP OWNER")
    comments = models.TextField(blank=True, verbose_name="Comments")

    def get_nad_value(self, amount, cur_from, cur_to, rate):
        """Convert currency amount to NAD"""
        if not amount:
            return Decimal('0')
        if cur_from == cur_to:
            return amount
        return amount * rate

    def save(self, *args, **kwargs):
        deposit_nad = self.get_nad_value(
            self.deposit_amount, self.deposit_currency_from, self.deposit_currency_to, self.deposit_exchange_rate
        )
        final_nad = self.get_nad_value(
            self.final_amount, self.final_currency_from, self.final_currency_to, self.final_exchange_rate
        )
        transport_nad = self.get_nad_value(
            self.transport_cost, self.transport_currency_from, self.transport_currency_to, self.transport_exchange_rate
        )
        commission_nad = self.get_nad_value(
            self.commission, self.commission_currency_from, self.commission_currency_to, self.commission_exchange_rate
        )

        duty_nad = self.duty if self.duty_currency == 'NAD' else Decimal('0')
        clearing_nad = self.clearing if self.clearing_currency == 'NAD' else Decimal('0')

        # Calculate total weight and estimated pouches
        if self.kg_per_box and self.total_boxes:
            self.total_weight_container = self.kg_per_box * self.total_boxes
            if self.kg_per_box > 0:
                self.estimated_pouches = int(self.total_weight_container / self.kg_per_box)
        else:
            self.total_weight_container = Decimal('0')
            self.estimated_pouches = 0

        # Sum all costs
        self.total_cost_nad = (
            deposit_nad +
            final_nad +
            transport_nad +
            commission_nad +
            duty_nad +
            clearing_nad
        )
        super().save(*args, **kwargs)

    def get_tracking_url(self):
        if not self.ship_owner or not self.container_number:
            return None
        ship_owner_upper = self.ship_owner.upper()
        if ship_owner_upper == "MSC":
            return f"https://www.msc.com/en/track-a-shipment?container={self.container_number}"
        elif ship_owner_upper == "MAERSK":
            return f"https://www.maersk.com/tracking/{self.container_number}"
        elif ship_owner_upper == "HAPAG":
            return f"https://www.hapag-lloyd.com/en/online-business/track/track-by-container-solution.html?container={self.container_number}"
        else:
            return None

    def __str__(self):
        return self.container_number

class UnitOfMeasure(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='units_of_measure',
        help_text="Site this unit belongs to. Leave blank for HQ units."
    )
    name = models.CharField(max_length=50)
    abbreviation = models.CharField(max_length=10)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['site', 'name'], name='unique_unit_name_per_site'),
            models.UniqueConstraint(fields=['site', 'abbreviation'], name='unique_unit_abbr_per_site'),
        ]

    def __str__(self):
        return self.abbreviation or self.name

class StockCategory(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='stock_categories'
    )
    name = models.CharField(max_length=50, verbose_name="Category Name")

    def __str__(self):
        return self.name

class StockSubCategory(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='stock_subcategories'
    )
    category = models.ForeignKey(StockCategory, on_delete=models.CASCADE, related_name='subcategories')
    name = models.CharField(max_length=100)
    
    def __str__(self):
        return self.name  
    
    class Meta:
        ordering = ['category', 'name']

class StockItem(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.PROTECT,
        related_name='stock_items',
        null=True,
        blank=True,
        help_text="Site this stock item belongs to"
    )
    category = models.ForeignKey(
        StockCategory,
        on_delete=models.CASCADE,
        verbose_name="Item Category"
    )
    sub_category = ChainedForeignKey(
        StockSubCategory,
        chained_field="category",
        chained_model_field="category",
        show_all=False,
        auto_choose=True,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Sub Category"
    )
    standard_cost_excl_transport = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        verbose_name="Price Excluding VAT and Transport"
    )
    standard_cost_excl_transport_currency = models.CharField(
        max_length=5,
        choices=[('R', 'Rand (R)'), ('NAD', 'Namibian Dollar (NAD)')],
        default='R',
        verbose_name="Currency"
    )
    
    standard_cost_incl_transport = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        verbose_name="Price Excluding VAT incl Transport"
    )
    standard_cost_incl_transport_currency = models.CharField(
        max_length=5,
        choices=[('R', 'Rand (R)'), ('NAD', 'Namibian Dollar (NAD)')],
        default='R',
        verbose_name="Currency"
    )
    name = models.CharField(max_length=120, verbose_name="Name")
    unit_of_measure = models.ForeignKey(
        'inventory.UnitOfMeasure',
        on_delete=models.PROTECT,
        related_name='stock_items',
        verbose_name='Unit of Measure'
    )
    reorder_level = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    is_archived = models.BooleanField(default=False, db_index=True)
    @property
    def stock_level_display(self):
        in_sum = self.transactions.filter(transaction_type='IN').aggregate(models.Sum('quantity'))['quantity__sum'] or 0
        out_sum = self.transactions.filter(transaction_type='OUT').aggregate(models.Sum('quantity'))['quantity__sum'] or 0
        return int(in_sum - out_sum)

    def __str__(self):
        return self.name
 
TRANSACTION_TYPE_CHOICES = [
    ('IN', 'Booking In'),
    ('OUT', 'Booking Out'),
    ('AMENDMENT', 'Amendment'),
]

class StockTransaction(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='stock_transactions'
    )
    category = models.ForeignKey('StockCategory', on_delete=models.CASCADE, verbose_name="Item Category")
    batch = models.ForeignKey(
        'manufacturing.Batch',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='stock_transactions', verbose_name="Linked Production Batch"
    )
    batch_ref = models.CharField(max_length=100, blank=True, verbose_name="Batch / Ref")
    sub_category = ChainedForeignKey(
        'inventory.StockSubCategory',
        chained_field="category",
        chained_model_field="category",
        show_all=False,
        auto_choose=True,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    stock_item = ChainedForeignKey(
        'inventory.StockItem',
        chained_field="sub_category",
        chained_model_field="sub_category",  # links to sub_category on StockItem
        show_all=False,
        auto_choose=True,
        sort=True,
        verbose_name="Stock Item",
        related_name='transactions'
    )
    transporter_document = models.FileField(
        upload_to='transporter_docs/', blank=True, null=True,
        verbose_name="Transporter Document (PDF/DOC)",
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png'])],
    )
    transaction_type = models.CharField(
        max_length=10, 
        choices=TRANSACTION_TYPE_CHOICES,
        default='IN'
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('Ordered', 'Ordered'),
            ('Available', 'Available'),
            ('Processed', 'Processed'),
        ],
        default='Pending',
        verbose_name="Status"
    )
    amendment_reason = models.TextField(blank=True, null=True)
    amendment_person = models.CharField(max_length=100, blank=True, null=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_date = models.DateField(verbose_name="Booking In Date")
    delivery_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(
        null=True, 
        blank=True, 
        verbose_name="Expiry Date",
        help_text="Date when this stock item expires"
    )
    authorized_person = models.CharField(max_length=100, blank=True, verbose_name="Authorized Person")

    supplier = ChainedForeignKey(
        'commercial.Supplier',
        chained_field="sub_category",        
        chained_model_field="sub_category",   
        show_all=False,
        auto_choose=True,
        sort=True,
        verbose_name="Supplier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    warehouse = models.ForeignKey(
        'commercial.Warehouse',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Warehouse"
    )
    container = models.ForeignKey(
        'inventory.Container',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_transactions',
        verbose_name="Linked Container"
    )
    kg_per_box = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, 
        verbose_name="Units/Package",
        blank=True
    )
    total_boxes = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=0, 
        verbose_name="Total Amount of Packages",
        blank=True
    )
    booking_in_total_qty = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name="Total Amount",  
        editable=True,  # ← CHANGE TO TRUE (so model's save() can set it)
        help_text="Calculated as: Units/Package × Total Amount of Packages"
    )
    gross_weight = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, 
        verbose_name="Gross Weight (kg)",
        blank=True
    )
    net_weight = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, 
        verbose_name="Net Weight (kg)",
        blank=True
    )
    price_per = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Price per", blank=True)
    total_invoice_amount_excl = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Total Invoice Amount Excl Transport and VAT", blank=True)
    transport_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Transport Cost", blank=True)
    transporter = models.ForeignKey('commercial.Transporter', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Transporter")
    invoice_document = models.FileField(upload_to='invoices/', blank=True, null=True, verbose_name="Invoice Document (PDF/DOC)", validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png'])])
    usage_notes = models.TextField(blank=True)
    waste_per_production_batch = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Waste per Production Batch",
        help_text="Total waste this batch (L/KG/unit etc)"
    )
    amount_used = models.DecimalField(
        max_digits=12, decimal_places=4, default=0,
        verbose_name="Amount Used", help_text="Quantity used in production booking out"
    )
    amount_unit = models.CharField(
        max_length=10, choices=[('L', 'Litre (L)'), ('KG', 'Kilogram (KG)'), ('Unit', 'Unit')],
        default='Unit', verbose_name="Usage Unit"
    )
    currency = models.CharField(
        max_length=5, choices=[('R', 'Rand (R)'), ('NAD', 'Namibian Dollar (NAD)')],
        default='R', verbose_name="Currency"
    )
    sauce_sheet = models.FileField(
        upload_to='sauce_sheets/', blank=True, null=True,
        verbose_name="Sauce Mixing Sheet (PDF/DOC)",
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png'])],
    )
    is_archived = models.BooleanField(default=False, db_index=True)
    
    @property
    def price_per_unit_display(self):
        """Calculate price per unit based on total invoice + transport"""
        if not self.stock_item:
            return "-"
        
        try:
            unit_str = str(self.stock_item.unit_of_measure) if self.stock_item.unit_of_measure else "Unit"
            currency = self.currency or "R"
            qty = float(self.quantity or 0)
            
            if qty <= 0:
                return f"{currency} 0.00 per {unit_str}"
            
            total_cost = float(self.total_invoice_amount_excl or 0) + float(self.transport_cost or 0)
            price_per = total_cost / qty
            
            return f"{currency} {price_per:,.2f} per {unit_str}"
        except Exception as e:
            return "-"
    
    @property
    def total_cost_display(self):
        """Calculate total cost (invoice + transport)"""
        try:
            currency = self.currency or "R"
            invoice = float(self.total_invoice_amount_excl or 0)
            transport = float(self.transport_cost or 0)
            total = invoice + transport
            
            return f"{currency} {total:,.2f}"
        except Exception as e:
            return f"Error: {str(e)}"
            
    class Meta:
        ordering = ['-transaction_date']

    def __str__(self):
        stock_name = self.stock_item.name if self.stock_item else 'No Item'
        return f"{self.get_transaction_type_display()} - {stock_name} ({self.quantity})"

    def save(self, *args, **kwargs):
        # ✨ AUTO-CALCULATE BOOKING_IN_TOTAL_QTY ✨
        if self.kg_per_box is not None and self.total_boxes is not None:
            self.booking_in_total_qty = Decimal(str(self.kg_per_box)) * Decimal(str(self.total_boxes))
        else:
            self.booking_in_total_qty = Decimal('0')
        
        super().save(*args, **kwargs)

    def price_per_actual_unit(self):
        try:
            base_cost = float(self.total_invoice_amount_excl or 0) + float(self.transport_cost or 0)
            used = float(self.amount_used or 1)
            units = float(self.batch.shift_total if self.batch else 0)
            if used <= 0 or units <= 0:
                return "-"
            total_units = units + float(self.waste_per_production_batch or 0)
            cost_per_unit = base_cost / total_units if total_units > 0 else 0
            return f"R{cost_per_unit:,.4f} ({self.amount_unit} basis)"
        except Exception:
            return "-"
    
    @property
    def cost_per_unit(self):
        try:
            amount = float(self.amount_used or 0)
            waste = float(self.waste_per_production_batch or 0)
            total = amount + waste
            price_per_l_num = float(self.price_per or 0) + (float(self.transport_cost or 0) / float(self.quantity or 1))
            batch_qty = float(self.batch.shift_total if self.batch else 0)
            currency_symbol = self.currency if self.currency else "R"
            if batch_qty > 0:
                cost_unit = (total * price_per_l_num) / batch_qty
                return f"{currency_symbol} {round(cost_unit, 2):,.2f}"
            return "-"
        except Exception:
            return "-"

    @property
    def unit_of_measure_display(self):
        """Returns the unit of measure string from stock_item"""
        if self.stock_item and self.stock_item.unit_of_measure:
            return str(self.stock_item.unit_of_measure)
        return "-"

    @property
    def linked_batch_qty_display(self):
        return self.batch.shift_total if self.batch and hasattr(self.batch, "shift_total") else "-"

    @property
    def price_excl_transport_per(self):
        try:
            currency_symbol = self.currency if self.currency else "R"
            qty = float(self.quantity or 0)
            invoice_amount = float(self.total_invoice_amount_excl or 0)
            if qty > 0:
                result = invoice_amount / qty
                return f"{currency_symbol} {result:,.2f}"
            return f"{currency_symbol} 0.00"
        except Exception:
            return f"{self.currency} 0.00"

    @property
    def price_incl_transport_per(self):
        try:
            currency_symbol = self.currency if self.currency else "R"
            qty = float(self.quantity or 0)
            invoice_amount = float(self.total_invoice_amount_excl or 0)
            transport = float(self.transport_cost or 0)
            if qty > 0:
                price_excl = invoice_amount / qty
                transport_per_unit = transport / qty
                combined = price_excl + transport_per_unit
                return f"{currency_symbol} {combined:,.2f}"
            return f"{currency_symbol} 0.00"
        except Exception:
            return f"{self.currency} 0.00"

    @property
    def price_per_unit(self):
        return self.stock_item.unit_of_measure if self.stock_item else "-"

class Amendment(models.Model):
    batch_ref = models.CharField(
        max_length=100,
        verbose_name="Batch / Ref",
    )
    stock_item = models.ForeignKey(
    'inventory.StockItem',
    on_delete=models.CASCADE,
    related_name='amendments',
    null=True,
    blank=True
    )
    AMENDMENT_TYPE_CHOICES = [
        ('IN', 'Booking Back In'),
        ('OUT', 'Extra Use')
    ]
    amendment_type = models.CharField(
        max_length=10,
        choices=AMENDMENT_TYPE_CHOICES,
        default='IN',           
    )
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField()
    person = models.CharField(max_length=100)
    date = models.DateField(default=timezone.now)

    def __str__(self):
        return f"{self.get_amendment_type_display()} ({self.quantity}) on {self.date} - Batch: {self.batch_ref}"

class PackagingBalance(models.Model):
    """
    Tracks packaging balance for a production DATE (combined for all batches that day)
    Supports multiple batch refs per stock item via batch_ref_type distinction
    """
    production_date = models.DateField(
        verbose_name="Production Date"
    )
    stock_item = models.ForeignKey(
        StockItem,
        on_delete=models.CASCADE,
        related_name='packaging_balances_by_date',
        verbose_name="Packaging Item"
    )
    opening_balance = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name="Stock Balance Last Production"  
    )
    booked_out_stock = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name="Booked Out Stock"
    )
    closing_balance = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name="Stock Balance Unused"
    )
    batch_ref_type = models.CharField(
        max_length=20,
        choices=[
            ('stock_source', 'Stock Item Source'),
            ('production', 'Production Batch'),
        ],
        default='stock_source',
        verbose_name="Batch Ref Type"
    )
    opening_batch_ref = models.CharField(max_length=255, blank=True, null=True)
    batch_ref = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        verbose_name="Batch Ref Number"  
    )
    amended_reason = models.CharField(
        max_length=255, 
        blank=True,
        verbose_name="Reason"
    )
    cancel_opening_use_bookout = models.BooleanField(
        default=False,
        verbose_name="Cancel Opening use Book out"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('production_date', 'stock_item', 'batch_ref_type', 'batch_ref')
        verbose_name = "Packaging Balance"
        verbose_name_plural = "Packaging Balances"
        ordering = ['stock_item__name']

    def __str__(self):
        return f"{self.production_date} - {self.stock_item.name} ({self.batch_ref_type}: {self.batch_ref})"

class RecipeStockItemBalance(models.Model):
    """
    Tracks recipe stock item balance for a production DATE (combined for all batches that day)
    Mirrors PackagingBalance but for recipe ingredients
    Supports multiple batch refs per stock item via batch_ref_type distinction
    """
    production_date = models.DateField(
        verbose_name="Production Date"
    )
    stock_item = models.ForeignKey(
        StockItem,
        on_delete=models.CASCADE,
        related_name='recipe_stock_balances_by_date',
        verbose_name="Recipe Stock Item"
    )
    opening_balance = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name="Stock Balance Last Production"
    )
    booked_out_stock = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name="Booked out stock"
    )
    closing_balance = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name="Stock Balance Unused"
    )
    batch_ref_type = models.CharField(
        max_length=20,
        choices=[
            ('stock_source', 'Stock Item Source'),
            ('production', 'Production Batch'),
        ],
        default='stock_source',
        verbose_name="Batch Ref Type"
    )
    opening_batch_ref = models.CharField(max_length=255, blank=True, null=True)
    batch_ref = models.CharField(
        max_length=100, 
        blank=True,
        verbose_name="Batch Ref Number"
    )
    amended_reason = models.CharField(
        max_length=255, 
        blank=True,
        verbose_name="Reason"
    )
    cancel_opening_use_bookout = models.BooleanField(
        default=False,
        verbose_name="Cancel Opening use Book out"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('production_date', 'stock_item', 'batch_ref_type', 'batch_ref')
        verbose_name_plural = "Recipe Stock Item Balances"

    def __str__(self):
        return f"{self.stock_item.name} - {self.production_date} ({self.batch_ref_type}: {self.batch_ref})"

FINISHED_PRODUCT_TRANSACTION_TYPES = [
    ('IN', 'Book In'),
    ('DISPATCH', 'Dispatch Out'),
    ('TRANSFER', 'Stock Transfer'),
    ('SCRAP', 'Damage / Scrap'),
]

class FinishedProductTransaction(models.Model):
    """
    Ledger for finished product per batch.
    Tracks movements in/out of warehouses and dispatches to clients.
    """
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='finished_product_transactions'
    )
    batch = models.ForeignKey(
        Batch,
        on_delete=models.CASCADE,
        related_name='finished_transactions',
        verbose_name="Production Batch",
        null=True,       
        blank=True,      
    )
    
    transaction_type = models.CharField(
        max_length=10,
        choices=FINISHED_PRODUCT_TRANSACTION_TYPES,
        default='IN',
    )
    cumulative_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Running balance after this transaction"
    )
    
    stock_released = models.BooleanField(
        default=False,
        verbose_name="Y/N"
    )
    stock_released_date = models.DateField(
        null=True, blank=True,
        verbose_name="Date Stock Released"
    )
    status = models.CharField(
        max_length=20,
        choices=[('PENDING', 'Pending'), ('RELEASED', 'Released')],
        default='RELEASED',
    )
    product_name = models.CharField(max_length=200, blank=True)
    size = models.CharField(max_length=50, blank=True)

    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Quantity",
    )

    from_warehouse = models.ForeignKey(
        'commercial.Warehouse',          
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='finished_outgoing',
        verbose_name="From Warehouse",
    )

    to_warehouse = models.ForeignKey(
        'commercial.Warehouse',    
        on_delete=models.PROTECT,
        null=True, blank=True,
        verbose_name="Warehouse",
        related_name="finishedproduct_to_warehouse",
    )

    client = models.ForeignKey(
        'commercial.Client',            
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Client",
    )
    ready_to_dispatch = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        editable=False 
    )
    date = models.DateField(verbose_name="Transaction Date")
    notes = models.TextField(blank=True)
    authorized_person = models.CharField(max_length=100, blank=True)
    is_archived = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Final product stock"
        verbose_name_plural = "Final product stock"
        ordering = ['-date', '-pk']
        indexes = [
            models.Index(fields=['batch', 'date']),
            models.Index(fields=['transaction_type']),
        ]

    def __str__(self):
        trans = self.get_transaction_type_display()
        if not getattr(self, "batch_id", None) or self.batch is None:
            return f"{trans} ({self.quantity})"
        return f"{trans} - {self.batch.batch_number} ({self.quantity})"
     
    @property
    def signed_quantity(self):
        """
        Return quantity with direction sign.
        IN / TRANSFER into batch are positive.
        OUT / DISPATCH / SCRAP are negative.
        """
        if self.transaction_type in ('IN', 'TRANSFER', 'AMENDMENT'):
            return Decimal(self.quantity or 0)
        return -Decimal(self.quantity or 0)

    @property
    def available_qty_for_batch(self):
        if not getattr(self, "batch_id", None):
            return Decimal("0.00")

        start = Decimal(self.batch.shift_total or 0)

        qs = FinishedProductTransaction.objects.filter(batch=self.batch)

        plus = qs.filter(
            transaction_type__in=['IN', 'TRANSFER']
        ).aggregate(s=Sum('quantity'))['s'] or Decimal('0.00')

        minus = qs.filter(
            transaction_type__in=['OUT', 'DISPATCH', 'SCRAP']
        ).aggregate(s=Sum('quantity'))['s'] or Decimal('0.00')

        am_total = qs.filter(
            transaction_type='AMENDMENT'
        ).aggregate(s=Sum('quantity'))['s'] or Decimal('0.00')

        return start + plus - minus + am_total
    
    @property
    def live_ready_to_dispatch(self):
        if not getattr(self, "batch_id", None) or self.batch is None:
            return Decimal('0.00')

        from manufacturing.models import Waste

        shift_total = Decimal(self.batch.shift_total or 0)

        try:
            waste = Waste.objects.filter(batch=self.batch).first()
            if waste:
                nsi = Decimal(waste.nsi_sample_per_batch.get(self.batch.batch_number, 0) or 0)
                retention = Decimal(waste.retention_sample_per_batch.get(self.batch.batch_number, 0) or 0)
                unclear = Decimal(waste.unclear_coding_per_batch.get(self.batch.batch_number, 0) or 0)
            else:
                nsi = retention = unclear = Decimal(0)

            return max(Decimal(0), shift_total - nsi - retention - unclear)
        except Exception:
            return Decimal(self.batch.shift_total or 0)
            
    @property
    def direction_display(self):
        """Display direction: Book In, Book Out, or Internal"""
        if self.transaction_type == "IN":
            return "Book In"
        elif self.transaction_type == "TRANSFER":
            return "Internal"
        return "Book Out"
    
    def save(self, *args, **kwargs):
        """Calculate cumulative_balance and handle dispatch status"""
        
        # Handle DISPATCH status workflow
        if self.transaction_type == 'DISPATCH':
            if self.stock_released:
                self.status = 'RELEASED'
                if not self.stock_released_date:
                    from django.utils import timezone
                    self.stock_released_date = timezone.now().date()
            else:
                self.status = 'PENDING'
                self.stock_released_date = None
        
        # Calculate cumulative balance
        if self.batch:
            from decimal import Decimal
            
            if self.transaction_type == 'IN':
                if hasattr(self, 'ready_to_dispatch') and self.ready_to_dispatch:
                    self.cumulative_balance = Decimal(str(self.ready_to_dispatch))
                else:
                    self.cumulative_balance = self.batch.get_ready_to_dispatch()
            else:
                # For DISPATCH: Only subtract from balance when RELEASED
                if self.transaction_type == 'DISPATCH' and self.status == 'PENDING':
                    previous_txn = FinishedProductTransaction.objects.filter(
                        batch=self.batch
                    ).exclude(pk=self.pk).order_by('-date', '-pk').first()
                    
                    if previous_txn and previous_txn.cumulative_balance is not None:
                        self.cumulative_balance = Decimal(str(previous_txn.cumulative_balance))
                    else:
                        self.cumulative_balance = self.batch.get_ready_to_dispatch()
                else:
                    previous_txn = FinishedProductTransaction.objects.filter(
                        batch=self.batch
                    ).exclude(pk=self.pk).order_by('-date', '-pk').first()
                    
                    if previous_txn and previous_txn.cumulative_balance is not None:
                        running_balance = Decimal(str(previous_txn.cumulative_balance))
                    else:
                        running_balance = self.batch.get_ready_to_dispatch()
                    
                    if self.transaction_type == 'TRANSFER':
                        self.cumulative_balance = running_balance + Decimal(str(self.quantity or 0))
                    else:
                        self.cumulative_balance = running_balance - Decimal(str(self.quantity or 0))
        
        super().save(*args, **kwargs)

class PickingSlip(models.Model):
    """
    Picking slips generated from Billing documents.
    Created automatically when create_picking_slip is checked on BillingDocumentHeader.
    """
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='picking_slips'
    )
    billing = models.OneToOneField(
        'costing.BillingDocumentHeader',
        on_delete=models.CASCADE,
        related_name='picking_slip',
        verbose_name="Billing Document",
    )

    picking_slip_pdf = models.FileField(
        upload_to="picking_slips/",
        blank=True,
        null=True,
        verbose_name="Picking Slip PDF",
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])],
    )

    billing_date = models.DateField(
        verbose_name="Billing Date",
        editable=False,
    )

    due_date = models.DateField(
        verbose_name="Due Date",
        null=True,
        blank=True,
        editable=False,
    )

    completed = models.BooleanField(
        default=False,
        verbose_name="Completed",
    )
    
    released_by = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Released By",
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name="Notes",
    )
    
    date_created = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date Created",
    )

    date_completed = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date Completed",
        editable=True,
    )
    is_archived = models.BooleanField(default=False, db_index=True)
    
    class Meta:
        verbose_name = "Picking Slip"
        verbose_name_plural = "Picking Slips"
        ordering = ['-billing_date', '-date_created']

    def __str__(self):
        return f"Picking Slip - {self.billing.base_number} ({self.billing_date.strftime('%d/%m/%y')})"

    def save(self, *args, **kwargs):
        # Auto-stamp completed time
        if self.completed and not self.date_completed:
            self.date_completed = timezone.now()
        elif not self.completed:
            self.date_completed = None
        super().save(*args, **kwargs)


# =============================================================================
# PURCHASE ORDER MODELS
# =============================================================================

class PurchaseOrder(models.Model):
    """
    Purchase Order header - for ordering stock from suppliers.
    Supports both Local and Import orders with different currency defaults.
    """
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        related_name='purchase_orders',
        null=True,
        blank=True,
        help_text="Site this purchase order belongs to"
    )
    TYPE_CHOICES = [
        ('Local', 'Local'),
        ('Import', 'Import'),
    ]
    CURRENCY_CHOICES = [
        ('R', 'Rand (R)'),
        ('NAD', 'Namibian Dollar (NAD)'),
        ('USD', 'US Dollar ($)'),
        ('EUR', 'Euro (€)'),
    ]
    STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('Sent', 'Sent'),
        ('Acknowledged', 'Acknowledged'),
        ('Received', 'Received'),
        ('Closed', 'Closed'),
    ]
    
    # PO Number - auto-incrementing but editable if needed
    po_number = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="PO Number",
        blank=True,
    )
    
    # Order type and currency
    order_type = models.CharField(
        max_length=10,
        choices=TYPE_CHOICES,
        default='Local',
        verbose_name="Order Type",
    )
    currency = models.CharField(
        max_length=5,
        choices=CURRENCY_CHOICES,
        default='R',
        verbose_name="Currency",
    )
    
    # Category/SubCategory for filtering supplier
    category = models.ForeignKey(
        'inventory.StockCategory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Category",
        help_text="Select category to filter available suppliers"
    )
    sub_category = ChainedForeignKey(
        'inventory.StockSubCategory',
        chained_field="category",
        chained_model_field="category",
        show_all=False,
        auto_choose=True,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Sub Category",
        help_text="Select sub-category to further filter suppliers"
    )
    
    # Dates
    order_date = models.DateField(
        verbose_name="Order Date",
    )
    due_date = models.DateField(
        verbose_name="Due Date",
        null=True,
        blank=True,
    )
    
    # Supplier (from Commercial) - chained to sub_category
    supplier = models.ForeignKey(
        'commercial.Supplier',
        on_delete=models.PROTECT,
        related_name='purchase_orders',
        verbose_name="Supplier",
        null=True,
        blank=True,
    )
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Draft',
        verbose_name="Status",
    )
    
    # VAT (Value Added Tax)
    vat_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=15,
        verbose_name="VAT (%)",
    )
    
    # Document generation flags
    create_po = models.BooleanField(
        default=False,
        verbose_name="Create PO",
    )
    
    # Notes
    notes = models.TextField(
        blank=True,
        verbose_name="Notes",
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # HQ flag - distinguishes HQ-created POs from site-created POs
    is_hq_order = models.BooleanField(default=False, db_index=True, verbose_name="HQ Order")
    
    # Archiving
    is_archived = models.BooleanField(default=False, db_index=True)
    
    class Meta:
        verbose_name = "Purchase Order"
        verbose_name_plural = "Purchase Orders"
        ordering = ['-order_date', '-po_number']
    
    def __str__(self):
        supplier_name = self.supplier.name if self.supplier else (self.site.name if self.site else 'No Supplier')
        return f"PO-{self.po_number} - {supplier_name}"
    
    def save(self, *args, **kwargs):
        # Auto-generate PO number if not set
        if not self.po_number:
            last_po = PurchaseOrder.objects.order_by('-id').first()
            if last_po and last_po.po_number:
                try:
                    last_num = int(last_po.po_number)
                    self.po_number = str(last_num + 1).zfill(5)
                except ValueError:
                    self.po_number = "00001"
            else:
                self.po_number = "00001"
        
        # Set default currency based on order type
        if not self.pk:  # Only on creation
            if self.order_type == 'Import' and self.currency == 'R':
                self.currency = 'USD'
            elif self.order_type == 'Local' and self.currency == 'USD':
                self.currency = 'R'
        
        super().save(*args, **kwargs)
    
    @property
    def total_amount(self):
        """Calculate total PO amount from line items"""
        total = sum(item.line_total for item in self.line_items.all())
        return total
    
    @property
    def total_amount_display(self):
        """Formatted total with currency symbol"""
        currency_symbols = {
            'R': 'R',
            'NAD': 'N$',
            'USD': '$',
            'EUR': '€',
        }
        symbol = currency_symbols.get(self.currency, self.currency)
        return f"{symbol} {self.total_amount:,.2f}"
    
    @property
    def grand_total(self):
        """Calculate grand total: total_amount + VAT"""
        vat_amount = self.total_amount * (self.vat_percentage / 100)
        return self.total_amount + vat_amount


class PurchaseOrderLineItem(models.Model):
    """
    Line items for a Purchase Order.
    Allows selecting stock items with chained category/subcategory.
    """
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name='line_items',
        verbose_name="Purchase Order",
    )
    
    # Stock item selection (chained)
    category = models.ForeignKey(
        'inventory.StockCategory',
        on_delete=models.CASCADE,
        verbose_name="Category",
    )
    sub_category = ChainedForeignKey(
        'inventory.StockSubCategory',
        chained_field="category",
        chained_model_field="category",
        show_all=False,
        auto_choose=True,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Sub Category",
    )
    stock_item = ChainedForeignKey(
        'inventory.StockItem',
        chained_field="sub_category",
        chained_model_field="sub_category",
        show_all=False,
        auto_choose=True,
        sort=True,
        verbose_name="Stock Item",
        related_name='po_line_items',
    )
    
    # Quantity and pricing
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Quantity to Order",
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Unit Price (Excl Transport)",
    )
    
    class Meta:
        verbose_name = "PO Line Item"
        verbose_name_plural = "PO Line Items"
        ordering = ['id']
    
    def __str__(self):
        return f"{self.stock_item.name} x {self.quantity}"
    
    @property
    def line_total(self):
        """Calculate line total"""
        return self.quantity * self.unit_price
    
    @property
    def line_total_display(self):
        """Formatted line total"""
        return f"{self.line_total:,.2f}"
    
    @property
    def unit_of_measure(self):
        """Get unit of measure from stock item"""
        if self.stock_item and self.stock_item.unit_of_measure:
            return str(self.stock_item.unit_of_measure)
        return "-"
    
    @classmethod
    def get_last_unit_price(cls, stock_item):
        """
        Get the last unit price for a stock item from StockTransaction.
        Calculates: Total Invoice Amount Excl Transport / Total Amount (booking_in_total_qty)
        """
        from inventory.models import StockTransaction
        
        last_transaction = StockTransaction.objects.filter(
            stock_item=stock_item,
            transaction_type='IN',
        ).order_by('-transaction_date', '-id').first()
        
        if last_transaction:
            invoice_amount = last_transaction.total_invoice_amount_excl or Decimal('0')
            total_qty = last_transaction.booking_in_total_qty or last_transaction.quantity or Decimal('1')
            
            if total_qty > 0:
                return invoice_amount / total_qty
        
        return Decimal('0')


class HQPOLineItem(models.Model):
    """
    Line items for HQ Purchase Orders.
    Uses Product details (ProductCategory / Product) instead of stock items.
    """
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name='hq_line_items',
        verbose_name="Purchase Order",
    )
    category = models.ForeignKey(
        'product_details.ProductCategory',
        on_delete=models.CASCADE,
        verbose_name="Category",
    )
    product = models.ForeignKey(
        'product_details.Product',
        on_delete=models.CASCADE,
        verbose_name="Product",
        null=True,
        blank=True,
    )
    sku = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="SKU",
    )
    size = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Size",
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Qty for PO",
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Price for PO",
    )

    class Meta:
        verbose_name = "HQ PO Line Item"
        verbose_name_plural = "HQ PO Line Items"
        ordering = ['id']

    def __str__(self):
        name = self.product.product_name if self.product else (self.sku or '-')
        return f"{name} x {self.quantity}"

    def save(self, *args, **kwargs):
        """Sync SKU and Size from product."""
        if self.product:
            self.sku = self.product.sku or ''
            self.size = self.product.size or ''
        super().save(*args, **kwargs)

    @property
    def line_total(self):
        return self.quantity * self.unit_price

