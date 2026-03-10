import logging
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path
from django.utils.dateparse import parse_date
from .models import Incident, IncidentAttachment
from manufacturing.models import Batch
from .forms import IncidentForm
from foodlinecontrol.admin_base import ArchivableAdmin
from tenants.admin_utils import SiteAwareModelAdmin

logger = logging.getLogger(__name__)

class IncidentAttachmentInline(admin.TabularInline):
    model = IncidentAttachment
    extra = 1
    fields = ['file', 'uploaded_at']
    readonly_fields = ['uploaded_at']

@admin.register(Incident)
class IncidentAdmin(SiteAwareModelAdmin, ArchivableAdmin):
    form = IncidentForm

    class Media:
        js = ('js/production_date_fix.js',)

    list_display = [
        'id', 'incident_date', 'batch', 'location',
        'investigation_start', 'investigation_end', 'report_date',
        'responsible_person', 'management_person'
    ]
    list_filter = ['incident_date', 'report_date', 'batch']
    search_fields = ['location', 'responsible_person', 'management_person', 'description']
    readonly_fields = ['created']
    inlines = [IncidentAttachmentInline]
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'batch-options/',
                self.admin_site.admin_view(self.batch_options_view),
                name='incident_batch_options',
            ),
        ]
        return custom_urls + urls
    
    def batch_options_view(self, request):
        """Return batch options filtered by production_date AND site"""
        
        production_date_str = request.GET.get('production_date')
        site_id = request.GET.get('site_id')
        
        production_date = parse_date(production_date_str) if production_date_str else None
        
        logger.debug('batch_options_view: production_date=%s, site_id=%s', production_date, site_id)
        
        if not production_date:
            return JsonResponse([], safe=False)
        
        # Filter by production_date first
        batches = Batch.objects.filter(production_date=production_date)
        logger.debug('Batches for date %s: count=%s', production_date, batches.count())
        
        # Then filter by site if site_id provided
        if site_id:
            try:
                site_id_int = int(site_id)
                batches = batches.filter(site_id=site_id_int)
                logger.debug('Filtered by site_id=%s, count=%s', site_id_int, batches.count())
            except (ValueError, TypeError) as e:
                logger.debug('Error parsing site_id: %s', e)
        else:
            # In site context, use current_site
            current_site = getattr(request, 'current_site', None)
            logger.debug('current_site=%s', current_site)
            if current_site:
                batches = batches.filter(site=current_site)
                logger.debug('Filtered by current_site, count=%s', batches.count())
            else:
                logger.debug('No site filter applied, returning all %s batches', batches.count())
        
        # Return batch options as JSON (value must be pk for Django ModelChoiceField)
        data = [
            {'value': batch.pk, 'display': str(batch)}
            for batch in batches.order_by('batch_number')
        ]
        
        logger.debug('Returning %s batches', len(data))
        return JsonResponse(data, safe=False)
    
    def save_model(self, request, obj, form, change):
        """
        HQ: Force site=NULL (incidents saved in HQ have no site affiliation).
        Site: Use parent to auto-assign to current_site.
        """
        current_site = getattr(request, 'current_site', None)
        
        if current_site:
            # In site context: auto-assign to current_site
            super().save_model(request, obj, form, change)
        else:
            # In HQ context: force site=NULL (no site affiliation)
            obj.site = None
            obj.save()
    
    def get_queryset(self, request):
        """
        HQ: Show ALL incidents (site__isnull=True only - HQ incidents).
        Site: Show only incidents for that site (site=current_site).
        """
        qs = super().get_queryset(request)
        
        # Apply archivable filter
        if hasattr(qs.model, 'is_archived'):
            qs = qs.filter(is_archived=False)
        
        current_site = getattr(request, 'current_site', None)
        if current_site:
            # In site context: show only this site's incidents
            qs = qs.filter(site=current_site)
        else:
            # HQ context: show only HQ incidents (site=NULL)
            qs = qs.filter(site__isnull=True)
        
        return qs
    
    fieldsets = (
        ("Incident Information", {
            'fields': (
                'site',
                ('incident_date', 'production_date', 'batch'),
                'location',
                'description'
            )
        }),
        ("Investigation Timeline", {
            'fields': (
                ('investigation_start', 'investigation_end', 'report_date'),
            )
        }),
        ("Responsible Parties", {
            'fields': (
                ('responsible_person', 'management_person'),
            )
        }),
        ("Upload Main Report File", {
            'fields': ('incident_report',)
        }),
        ("System Info", {
            'fields': ('created',),
            'classes': ('collapse',),
        })
    )
    
    def get_fieldsets(self, request, obj=None):
        """
        Override fieldsets to exclude 'site' field in site admin context.
        HQ admin (site=NULL incidents) shows 'site' field.
        Site admin (site=specific) hides 'site' field.
        """
        fieldsets = super().get_fieldsets(request, obj)
        
        # Check if we're in site context (not HQ)
        site_id = request.session.get('current_site_id')
        
        # If in site context, remove 'site' field from fieldsets
        if site_id:
            # Remove 'site' from the fieldsets
            fieldsets = tuple(
                (name, {
                    **config,
                    'fields': tuple(
                        f for f in config.get('fields', ())
                        if f != 'site'  # Remove 'site' field
                    )
                })
                for name, config in fieldsets
            )
        
        return fieldsets
    
    def get_form(self, request, obj=None, **kwargs):
        """
        Override form to exclude 'site' field in site admin context
        and pass request to form for site-aware batch filtering.
        """
        form_class = super().get_form(request, obj, **kwargs)
        
        # Check if we're in site context (not HQ)
        site_id = request.session.get('current_site_id')
        
        # Attach request to form class so form __init__ can access current_site
        form_class._request = request
        
        # If in site context, exclude 'site' from form fields
        if site_id:
            # Create a new form class that excludes 'site'
            class SiteIncidentForm(form_class):
                class Meta(form_class.Meta):
                    fields = [f for f in form_class.Meta.fields if f != 'site']
            
            SiteIncidentForm._request = request
            return SiteIncidentForm
        
        return form_class
