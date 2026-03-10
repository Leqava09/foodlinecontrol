"""
HQ Dashboard view for multi-site FoodLineControl
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.http import HttpResponseForbidden
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from tenants.models import Site


def is_hq_user(user):
    """Check if user is a superuser or HQ admin"""
    if user.is_superuser:
        return True
    try:
        return user.site_profile.is_hq_user
    except Exception:
        return False


@csrf_protect
@require_http_methods(["POST"])
def custom_logout(request):
    """
    Custom logout view that redirects to the appropriate login page.
    
    If user is logged out from a site admin:
        - Redirect to site-specific login (Grappelli login at /hq/{site}/admin/login/)
    If user is logged out from HQ admin:
        - Redirect to HQ login (/hq/login/)
    """
    # Get the site context BEFORE logout clears the session
    current_site_slug = request.session.get('current_site_slug')
    is_hq_context = request.session.get('is_hq_context', False)
    
    # Determine redirect URL before logout
    if current_site_slug and not is_hq_context:
        # Site user - redirect to site admin login
        redirect_url = f'/hq/{current_site_slug}/admin/login/'
    else:
        # HQ user - redirect to HQ login
        redirect_url = '/hq/login/'
    
    # Perform the logout
    logout(request)
    
    # Redirect to appropriate login page
    return redirect(redirect_url)


@login_required
def hq_dashboard(request):
    """
    HQ Dashboard - shows all sites.
    URL: /hq/
    
    Only HQ users and superusers can access this view.
    Site users are redirected to their assigned site.
    """
    # Check if user is HQ user
    if not is_hq_user(request.user):
        # Try to redirect to their site
        try:
            user_site = request.user.site_profile
            if user_site.assigned_site:
                return redirect(f'/hq/{user_site.assigned_site.slug}/admin/')
        except Exception:
            pass
        return HttpResponseForbidden("You don't have access to HQ dashboard.")
    
    # Clear any site-specific session (we're at HQ level now)
    request.session['current_site_id'] = None
    request.session['current_site_slug'] = None
    request.session['current_site_name'] = None
    request.session['is_hq_context'] = True  # Mark that we're in HQ context
    
    # Get active sites (not archived)
    sites = Site.objects.filter(is_active=True, is_archived=False).order_by('name')
    
    # Get archived sites
    archived_sites = Site.objects.filter(is_archived=True).order_by('name')
    
    context = {
        'title': 'HQ Dashboard - Manufacturing Sites',
        'sites': sites,
        'archived_sites': archived_sites,
        'is_hq': True,
        'current_user': request.user,
        'site_count': sites.count(),
        'archived_count': archived_sites.count(),
    }
    
    return render(request, 'hq/home.html', context)
