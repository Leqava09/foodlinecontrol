# incident_management/forms.py
from django import forms
from .models import Incident

DATE_INPUTS = ["%d-%m-%Y", "%Y-%m-%d"]

class IncidentForm(forms.ModelForm):
    site = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        help_text="In HQ: Used for batch filtering only (not saved). In Site: Auto-assigned to current site."
    )
    
    incident_date = forms.DateField(
        required=True,
        input_formats=DATE_INPUTS,
        widget=forms.DateInput(
            format="%d-%m-%Y",
            attrs={"class": "vDateField"},
        ),
    )
    production_date = forms.DateField(
        required=False,
        input_formats=DATE_INPUTS,
        widget=forms.DateInput(
            format="%d-%m-%Y",  # ← Change back to DD-MM-YYYY
            attrs={"class": "vDateField"},
        ),
    )
    investigation_start = forms.DateField(
        required=True,
        input_formats=DATE_INPUTS,
        widget=forms.DateInput(
            format="%d-%m-%Y",
            attrs={"class": "vDateField"},
        ),
    )
    investigation_end = forms.DateField(
        required=True,
        input_formats=DATE_INPUTS,
        widget=forms.DateInput(
            format="%d-%m-%Y",
            attrs={"class": "vDateField"},
        ),
    )
    report_date = forms.DateField(
        required=True,
        input_formats=DATE_INPUTS,
        widget=forms.DateInput(
            format="%d-%m-%Y",
            attrs={"class": "vDateField"},
        ),
    )

    class Meta:
        model = Incident
        fields = [
            'site',
            'production',
            'production_date',
            'batch',
            'incident_date',
            'location',
            'investigation_start',
            'investigation_end',
            'report_date',
            'responsible_person',
            'management_person',
            'description',
            'incident_report',
            'is_archived',
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from tenants.models import Site
        from manufacturing.models import Batch
        
        self.fields['site'].queryset = Site.objects.all()
        self.fields['site'].required = False
        
        # Handle batch queryset filtering
        if self.instance and self.instance.pk:
            # Editing existing incident
            if self.data:
                # Form submitted (POST) - Don't filter to prevent validation errors
                # The JavaScript handles the filtering in the UI, but validation needs all batches
                self.fields['batch'].queryset = Batch.objects.all().order_by('batch_number')
            else:
                # GET request - editing existing incident
                # CRITICAL: Always include the currently selected batch in queryset
                if self.instance.batch:
                    # Start with the selected batch
                    queryset = Batch.objects.filter(pk=self.instance.batch.pk)
                    
                    # Determine the site for filtering
                    filter_site = None
                    if self.instance.batch.site:
                        # HQ incident - use batch's site for filtering
                        filter_site = self.instance.batch.site
                        self.initial['site'] = filter_site
                        self.fields['site'].initial = filter_site
                    elif self.instance.site:
                        # Site incident - use incident's site for filtering
                        filter_site = self.instance.site
                    
                    # Add filtered batches from the same site and production date
                    if filter_site:
                        filtered_batches = Batch.objects.filter(site=filter_site)
                        if self.instance.production_date:
                            filtered_batches = filtered_batches.filter(
                                production_date=self.instance.production_date
                            )
                        # Combine: selected batch + filtered batches
                        queryset = (queryset | filtered_batches).distinct()
                    
                    self.fields['batch'].queryset = queryset.order_by('batch_number')
                elif self.instance.site:
                    # No batch selected yet, but in site context
                    site = self.instance.site
                    if self.instance.production_date:
                        self.fields['batch'].queryset = Batch.objects.filter(
                            site=site,
                            production_date=self.instance.production_date
                        ).order_by('batch_number')
                    else:
                        self.fields['batch'].queryset = Batch.objects.filter(
                            site=site
                        ).order_by('batch_number')
        elif not self.data:
            # New incident form (GET request, not POST): Start with empty batch queryset
            # JavaScript will populate it after production_date is selected
            self.fields['batch'].queryset = Batch.objects.none()
        else:
            # New incident form submitted (POST) - filter batches if site is selected
            site_id = self.data.get('site')
            production_date = self.data.get('production_date')
            
            if site_id:
                queryset = Batch.objects.filter(site_id=site_id)
                if production_date:
                    # Try to parse the date and filter
                    try:
                        from django.utils.dateparse import parse_date
                        # Handle both DD-MM-YYYY and YYYY-MM-DD formats
                        if isinstance(production_date, str):
                            parts = production_date.split('-')
                            if len(parts) == 3 and len(parts[0]) == 2:
                                # DD-MM-YYYY format
                                parsed_date = parse_date(f'{parts[2]}-{parts[1]}-{parts[0]}')
                            else:
                                parsed_date = parse_date(production_date)
                        else:
                            parsed_date = production_date
                            
                        if parsed_date:
                            queryset = queryset.filter(production_date=parsed_date)
                    except:
                        pass
                self.fields['batch'].queryset = queryset.order_by('batch_number')
