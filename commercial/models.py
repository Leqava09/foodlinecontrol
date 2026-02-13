from django.db import models
from inventory.models import StockCategory
from smart_selects.db_fields import ChainedForeignKey
from django.db import models
from decimal import Decimal


class Supplier(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        related_name='suppliers',
        null=True,
        blank=True,
        help_text="Site this supplier belongs to"
    )
    category = models.ForeignKey(
        'inventory.StockCategory',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Category"
    )
    sub_category = ChainedForeignKey(
        'inventory.StockSubCategory',
        chained_field="category",
        chained_model_field="category",
        show_all=False,
        auto_choose=True,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Sub Category"
    )
    name = models.CharField(max_length=120)
    contact_person = models.CharField(max_length=80, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_archived = models.BooleanField(default=False, db_index=True)

    def __str__(self):
        return self.name 

class Client(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        related_name='clients',
        null=True,
        blank=True,
        help_text="Site this client belongs to"
    )
    # Identity
    name = models.CharField("Company name", max_length=255)
    legal_name = models.CharField("Legal name", max_length=255, blank=True)
    registration_number = models.CharField(max_length=100, blank=True)
    vat_number = models.CharField("VAT number", max_length=100, blank=True)

    # Address
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True, default="South Africa")

    # Commercial / contact
    payment_terms = models.TextField(blank=True)
    contact_person = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)

    notes = models.TextField(blank=True)
    
    is_archived = models.BooleanField(default=False, db_index=True)

    def __str__(self):
        # Show a nice name in admin
        return self.name or self.legal_name or "Client"

class Warehouse(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        related_name='warehouses',
        null=True,
        blank=True,
        help_text="Site this warehouse belongs to"
    )
    warehouse_name = models.CharField("Warehouse name", max_length=80)
    
    # Lease info
    size_m2 = models.DecimalField(
        "Size m²",
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Total floor area in square meters.",
    )
    standard_rate_per_m2_per_month = models.DecimalField(
        "Standard rate per m² / month",
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Base rental rate per square meter per month.",
    )
    total_rent_per_month = models.DecimalField(
        "Total rent per month",
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Monthly rent for this warehouse.",
    )
    lease_expiry_date = models.DateField(
        "Expiry date of lease",
        blank=True,
        null=True,
    )
    manager = models.CharField(max_length=80, blank=True)
    # Contact
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)

    # Address
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True, default="South Africa")

    notes = models.TextField(blank=True)
    
    is_archived = models.BooleanField(default=False, db_index=True)

    def __str__(self):
        return self.warehouse_name
        
class Transporter(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        related_name='transporters',
        null=True,
        blank=True,
        help_text="Site this transporter belongs to"
    )
    name = models.CharField(max_length=120)
    contact_person = models.CharField(max_length=80, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)

    is_archived = models.BooleanField(default=False, db_index=True)
    
    def __str__(self):
        return self.name

class StandardTransportRate(models.Model):
    
    CURRENCY_ZAR = "R"
    CURRENCY_NAD = "NAD"
    CURRENCY_USD = "$"
    CURRENCY_EUR = "€"

    CURRENCY_CHOICES = [
        (CURRENCY_ZAR, "R"),
        (CURRENCY_NAD, "NAD"),
        (CURRENCY_USD, "$"),
        (CURRENCY_EUR, "€"),
    ]

    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default=CURRENCY_ZAR,
    )
    transporter = models.ForeignKey(
        Transporter,
        on_delete=models.CASCADE,
        related_name="standard_rates"
    )
    from_location = models.CharField("From", max_length=120)
    to_location = models.CharField("To", max_length=120)
    
    amount_excl = models.DecimalField(
        "Amount excl",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    class Meta:
        verbose_name = "Standard transport rate"
        verbose_name_plural = "Standard transport rates"
        ordering = ["from_location", "to_location", "currency"]

    def __str__(self):
        return f"{self.transporter} {self.from_location} → {self.to_location} ({self.currency} {self.amount_excl})"
        
class CompanyDetails(models.Model):   # <<< rename from Companydetails
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='company_details'
    )
    name = models.CharField("Company name", max_length=255)
    legal_name = models.CharField("Legal name", max_length=255, blank=True)
    registration_number = models.CharField(max_length=100, blank=True)
    vat_number = models.CharField("VAT number", max_length=100, blank=True)

    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True, default="South Africa")

    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)

    bank_name = models.CharField(max_length=255, blank=True)
    bank_account_name = models.CharField(max_length=255, blank=True)
    bank_account_number = models.CharField(max_length=50, blank=True)
    bank_branch_code = models.CharField(max_length=50, blank=True)
    
    currency = models.CharField(
        "Currency",
        max_length=10,
        blank=True,
    )

    logo = models.ImageField(
        upload_to="company/logo/",
        blank=True,
        null=True,
        help_text="Logo used on invoices/quotes."
    )

    billing_template = models.FileField(
        upload_to="company/templates/billing/",
        blank=True,
        null=True,
        help_text="Single billing template used for invoice/quote/proforma."
    )
    
    po_template = models.FileField(
        upload_to="company/templates/po/",
        blank=True,
        null=True,
        verbose_name="Purchase Order Template",
        help_text="Template document (.docx) for generating purchase orders."
    )
    
    admin_background = models.ImageField(
        upload_to="company/background/",
        blank=True,
        null=True,
        verbose_name="Admin Background Image",
        help_text="Background image displayed on the admin dashboard (JPEG/PNG)."
    )
    
    is_archived = models.BooleanField(default=False, db_index=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Company details"
        verbose_name_plural = "Company details"

    def __str__(self):
        return self.name or "Company details"

