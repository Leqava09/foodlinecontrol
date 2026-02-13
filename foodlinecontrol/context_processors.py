"""
Custom context processors for the FoodLineControl admin.
"""

def admin_background(request):
    """
    Adds admin_background_url to template context from the current Site's background image.
    Falls back to CompanyDetails if no site context.
    """
    # First try to get from current site (set by middleware)
    current_site = getattr(request, 'current_site', None)
    if current_site and current_site.admin_background:
        return {'admin_background_url': current_site.admin_background.url}
    
    # Fallback to HQ CompanyDetails (site=NULL) for backward compatibility
    from commercial.models import CompanyDetails
    try:
        company = CompanyDetails.objects.filter(site__isnull=True, is_active=True).first()
        if company and company.admin_background:
            return {'admin_background_url': company.admin_background.url}
    except:
        pass
    
    return {'admin_background_url': None}


def site_context(request):
    """
    Adds site-related context for navigation:
    - current_site_name: Name of current site (if accessing via /hq/{site}/admin/)
    - current_site_slug: Slug of current site
    - is_hq_user: Whether the user can access HQ
    - user_home_url: Where the user should go when clicking "Home"
    """
    context = {
        'current_site_name': None,
        'current_site_slug': None,
        'is_hq_user': False,
        'user_home_url': '/admin/',
    }
    
    if not request.user.is_authenticated:
        return context
    
    # Check if user is HQ user
    # Superusers are always HQ users
    is_hq = False
    if request.user.is_superuser:
        is_hq = True
    else:
        try:
            # Use site_profiles (plural) - it's a ForeignKey, not OneToOne
            user_site = request.user.site_profiles.filter(is_hq_user=True, is_archived=False).first()
            is_hq = user_site is not None
        except:
            pass
    context['is_hq_user'] = is_hq
    
    # Get current site from session (set by SiteAdminView)
    site_name = request.session.get('current_site_name')
    site_slug = request.session.get('current_site_slug')
    
    if site_name:
        context['current_site_name'] = site_name
        context['current_site_slug'] = site_slug
        
        # Set home URL based on user type
        if is_hq:
            context['user_home_url'] = '/hq/'
        else:
            context['user_home_url'] = f'/hq/{site_slug}/admin/'
    else:
        # Not in a site context
        if is_hq:
            context['user_home_url'] = '/hq/'
        else:
            # Try to get user's assigned site
            try:
                # Use site_profiles (plural)
                user_site = request.user.site_profiles.filter(is_archived=False).first()
                if user_site and user_site.assigned_site:
                    context['user_home_url'] = f'/hq/{user_site.assigned_site.slug}/admin/'
            except:
                pass
    
    return context
