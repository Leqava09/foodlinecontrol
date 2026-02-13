from django import forms
from .models import Production, Batch
from product_details.models import ProductCategory, Product

DATE_INPUTS = ["%d-%m-%Y", "%Y-%m-%d"]  # dd-mm-yyyy + ISO


# Custom field that renders as select but validates like CharField (no strict choice enforcement)
class FlexibleSelectField(forms.CharField):
    """CharField with Select widget - allows any string value, not restricted to choices"""
    def __init__(self, *args, choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.widget = forms.Select(choices=choices or [])
    
    def validate(self, value):
        # Skip the standard ChoiceField validation that enforces choices
        # Just validate that it's not empty if required
        if self.required and not value:
            raise forms.ValidationError(self.error_messages['required'])


class ProductionForm(forms.ModelForm):
    production_date = forms.DateField(
        required=True,
        input_formats=DATE_INPUTS,
        widget=forms.DateInput(
            format="%d-%m-%Y",
            attrs={"class": "vDateField"},
        ),
    )

    class Meta:
        model = Production
        fields = "__all__"


class BatchForm(forms.ModelForm):
    batch_id = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )
    
    sku = FlexibleSelectField(
        required=False,
        max_length=100,
        choices=[('', '-- Select SKU --')],
    )

    class Meta:
        model = Batch
        fields = ('a_no', 'batch_number', 'production', 'category', 'product', 'sku', 'size', 'shift_total')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set the batch_id field to the actual instance ID
        if self.instance and self.instance.pk:
            self.fields['batch_id'].initial = self.instance.pk
        
        # Filter category and product fields by current site if available from request
        if hasattr(self, '_current_site') and self._current_site:
            site = self._current_site
            print(f'[BatchForm] Filtering fields for site: {site}')
            self.fields['category'].queryset = ProductCategory.objects.filter(site=site)
            self.fields['product'].queryset = Product.objects.filter(site=site)
            print(f'[BatchForm] Category queryset count: {self.fields["category"].queryset.count()}')
            print(f'[BatchForm] Product queryset count: {self.fields["product"].queryset.count()}')
        
        # Populate SKU choices dynamically when editing existing batch
        if self.instance and self.instance.pk and self.instance.product:
            try:
                product = self.instance.product
                # Get all products with the same product_name (different SKUs/sizes)
                sku_products = Product.objects.filter(
                    product_name=product.product_name,
                    site=product.site
                ).values_list('sku', 'size').distinct().order_by('sku')
                
                # Build choices: [('', '-- Select SKU --'), ('GCLRG425G', 'GCLRG425G'), ...]
                # Only show SKU code in the dropdown - size is in a separate read-only field
                sku_choices = [('', '-- Select SKU --')]
                for sku, size in sku_products:
                    if sku:
                        # ✅ Show only SKU code - no size text in the label
                        sku_choices.append((sku, sku))
                
                # Update both the field and widget choices
                self.fields['sku'].widget.choices = sku_choices
            except Exception:
                # If anything fails, keep default choices
                pass
    
    def clean(self):
        cleaned_data = super().clean()
        
        # ✅ Skip validation if form is marked for deletion
        if cleaned_data.get('DELETE', False):
            return cleaned_data
        
        # ✅ CRITICAL: Strip size text from SKU field if it has been appended
        # This can happen if form submission includes text like "GCLRG425G (425 gr)"
        if 'sku' in cleaned_data and cleaned_data['sku']:
            sku_value = cleaned_data['sku']
            if '(' in sku_value:
                # Size has been appended - extract just the SKU code
                clean_sku = sku_value.split('(')[0].strip()
                cleaned_data['sku'] = clean_sku
        
        # ✅ Validate batch_number uniqueness per site (allow duplicates across sites)
        # Note: This only checks against database. Formset-level validation handles duplicates within the formset.
        batch_number = cleaned_data.get('batch_number')
        
        # Get site from form instance
        site = None
        if self.instance and self.instance.site:
            site = self.instance.site
        
        if batch_number and site:
            # Check if this batch_number already exists in the same site (excluding self during edit)
            query = Batch.objects.filter(batch_number=batch_number, site=site)
            
            # During edit, exclude the current batch by id
            if self.instance and self.instance.id:
                query = query.exclude(id=self.instance.id)
            
            if query.exists():
                from django.core.exceptions import ValidationError
                raise ValidationError(
                    f"Production Code '{batch_number}' already exists in site '{site.name}'. "
                    f"Each site must have unique Production Codes."
                )
        
        return cleaned_data


class BatchFormSet(forms.BaseInlineFormSet):
    """Custom formset for batch inline to validate uniqueness across all batches in the formset"""
    
    def clean(self):
        """Validate that batch_numbers are unique within this formset (excluding deleted forms)"""
        if any(self.errors):
            # Don't validate formset if individual forms have errors
            return
        
        batch_numbers = {}
        site = None
        
        for form in self.forms:
            # Skip empty forms and forms marked for deletion
            if not form.cleaned_data or form.cleaned_data.get('DELETE', False):
                continue
            
            batch_number = form.cleaned_data.get('batch_number')
            if not batch_number:
                continue
            
            # Get site from the form instance
            if form.instance and form.instance.site:
                site = form.instance.site
            
            # Check for duplicates within the formset
            if batch_number in batch_numbers:
                from django.core.exceptions import ValidationError
                site_name = site.name if site else "this site"
                raise ValidationError(
                    f"Production Code '{batch_number}' appears multiple times. "
                    f"Each batch must have a unique Production Code within {site_name}."
                )
            
            batch_numbers[batch_number] = form

