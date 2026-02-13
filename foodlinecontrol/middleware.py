"""
Multi-site middleware for FoodLineControl.
Handles URL rewriting to serve admin at /hq/{site}/admin/ URLs.
"""
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponseForbidden, Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
import re
import logging

logger = logging.getLogger(__name__)


class SiteAdminMiddleware(MiddlewareMixin):
    """
    Middleware that rewrites /hq/{site}/admin/... URLs to /admin/...
    
    This allows admin to be served at /hq/{site}/admin/ URLs while
    internally routing to the standard Django admin.
    
    URL Structure:
    - /hq/ → HQ Dashboard
    - /hq/admin/tenants/... → HQ Admin (Sites, Users)
    - /hq/{site}/admin/... → Site Admin (rewritten to /admin/...)
    """
    
    def process_request(self, request):
        """Rewrite /hq/{site}/admin/ URLs to /admin/"""
        path = request.path
        # Get query string from META instead of request.GET
        query_string = request.META.get('QUERY_STRING', '')
        
        # If user hits /admin/ directly (not through /hq/), redirect to their site or HQ
        # EXCEPT for login/logout pages which should work standalone
        if path.startswith('/admin/') and not hasattr(request, '_site_slug'):
            # Allow login/logout pages to work without redirection
            if path.startswith('/admin/login') or path.startswith('/admin/logout'):
                return None
            
            # Check if there's a site slug in session from previous access
            site_slug = request.session.get('current_site_slug')
            
            # If not in session, check if user is authenticated with an assigned site
            if not site_slug and request.user.is_authenticated:
                try:
                    from tenants.models import UserSite
                    user_site = UserSite.objects.filter(
                        user=request.user,
                        is_hq_user=False
                    ).first()
                    if user_site and user_site.assigned_site:
                        site_slug = user_site.assigned_site.slug
                except:
                    pass
            
            # Redirect to their site admin or HQ
            if site_slug:
                new_path = path.replace('/admin/', f'/hq/{site_slug}/admin/', 1)
                if query_string:
                    new_path += f'?{query_string}'
                return HttpResponseRedirect(new_path)
            
            # Otherwise redirect to HQ dashboard
            return HttpResponseRedirect('/hq/')
        
        # Match /hq/{site_slug}/admin/...
        match = re.match(r'^/hq/([\w-]+)/admin(/.*)?$', path)
        if not match:
            return None
        
        site_slug = match.group(1)
        admin_path = match.group(2) or '/'
        
        # Don't rewrite 'tenants' - that's the HQ admin
        if site_slug == 'tenants':
            return None
        
        # Get the site and validate access
        from tenants.models import Site
        try:
            site = Site.objects.get(slug=site_slug, is_active=True)
        except Site.DoesNotExist:
            from django.http import Http404
            raise Http404(f"Site '{site_slug}' not found")
        
        # Check user permission
        user = request.user
        if user.is_authenticated:
            if not self._user_can_access_site(user, site):
                return HttpResponseForbidden(f"You don't have access to {site.name}.")
        
        # Store site info in session AND on request object
        request.session['current_site_id'] = site.id
        request.session['current_site_slug'] = site.slug
        request.session['current_site_name'] = site.name
        request.session['is_hq_context'] = False
        request.session.save()  # Save session so it persists
        request.session['is_hq_context'] = False
        
        # IMPORTANT: Set current_site on request for SiteAwareModelAdmin
        request.current_site = site
        
        # Store original path for URL rewriting in response
        request._original_path = path
        request._site_slug = site_slug
        request._site_admin_prefix = f'/hq/{site_slug}/admin'
        
        # Rewrite URL to standard admin path
        request.path = f'/admin{admin_path}'
        request.path_info = f'/admin{admin_path}'
        
        return None
    
    def process_response(self, request, response):
        """Rewrite /admin/ links back to /hq/{site}/admin/"""
        # Only process if we rewrote the URL
        if not hasattr(request, '_site_slug'):
            return response
        
        site_slug = request._site_slug
        
        # Handle HTTP redirects (Location header)
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.get('Location', '')
            logger.debug(f"Redirect Location: {location}")
            
            # Handle different redirect URL formats
            if location:
                # Already has correct prefix - skip
                if f'/hq/{site_slug}/admin/' in location:
                    return response
                
                # Absolute URL with /admin/
                if '/admin/' in location:
                    response['Location'] = location.replace('/admin/', f'/hq/{site_slug}/admin/')
                # Relative URL starting with /admin/
                elif location.startswith('/admin/'):
                    response['Location'] = location.replace('/admin/', f'/hq/{site_slug}/admin/', 1)
                # URL is just "admin/..." without leading slash
                elif location.startswith('admin/'):
                    response['Location'] = f'/hq/{site_slug}/{location}'
                # Relative URL like "../" or same-level
                elif not location.startswith('/') and not location.startswith('http'):
                    # Keep relative as-is, will resolve correctly
                    pass
            return response
        
        # Only rewrite HTML responses
        content_type = response.get('Content-Type', '')
        if 'text/html' not in content_type:
            return response
        
        # Rewrite URLs in response content
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
                
                # Update Content-Length header
                response['Content-Length'] = len(response.content)
            except Exception as e:
                logger.error(f"Error rewriting response URLs: {e}")
        
        return response
    
    def _user_can_access_site(self, user, site):
        """Check if user can access this site"""
        if user.is_superuser:
            return True
        try:
            return user.site_profile.can_access_site(site)
        except:
            return False
