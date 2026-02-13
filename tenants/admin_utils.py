"""
Site-aware admin utilities for multi-tenant data isolation.
"""
from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponseRedirect
from tenants.models import get_current_site


class SiteAwareModelAdmin(admin.ModelAdmin):
    """
    Admin class that provides site-based data isolation.
    
    - Filters queryset to show only current site's data
    - Auto-assigns site when saving new records
    - HQ users (when at /hq/admin/tenants/) see all data
    """
    
    # Override to exclude 'site' from the form if desired
    exclude_site_from_form = True
    
    def _get_site_admin_url(self, request, url):
        """Convert /admin/ URL to /hq/{site}/admin/ URL"""
        site_slug = getattr(request, '_site_slug', None)
        if site_slug and '/admin/' in url and f'/hq/{site_slug}/admin/' not in url:
            return url.replace('/admin/', f'/hq/{site_slug}/admin/')
        return url
    
    def response_add(self, request, obj, post_url_continue=None):
        """Override to fix redirect URL after add"""
        response = super().response_add(request, obj, post_url_continue)
        if isinstance(response, HttpResponseRedirect):
            response['Location'] = self._get_site_admin_url(request, response['Location'])
        return response
    
    def response_change(self, request, obj):
        """Override to fix redirect URL after change"""
        response = super().response_change(request, obj)
        if isinstance(response, HttpResponseRedirect):
            response['Location'] = self._get_site_admin_url(request, response['Location'])
        return response
    
    def response_delete(self, request, obj_display, obj_id):
        """Override to fix redirect URL after delete"""
        response = super().response_delete(request, obj_display, obj_id)
        if isinstance(response, HttpResponseRedirect):
            response['Location'] = self._get_site_admin_url(request, response['Location'])
        return response
    
    def get_queryset(self, request):
        """
        Filter queryset based on site context.
        
        HQ (/hq/admin/): See all data across all sites
        Site (/hq/site-slug/admin/): See ONLY this site's data (no cross-site access, no global sharing)
        """
        qs = super().get_queryset(request)
        
        # Get current site from request (set by middleware)
        current_site = getattr(request, 'current_site', None)
        
        if current_site:
            # In a site context - show ONLY this site's data (no global sharing, no other sites)
            return qs.filter(site=current_site)
        else:
            # HQ context (/hq/admin/) - show ALL data across all sites
            return qs
    
    def save_model(self, request, obj, form, change):
        """Auto-assign site and company when creating new records"""
        if not change:  # Only on create, not update
            current_site = getattr(request, 'current_site', None)
            if current_site and not obj.site_id:
                obj.site = current_site
        
        # For models with 'company' field (like BillingDocumentHeader, PurchaseOrder),
        # ALWAYS set the correct company based on site
        if hasattr(obj, 'company'):
            from commercial.models import CompanyDetails
            if obj.site:
                # Site records: use site's company
                obj.company = CompanyDetails.objects.filter(site=obj.site, is_active=True).first()
            elif not getattr(request, 'current_site', None):
                # HQ records (site=NULL): use HQ company
                obj.company = CompanyDetails.objects.filter(site__isnull=True, is_active=True).first()
        
        super().save_model(request, obj, form, change)
    
    def get_exclude(self, request, obj=None):
        """Optionally exclude 'site' field from form"""
        exclude = list(super().get_exclude(request, obj) or [])
        
        # Hide site field in site admin (auto-assigned)
        if self.exclude_site_from_form:
            current_site = getattr(request, 'current_site', None)
            if current_site and 'site' not in exclude:
                exclude.append('site')
        
        return exclude
    
    def get_list_display(self, request):
        """Optionally show site column for HQ users"""
        list_display = list(super().get_list_display(request))
        
        # Show site column only in HQ context
        current_site = getattr(request, 'current_site', None)
        if not current_site and hasattr(self.model, 'site'):
            if 'site' not in list_display:
                list_display.append('site')
        
        return list_display
    
    def has_add_permission(self, request):
        """Allow adding when in site context"""
        # Always allow add for superusers
        if request.user.is_superuser:
            return True
        # Check parent permission
        return super().has_add_permission(request)
    
    def has_change_permission(self, request, obj=None):
        """Allow changing when in site context"""
        if request.user.is_superuser:
            return True
        return super().has_change_permission(request, obj)
    
    def has_delete_permission(self, request, obj=None):
        """Allow deleting when in site context"""
        if request.user.is_superuser:
            return True
        return super().has_delete_permission(request, obj)


class SiteAwareTabularInline(admin.TabularInline):
    """Tabular inline that respects site context"""
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        current_site = getattr(request, 'current_site', None)
        if current_site and hasattr(self.model, 'site'):
            return qs.filter(site=current_site)
        return qs


class SiteAwareStackedInline(admin.StackedInline):
    """Stacked inline that respects site context"""
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        current_site = getattr(request, 'current_site', None)
        if current_site and hasattr(self.model, 'site'):
            return qs.filter(site=current_site)
        return qs
