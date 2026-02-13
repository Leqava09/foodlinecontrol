"""
Multi-site middleware - Detects current site from URL and manages access control.
Also handles URL rewriting so /hq/{site}/admin/ serves admin without redirect.
"""
import threading
import re
from django.shortcuts import redirect
from django.http import HttpResponseForbidden
from django.urls import resolve

_thread_locals = threading.local()


def get_current_site():
    """Get the current site from thread local storage"""
    return getattr(_thread_locals, 'site', None)


def get_current_user():
    """Get the current user from thread local storage"""
    return getattr(_thread_locals, 'user', None)


def set_current_site(site):
    """Set the current site in thread local storage"""
    _thread_locals.site = site


class SiteMiddleware:
    """
    Middleware to:
    1. Rewrite /hq/{site}/admin/... URLs to /admin/...
    2. Check user has permission to access the site
    3. Store current site in thread local for filtering
    4. Rewrite /admin/ links back to /hq/{site}/admin/ in response
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Clear thread locals
        _thread_locals.site = None
        _thread_locals.user = request.user if request.user.is_authenticated else None
        
        path = request.path
        site_slug = None
        
        # Check for HQ Admin URL: /hq/admin/...
        if path.startswith('/hq/admin/') or path == '/hq/admin':
            # This is HQ admin - set HQ context
            request.session['is_hq_context'] = True
            request.session['current_site_id'] = None
            request.session['current_site_slug'] = None
            request.session['current_site_name'] = None
        
        # Check for site admin URL: /hq/{site_slug}/admin/...
        elif re.match(r'^/hq/([\w-]+)/admin(/.*)?$', path):
            match = re.match(r'^/hq/([\w-]+)/admin(/.*)?$', path)
            site_slug = match.group(1)
            admin_path = match.group(2) or '/'
            
            # Skip 'tenants' - that's the HQ admin (already handled above)
            if site_slug != 'tenants':
                from tenants.models import Site
                try:
                    site = Site.objects.get(slug=site_slug, is_active=True)
                    _thread_locals.site = site
                    request.current_site = site
                    
                    # Store for URL rewriting
                    request._site_slug = site_slug
                    request._original_path = path
                    
                    # Set session variables
                    request.session['current_site_id'] = site.id
                    request.session['current_site_slug'] = site.slug
                    request.session['current_site_name'] = site.name
                    request.session['is_hq_context'] = False
                    
                    # Check access permission
                    if request.user.is_authenticated:
                        if not self._user_can_access_site(request.user, site):
                            return HttpResponseForbidden(f"You don't have access to {site.name}.")
                    
                    # Rewrite URL to /admin/...
                    request.path = f'/admin{admin_path}'
                    request.path_info = f'/admin{admin_path}'
                    
                except Site.DoesNotExist:
                    from django.http import Http404
                    raise Http404(f"Site '{site_slug}' not found")
        
        # Check HQ dashboard access for /hq/
        elif path == '/hq/' or path == '/hq':
            if request.user.is_authenticated:
                if not self._user_is_hq(request.user):
                    # Site users CANNOT access HQ at all - redirect to their site
                    site_redirect = self._get_user_site_redirect(request.user)
                    if site_redirect:
                        return redirect(site_redirect)
                    return HttpResponseForbidden(
                        "❌ Access Denied: This account is restricted to site access only. "
                        "You cannot access the HQ dashboard. Please contact your administrator."
                    )
            # Allow unauthenticated access (login page will redirect appropriately)
        
        # BLOCK direct /admin/ access - must go through /hq/{site}/admin/
        # EXCEPT login/logout which must work standalone
        elif path.startswith('/admin/'):
            # Allow login/logout pages to work without redirection
            if path.startswith('/admin/login') or path.startswith('/admin/logout'):
                pass  # Allow these through
            else:
                # Check if user is authenticated and is a site user (not HQ)
                if request.user.is_authenticated:
                    if not self._user_is_hq(request.user):
                        # Site user - redirect to their assigned site
                        site_redirect = self._get_user_site_redirect(request.user)
                        if site_redirect:
                            # Append the admin path to the site redirect
                            admin_path = path.replace('/admin', '', 1)
                            return redirect(site_redirect.rstrip('/') + admin_path if admin_path else site_redirect)
                
                # If user has a site in session, redirect to that site's admin
                site_slug = request.session.get('current_site_slug')
                if site_slug:
                    new_path = path.replace('/admin/', f'/hq/{site_slug}/admin/', 1)
                    return redirect(new_path)
                
                # HQ users or no context - redirect to HQ dashboard
                if request.user.is_authenticated and self._user_is_hq(request.user):
                    return redirect('/hq/')
                
                # Site user without assigned site - show error
                if request.user.is_authenticated:
                    return HttpResponseForbidden(
                        "❌ No site assigned. Please contact your administrator."
                    )
                
                # Not authenticated - let Django handle login redirect
                return redirect('/hq/')
        
        # Get the response
        request.current_site = getattr(_thread_locals, 'site', None)
        response = self.get_response(request)
        
        # Rewrite URLs in response if we're in a site context
        if hasattr(request, '_site_slug'):
            response = self._rewrite_response_urls(request, response)
        
        # Clean up
        _thread_locals.site = None
        _thread_locals.user = None
        
        return response
    
    def _rewrite_response_urls(self, request, response):
        """Rewrite /admin/ URLs back to /hq/{site}/admin/ in response"""
        site_slug = request._site_slug
        
        # Only rewrite HTML responses
        content_type = response.get('Content-Type', '')
        if 'text/html' not in content_type:
            return response
        
        if hasattr(response, 'content'):
            try:
                content = response.content.decode('utf-8')
                
                # Replace /admin/ links with /hq/{site_slug}/admin/
                content = content.replace('href="/admin/', f'href="/hq/{site_slug}/admin/')
                content = content.replace('action="/admin/', f'action="/hq/{site_slug}/admin/')
                content = content.replace("href='/admin/", f"href='/hq/{site_slug}/admin/")
                content = content.replace("action='/admin/", f"action='/hq/{site_slug}/admin/")
                content = content.replace('"/admin/', f'"/hq/{site_slug}/admin/')
                
                response.content = content.encode('utf-8')
                response['Content-Length'] = len(response.content)
            except Exception:
                pass
        
        return response
    
    def _user_can_access_site(self, user, site):
        """Check if user can access a specific site"""
        if user.is_superuser:
            return True
        
        try:
            # Use site_profiles (plural) - it's a ForeignKey, not OneToOne
            user_site = user.site_profiles.filter(is_archived=False).first()
            if user_site:
                return user_site.can_access_site(site)
            return False
        except:
            return False
    
    def _user_is_hq(self, user):
        """Check if user is an HQ user"""
        # Superusers are always HQ users
        if user.is_superuser:
            return True
        
        try:
            # Use site_profiles (plural) - it's a ForeignKey, not OneToOne
            user_site = user.site_profiles.filter(is_hq_user=True, is_archived=False).first()
            return user_site is not None
        except:
            return False
    
    def _get_user_site_redirect(self, user):
        """Get the URL to redirect a site user to their site"""
        try:
            # Use site_profiles (plural) - it's a ForeignKey, not OneToOne
            user_site = user.site_profiles.filter(is_archived=False).first()
            if user_site and user_site.assigned_site:
                return f'/hq/{user_site.assigned_site.slug}/admin/'
        except:
            pass
        return None
