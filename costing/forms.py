import logging
from django import forms
from .models import (
    SalaryPosition,
    OverheadItem,
    SalaryCosting,
    OverheadCosting,
    BillingDocumentHeader,
    InvestorLoanCosting,
    InvestorLoanItem,
)
from commercial.models import CompanyDetails

logger = logging.getLogger(__name__)

DATE_INPUTS = ["%d-%m-%Y", "%Y-%m-%d"]  # dd-mm-yyyy + ISO


def get_company_currency():
    # Note: Forms don't have direct site context; default to HQ company (site=NULL)
    # In context where site is available, use: CompanyDetails.objects.filter(site=site, is_active=True).first()
    company = CompanyDetails.objects.filter(site__isnull=True, is_active=True).first()
    if company and company.currency:
        return company.currency
    return "R"


class SalaryCostingForm(forms.ModelForm):
    date = forms.DateField(
        required=True,
        input_formats=DATE_INPUTS,
        widget=forms.DateInput(
            format="%d-%m-%Y",
            attrs={"class": "vDateField", "size": 10},
        ),
    )

    class Meta:
        model = SalaryCosting
        fields = "__all__"


class SalaryPositionForm(forms.ModelForm):
    total_per_hour_display = forms.CharField(
        label="Per Hour",
        required=False,
        disabled=True,
    )
    total_per_month_display = forms.CharField(
        label="Total for Month",
        required=False,
        disabled=True,
    )
    percentage_display = forms.CharField(
        label="% Total",
        required=False,
        disabled=True,
    )

    class Meta:
        model = SalaryPosition
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        cur = get_company_currency()
        numeric_right = "text-align:right; padding-right:4px;"
        numeric_center = "text-align:center;"

        # Read‑only display fields
        self.fields["total_per_hour_display"].widget.attrs["style"] = (
            f"width:85px; {numeric_right}"
        )
        self.fields["total_per_month_display"].widget.attrs["style"] = (
            f"width:115px; {numeric_right}"
        )
        self.fields["percentage_display"].widget.attrs["style"] = (
            f"width:65px; {numeric_center}"
        )

        # Entry fields – all centered except position_name
        centered_fields = [
            ("general_workers", "60px"),
            ("qa_workers", "60px"),
            ("shifts", "60px"),
            ("shift_hours", "60px"),
            ("rate_per_hour", "60px"),
            ("qa_rate_per_hour", "60px"),
            ("days_worked", "60px"),
        ]
        
        right_aligned_fields = []
        
        for name, width in centered_fields:
            if name in self.fields:
                self.fields[name].widget.attrs["style"] = (
                    f"width:{width}; {numeric_center}"
                )
        
        for name, width in right_aligned_fields:
            if name in self.fields:
                self.fields[name].widget.attrs["style"] = (
                    f"width:{width}; {numeric_right}"
                )

        # Populate readonly values from instance
        if self.instance.pk:
            self.fields["total_per_hour_display"].initial = (
                f"{cur} {float(self.instance.total_per_hour):,.2f}"
            )
            self.fields["total_per_month_display"].initial = (
                f"{cur} {float(self.instance.total_per_month):,.2f}"
            )
            self.fields["percentage_display"].initial = (
                "{:.2f}%".format(float(self.instance.percentage))
            )

class OverheadCostingForm(forms.ModelForm):
    date = forms.DateField(
        required=True,
        input_formats=DATE_INPUTS,
        widget=forms.DateInput(
            format="%d-%m-%Y",
            attrs={"class": "vDateField", "size": 10},
        ),
    )

    class Meta:
        model = OverheadCosting
        fields = "__all__"


