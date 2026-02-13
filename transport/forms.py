# transport/forms.py

from django import forms
from .models import TransportLoad
from commercial.models import Client, Transporter
from tenants.models import Site


class ImportTransportForm(forms.ModelForm):
    """Form for importing transport loads from site"""
    site = forms.ModelChoiceField(
        queryset=None,
        required=True,
        label="Site",
        help_text="Select site to import transport load from",
        widget=forms.Select(attrs={
            'class': 'vSelect',
            'id': 'id_import_site',
            'onchange': 'loadTransportLoadsForSite(this.value)',
        })
    )
    
    load_number = forms.CharField(
        required=True,
        label="Load Number",
        max_length=50,
        widget=forms.TextInput(attrs={
            'placeholder': 'Select site first...',
            'size': 20,
            'class': 'vTextField',
            'autocomplete': 'off',
            'id': 'id_import_load_number',
            'onchange': 'pullTransportLoadData(this.value)',
        }),
        help_text="Load number from selected site"
    )
    
    hq_load_number = forms.CharField(
        required=True,
        label="HQ Load Number",
        max_length=50,
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g., HQ-LOAD-001',
            'size': 20,
            'class': 'vTextField',
            'autocomplete': 'off',
            'id': 'id_hq_load_number',
        }),
        help_text="New load number for HQ transport"
    )
    
    class Meta:
        model = TransportLoad
        fields = [
            'transporter',
            'delivery_note_documents', 'namra_documents', 'daff_documents',
            'meat_board_documents', 'import_permit_documents', 'other_documents',
        ]
        widgets = {
            'transporter': forms.Select(attrs={'class': 'vSelect'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Site queryset - only active sites
        self.fields['site'].queryset = Site.objects.filter(is_active=True)
        
        # Transporter from HQ only
        self.fields['transporter'].queryset = Transporter.objects.filter(site__isnull=True, is_archived=False)
        
        # When editing an existing import, make site and load_number not required
        if self.instance and self.instance.pk and self.instance.import_source_site:
            self.fields['site'].required = False
            self.fields['load_number'].required = False
            # Pre-populate
            self.fields['site'].initial = self.instance.import_source_site
            self.fields['load_number'].initial = self.instance.import_source_load_number
            self.fields['hq_load_number'].initial = self.instance.load_number
    
    def clean(self):
        """Validate that

 load_number exists in the selected site (only when creating new import)"""
        cleaned_data = super().clean()
        load_number = cleaned_data.get('load_number')
        site = cleaned_data.get('site')
        
        # Skip validation when editing existing import
        if self.instance and self.instance.pk:
            return cleaned_data
        
        if load_number and site:
            # Check if this load number exists in this site
            exists = TransportLoad.objects.filter(
                load_number=load_number,
                site=site
            ).exists()
            if not exists:
                raise forms.ValidationError(
                    f"Load number '{load_number}' not found for {site.name}. "
                    f"Make sure you selected the correct site and load number."
                )
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Get import source from form fields
        import_site = self.cleaned_data.get('site')
        import_load = self.cleaned_data.get('load_number')
        hq_load = self.cleaned_data.get('hq_load_number')
        
        # Set import source tracking
        if import_site:
            instance.import_source_site = import_site
        if import_load:
            instance.import_source_load_number = import_load
        
        # Set HQ load number
        if hq_load:
            instance.load_number = hq_load
        
        # Force site=NULL for HQ imports
        instance.site = None
        
        if commit:
            instance.save()
            self.save_m2m()
            
            # Copy data from site transport load to HQ import
            if import_site and import_load:
                try:
                    # Find the original site transport load
                    site_load = TransportLoad.objects.get(
                        site=import_site,
                        load_number=import_load
                    )
                    
                    # Copy relevant fields (most fields are read-only, created by signals)
                    instance.billing_document = site_load.billing_document
                    instance.transporter = site_load.transporter
                    
                    # Copy documents
                    instance.delivery_note_documents = site_load.delivery_note_documents
                    instance.namra_documents = site_load.namra_documents
                    instance.daff_documents = site_load.daff_documents
                    instance.meat_board_documents = site_load.meat_board_documents
                    instance.import_permit_documents = site_load.import_permit_documents
                    instance.other_documents = site_load.other_documents
                    
                    instance.save()
                    print(f"✅ Copied transport load data from site {import_site.name} load {import_load} to HQ load {hq_load}")
                except TransportLoad.DoesNotExist:
                    print(f"❌ ERROR: Could not find load {import_load} in site {import_site.name}")
                except Exception as e:
                    print(f"❌ ERROR copying transport load data: {e}")
        
        return instance


class HQDirectTransportForm(forms.ModelForm):
    """Form for HQ direct transport load creation (without import functionality)"""
    
    class Meta:
        model = TransportLoad
        fields = [
            'transporter',
            'delivery_note_documents', 'namra_documents', 'daff_documents',
            'meat_board_documents', 'import_permit_documents', 'other_documents',
        ]
        widgets = {
            'transporter': forms.Select(attrs={'class': 'vSelect'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Transporter should filter from HQ transporters only (site is NULL)
        self.fields['transporter'].queryset = Transporter.objects.filter(site__isnull=True, is_archived=False)
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # Force site=NULL for HQ transport
        instance.site = None
        
        if commit:
            instance.save()
            self.save_m2m()
        return instance
