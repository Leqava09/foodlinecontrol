from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

admin.autodiscover()

import foodlinecontrol.auth_admin
from foodlinecontrol.views import hq_dashboard, custom_logout
from tenants.hq_admin import hq_admin_site
from tenants.views import hq_login, get_batch_details

urlpatterns = [
    # Root URL redirects to HQ dashboard
    path('', lambda request: redirect('/hq/')),
    
    # Grappelli (must be before admin)
    path('grappelli/', include('grappelli.urls')),

    # Custom logout - redirects to site login or HQ login based on context
    path('admin/logout/', custom_logout, name='custom_logout'),
    
    # HQ Login - custom login for HQ users with hq_username/hq_password
    path('hq/login/', hq_login, name='hq_login'),
    
    # HQ Dashboard - exact match for /hq/
    path('hq/', hq_dashboard, name='hq_dashboard'),
    
    # API endpoint for batch details (for billing inline)
    path('api/batch/<str:batch_id>/details/', get_batch_details, name='api_batch_details'),
    
    # HQ Admin (Sites, Users) at /hq/admin/ - for managing Sites and UserSites
    path('hq/admin/', hq_admin_site.urls),
    
    # Site admin URLs: /hq/{site}/admin/... 
    # Handled by SiteAdminMiddleware which rewrites to /admin/
    # No explicit URL pattern needed - middleware intercepts first
    
    # Default admin - serves both /admin/ and /hq/{site}/admin/ (via middleware)
    path('admin/', admin.site.urls),
    
    # App URLs
    path('inventory/', include('inventory.urls')),
    path('chaining/', include('smart_selects.urls')),
    path('manufacturing/', include('manufacturing.urls')),  
    path('nested_admin/', include('nested_admin.urls')),
    path('costing/', include('costing.urls')), 
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)