class OverheadItemForm(forms.ModelForm):
    per_week_display = forms.CharField(
        label="Per Week",
        required=False,
        disabled=True,
    )
    per_day_display = forms.CharField(
        label="Per Day",
        required=False,
        disabled=True,
    )
    per_hour_display = forms.CharField(
        label="Per Hour",
        required=False,
        disabled=True,
    )
    per_unit_display = forms.CharField(
        label="Per Unit",
        required=False,
        disabled=True,
    )
    percentage_display = forms.CharField(
        label="% Total",
        required=False,
        disabled=True,
    )

    class Meta:
        model = OverheadItem
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        cur = get_company_currency()
        numeric_align = "text-align:right; padding-right:4px;"

        # Read‑only totals
        self.fields["per_week_display"].widget.attrs["style"] = (
            f"width:90px; {numeric_align}"
        )
        self.fields["per_day_display"].widget.attrs["style"] = (
            f"width:90px; {numeric_align}"
        )
        self.fields["per_hour_display"].widget.attrs["style"] = (
            f"width:85px; {numeric_align}"
        )
        self.fields["per_unit_display"].widget.attrs["style"] = (
            f"width:85px; {numeric_align}"
        )
        self.fields["percentage_display"].widget.attrs["style"] = (
            f"width:65px; {numeric_align}"
        )

        # Entry fields in OverheadItem
        for name, width in [
            ("per_month", "90px"),
        ]:
            if name in self.fields:
                self.fields[name].widget.attrs["style"] = (
                    f"width:{width}; {numeric_align}"
                )

        # Populate readonly values from instance
        if self.instance.pk:
            self.fields["per_week_display"].initial = (
                f"{cur} {float(self.instance.per_week):,.2f}"
            )
            self.fields["per_day_display"].initial = (
                f"{cur} {float(self.instance.per_day):,.2f}"
            )
            self.fields["per_hour_display"].initial = (
                f"{cur} {float(self.instance.per_hour):,.2f}"
            )
            self.fields["per_unit_display"].initial = (
                f"{cur} {float(self.instance.per_unit):,.4f}"
            )


class InvestorLoanCostingForm(forms.ModelForm):
    date = forms.DateField(
        required=True,
        input_formats=DATE_INPUTS,
        widget=forms.DateInput(
            format="%d-%m-%Y",
            attrs={"class": "vDateField", "size": 10},
        ),
    )

    class Meta:
        model = InvestorLoanCosting
        fields = "__all__"


class InvestorLoanItemForm(forms.ModelForm):
    per_unit_display = forms.CharField(
        label="Per Unit",
        required=False,
        disabled=True,
    )
    percentage_display = forms.CharField(
        label="% Total",
        required=False,
        disabled=True,
    )

    class Meta:
        model = InvestorLoanItem
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        cur = get_company_currency()
        numeric_align = "text-align:right; padding-right:4px;"

        # Read‑only totals
        self.fields["per_unit_display"].widget.attrs["style"] = (
            f"width:85px; {numeric_align}"
        )
        self.fields["percentage_display"].widget.attrs["style"] = (
            f"width:65px; {numeric_align}"
        )

        # Entry fields
        for name, width in [
            ("total_amount", "120px"),
            ("monthly_payment", "120px"),
        ]:
            if name in self.fields:
                self.fields[name].widget.attrs["style"] = (
                    f"width:{width}; {numeric_align}"
                )

        # Populate readonly values from instance
        if self.instance.pk:
            self.fields["per_unit_display"].initial = (
                f"{cur} {float(self.instance.per_unit):,.4f}"
            )


