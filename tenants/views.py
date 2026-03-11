"""
Site-specific views for multi-site support
"""
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.contrib.sessions.models import Session
from django.contrib.auth import get_user_model
from django.conf import settings
from .models import Site, UserSite

User = get_user_model()


@csrf_protect
@require_http_methods(["GET", "POST"])
def hq_login(request):
    """
    Custom HQ login view using hq_username and hq_password.
    
    GET: Display login form
    POST: Authenticate and create session
    """
    if request.method == 'GET':
        return render(request, 'hq/login.html', {'error': None})
    
    # POST: Handle login
    hq_username = request.POST.get('hq_username', '').strip()
    hq_password = request.POST.get('hq_password', '').strip()
    next_url = request.POST.get('next', '/hq/')
    
    # Validate redirect URL to prevent open redirects
    from django.utils.http import url_has_allowed_host_and_scheme
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts=set(settings.ALLOWED_HOSTS), require_https=request.is_secure()):
        next_url = '/hq/'
    
    if not hq_username or not hq_password:
        return render(request, 'hq/login.html', {
            'error': 'Please enter both username and password.',
            'hq_username': hq_username
        })
    
    try:
        # Find HQ user with matching credentials
        user_site = UserSite.objects.get(
            hq_username=hq_username,
            is_hq_user=True,
            is_archived=False
        )
        
        # Check password
        if not user_site.check_hq_password(hq_password):
            return render(request, 'hq/login.html', {
                'error': 'Invalid username or password.',
                'hq_username': hq_username
            })
        
        # Create or get Django User for this HQ user using get_or_create
        # This safely handles the case where the user already exists
        django_user, created = User.objects.get_or_create(
            username=f'hq_{hq_username}',
            defaults={
                'password': '',  # No password needed for HQ users
                'first_name': hq_username,
                'is_active': True,
                'is_staff': True,     # HQ users need staff status to access admin
                'is_superuser': True  # HQ users have full admin privileges
            }
        )
        
        # Ensure all required flags are True for HQ users (in case user already existed)
        needs_save = False
        if not django_user.is_active:
            django_user.is_active = True
            needs_save = True
        if not django_user.is_staff:
            django_user.is_staff = True
            needs_save = True
        if not django_user.is_superuser:
            django_user.is_superuser = True
            needs_save = True
        if needs_save:
            django_user.save()
        
        # Link the Django user to the UserSite if not already linked
        if not user_site.user:
            user_site.user = django_user
            user_site.save()
        
        # Update the existing user's display name and email to match UserSite
        needs_save = False
        if django_user.first_name != hq_username:
            django_user.first_name = hq_username
            needs_save = True
        if user_site.email and django_user.email != user_site.email:
            django_user.email = user_site.email
            needs_save = True
        if needs_save:
            django_user.save()
        
        # Login the user manually (create session)
        request.session['_auth_user_id'] = django_user.pk
        request.session['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
        request.session['_auth_user_hash'] = django_user.get_session_auth_hash()
        request.session['_hq_authenticated'] = True
        
        # Mark session as HQ
        request.session['is_hq_context'] = True
        request.session.save()
        
        # Redirect to next URL or HQ dashboard
        return redirect(next_url if next_url else '/hq/')
    
    except UserSite.DoesNotExist:
        return render(request, 'hq/login.html', {
            'error': 'Invalid username or password.',
            'hq_username': hq_username
        })


@login_required
def site_admin_redirect(request, site_slug, path=''):
    """
    Sets site context in session, then redirects to /admin/...
    
    URL: /hq/{site_slug}/admin/... -> /admin/...
    
    The URL changes but the session tracks which site the user is working with.
    The admin template shows "Back to HQ" link based on session.
    """
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
    
    # Redirect to admin with the path
    return redirect(f'/admin/{path}')


from django.http import JsonResponse
from django.views.decorators.http import require_GET

@login_required
@require_GET
def get_batch_details(request, batch_id):
    """
    AJAX endpoint to get batch details (product name, size) for billing inline.
    Returns JSON with product and size.
    """
    from manufacturing.models import Batch
    
    try:
        batch = Batch.objects.select_related('product').get(pk=batch_id)
        product_name = batch.product.product_name if batch.product else '-'
        size = batch.size or '-'
        
        return JsonResponse({
            'success': True,
            'product': product_name,
            'size': size,
        })
    except Batch.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Batch not found',
            'product': '-',
            'size': '-',
        })
