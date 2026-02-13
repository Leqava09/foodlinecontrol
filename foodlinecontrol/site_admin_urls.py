"""
Site Admin URL Configuration

This module serves the Django admin at /hq/{site_slug}/admin/
It wraps the standard admin.site with site context middleware.
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import get_object_or_404
from django.http import HttpResponseForbidden
from functools import wraps


def site_admin_wrapper(view_func):
    """
    Wrapper that sets site context before calling admin view.
    Extracts site_slug from URL and sets session variables.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from tenants.models import Site
        
        # Get site_slug from the URL resolver match
        site_slug = request.resolver_match.kwargs.get('site_slug')
        if not site_slug:
            # Try to get from captured groups in parent URL
            site_slug = kwargs.pop('site_slug', None)
        
        if site_slug:
            # Get the site
            site = get_object_or_404(Site, slug=site_slug, is_active=True)
            
            # Check permission
            if not _user_can_access_site(request.user, site):
                return HttpResponseForbidden(f"You don't have access to {site.name}.")
            
            # Set site context in session
            request.session['current_site_id'] = site.id
            request.session['current_site_slug'] = site.slug
            request.session['current_site_name'] = site.name
            request.session['is_hq_context'] = False
            
            # Store on request object too
            request.current_site = site
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def _user_can_access_site(user, site):
    """Check if user can access this site"""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    try:
        return user.site_profile.can_access_site(site)
    except:
        return False


class SiteAdminSite(admin.AdminSite):
    """
    Custom AdminSite that serves at /hq/{site}/admin/
    """
    
    def admin_view(self, view, cacheable=False):
        """Wrap admin views with site context"""
        wrapped = super().admin_view(view, cacheable)
        return site_admin_wrapper(wrapped)


# Create a site-aware admin instance
site_admin = SiteAdminSite(name='site_admin')

# Copy all registrations from the default admin to our site admin
# This must be done after all apps have registered their models
def setup_site_admin():
    """Copy model registrations from default admin to site admin"""
    from django.contrib.admin.sites import site as default_site
    
    for model, admin_class in default_site._registry.items():
        # Don't copy Tenant models - they belong in HQ admin only
        if model._meta.app_label == 'tenants':
            continue
        try:
            site_admin.register(model, type(admin_class))
        except admin.sites.AlreadyRegistered:
            pass


# The URL patterns - these will be mounted at /hq/{site_slug}/admin/
# The site_slug is captured by the parent URL pattern
app_name = 'site_admin'

urlpatterns = admin.site.urls[0]  # Get just the URL patterns, not the tuple