class ImportBillingForm(forms.ModelForm):
    """Form for importing billing from site and amending pricing"""
    site = forms.ModelChoiceField(
        queryset=None,
        required=True,
        label="Site",
        help_text="Select site to import billing from",
        widget=forms.Select(attrs={
            'class': 'vSelect',
            'id': 'id_import_site',
            'onchange': 'loadInvoicesForSite(this.value)',  # JavaScript to load invoices
        })
    )
    
    invoice_number = forms.CharField(
        required=True,
        label="Invoice Number",
        max_length=20,
        widget=forms.TextInput(attrs={
            'placeholder': 'Select site first...',
            'size': 20,
            'class': 'vTextField',
            'autocomplete': 'off',
            'id': 'id_import_invoice_number',
            'onchange': 'pullInvoiceData(this.value)',  # Load data when invoice selected
        }),
        help_text="Invoice number from selected site"
    )
    
    base_number = forms.CharField(
        required=True,
        label="HQ Base Number",
        max_length=20,
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g., HQ-001',
            'size': 15,
            'class': 'vTextField',
            'autocomplete': 'off',
            'id': 'id_hq_base_number',
        }),
        help_text="New invoice number for HQ billing"
    )
    
    class Meta:
        model = BillingDocumentHeader
        fields = [
            'client', 'delivery_institution', 'base_number',
            'billing_date', 'due_date',
            'from_currency', 'to_currency', 'exchange_rate', 'vat_percentage',
            'bill_per_primary', 'bill_per_secondary', 'bill_per_pallet',
            'transporters', 'transport_cost',
            'create_quote', 'create_proforma', 'create_invoice',
            'create_picking_slip', 'create_delivery_note',
            'dispatched',
            'qty_for_invoice_data',
        ]
        widgets = {
            'client': forms.Select(attrs={
                'class': 'vSelect',
                'style': 'max-width: 200px;',  # Even smaller
            }),
            'billing_date': forms.DateInput(
                format='%d/%m/%Y',
                attrs={'class': 'vDateField', 'size': 10}
            ),
            'due_date': forms.DateInput(
                format='%d/%m/%Y',
                attrs={'class': 'vDateField', 'size': 10}
            ),
            'qty_for_invoice_data': forms.Textarea(),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from tenants.models import Site
        from commercial.models import Client
        from transport.models import DeliverySite
        self.fields['site'].queryset = Site.objects.filter(is_active=True)
        # Client should filter from HQ clients only (no site filtering)
        self.fields['client'].queryset = Client.objects.filter(site__isnull=True)
        
        # Setup delivery_institution field with dynamic filtering
        if 'delivery_institution' in self.fields:
            # If editing existing object with a client, filter by that client
            if self.instance.pk and self.instance.client_id:
                self.fields['delivery_institution'].queryset = DeliverySite.objects.filter(
                    client=self.instance.client
                ).order_by('institutionname')
            else:
                # Empty queryset initially (will be populated by client selection)
                self.fields['delivery_institution'].queryset = DeliverySite.objects.none()
            
            # Add data attribute for JavaScript to enable dynamic filtering
            self.fields['delivery_institution'].widget.attrs['data-chained-field'] = 'client'
        
        # When editing an existing import, make site and invoice_number not required
        # (they're shown as readonly fields in the admin)
        if self.instance and self.instance.pk and self.instance.import_source_site:
            self.fields['site'].required = False
            self.fields['invoice_number'].required = False
            # Pre-populate in case they're hidden
            self.fields['site'].initial = self.instance.import_source_site
            self.fields['invoice_number'].initial = self.instance.import_source_invoice_number
    
    def clean(self):
        """Validate that invoice_number exists in the selected site (only when creating new import)"""
        cleaned_data = super().clean()
        invoice_number = cleaned_data.get('invoice_number')
        site = cleaned_data.get('site')
        
        # Skip validation when editing existing import
        if self.instance and self.instance.pk:
            return cleaned_data
        
        if invoice_number and site:
            # Check if this invoice number exists in this site
            exists = BillingDocumentHeader.objects.filter(
                base_number=invoice_number,
                site=site
            ).exists()
            if not exists:
                raise forms.ValidationError(
                    f"Invoice number '{invoice_number}' not found for {site.name}. "
                    f"Make sure you selected the correct site and invoice number."
                )
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Get import source from form fields
        import_site = self.cleaned_data.get('site')
        import_invoice = self.cleaned_data.get('invoice_number')
        
        # Set import source tracking from form fields (only if provided)
        # When editing, these might not be in cleaned_data if they're not in the fieldset
        if import_site:
            instance.import_source_site = import_site
        if import_invoice:
            instance.import_source_invoice_number = import_invoice
        
        # Force site=NULL for HQ imports
        instance.site = None
        
        if commit:
            instance.save()
            self.save_m2m()
            
            # ✅ COPY batch_costings from site invoice to HQ billing document
            if import_site and import_invoice:
                try:
                    # Find the original site invoice
                    site_invoice = BillingDocumentHeader.objects.get(
                        site=import_site,
                        base_number=import_invoice
                    )
                    
                    # Copy all batch_costings from site invoice to HQ import
                    batch_costings = site_invoice.batch_costings.all()
                    if batch_costings.exists():
                        instance.batch_costings.set(batch_costings)
                        logger.info('Copied %s batch_costings from site invoice %s to HQ billing %s', batch_costings.count(), import_invoice, instance.base_number)
                    else:
                        logger.warning('Site invoice %s has no batch_costings', import_invoice)
                    
                    # Copy qty_for_invoice_data from source invoice if not already set
                    if not instance.qty_for_invoice_data and site_invoice.qty_for_invoice_data:
                        instance.qty_for_invoice_data = site_invoice.qty_for_invoice_data
                        instance.save(update_fields=['qty_for_invoice_data'])
                        logger.info('Copied qty_for_invoice_data from site invoice')
                except BillingDocumentHeader.DoesNotExist:
                    logger.error('Could not find site invoice %s in site %s', import_invoice, import_site.name)
                except Exception as e:
                    logger.error('Error copying batch_costings: %s', e)
        
        return instance


class HQDirectBillingForm(forms.ModelForm):
    """Form for HQ direct billing (without import functionality)"""
    base_number = forms.CharField(
        required=True,
        label="HQ Base Number",
        max_length=20,
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g., HQ-001',
            'size': 15,
            'class': 'vTextField',
            'autocomplete': 'off',
            'id': 'id_hq_base_number',
        }),
        help_text="Invoice number for HQ billing"
    )
    
    # Explicit date fields with input_formats for dd-mm-yyyy
    billing_date = forms.DateField(
        label="Billing date",
        input_formats=['%d-%m-%Y', '%d/%m/%Y', '%Y-%m-%d'],
        widget=forms.DateInput(
            format='%d-%m-%Y',
            attrs={'class': 'vDateField', 'size': 10}
        )
    )
    due_date = forms.DateField(
        label="Due date",
        required=False,
        input_formats=['%d-%m-%Y', '%d/%m/%Y', '%Y-%m-%d'],
        widget=forms.DateInput(
            format='%d-%m-%Y',
            attrs={'class': 'vDateField', 'size': 10}
        )
    )
    
    class Meta:
        model = BillingDocumentHeader
        fields = [
            'client', 'delivery_institution', 'base_number',
            'billing_date', 'due_date',
            'from_currency', 'to_currency', 'exchange_rate', 'vat_percentage',
            'bill_per_primary', 'bill_per_secondary', 'bill_per_pallet',
            'transporters', 'transport_cost',
            'create_quote', 'create_proforma', 'create_invoice',
            'create_picking_slip', 'create_delivery_note',
            'dispatched',
            'qty_for_invoice_data',
        ]
        widgets = {
            'client': forms.Select(attrs={
                'class': 'vSelect',
                'style': 'max-width: 200px;',
            }),
            'qty_for_invoice_data': forms.Textarea(),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from commercial.models import Client, Transporter
        from transport.models import DeliverySite
        # Client should filter from HQ clients only (site is NULL)
        self.fields['client'].queryset = Client.objects.filter(site__isnull=True, is_archived=False)
        # Transporter should filter from HQ transporters only (site is NULL)
        self.fields['transporters'].queryset = Transporter.objects.filter(site__isnull=True, is_archived=False)
        
        # Setup delivery_institution field with dynamic filtering
        if 'delivery_institution' in self.fields:
            # If editing existing object with a client, filter by that client
            if self.instance.pk and self.instance.client_id:
                self.fields['delivery_institution'].queryset = DeliverySite.objects.filter(
                    client=self.instance.client
                ).order_by('institutionname')
            else:
                # Empty queryset initially (will be populated by client selection)
                self.fields['delivery_institution'].queryset = DeliverySite.objects.none()
            
            # Add data attribute for JavaScript to enable dynamic filtering
            self.fields['delivery_institution'].widget.attrs['data-chained-field'] = 'client'
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # Force site=NULL for HQ billing
        instance.site = None
        
        if commit:
            instance.save()
            self.save_m2m()
        return instance