"""
Tenants URL patterns for HQ Admin.
NOTE: This file is not currently used - HQ Admin is mounted directly at /hq/admin/
The actual URLs are served by hq_admin_site.urls in foodlinecontrol/urls.py
"""
from django.urls import path
from .hq_admin import hq_admin_site
from .models import Site, UserSite

# Get model admin instances from HQ admin site
site_admin = hq_admin_site._registry[Site]
usersite_admin = hq_admin_site._registry[UserSite]

app_name = 'tenants'

urlpatterns = [
    # Site management
    path('site/', hq_admin_site.admin_view(site_admin.changelist_view), name='site_changelist'),
    path('site/add/', hq_admin_site.admin_view(site_admin.add_view), name='site_add'),
    path('site/<path:object_id>/change/', hq_admin_site.admin_view(site_admin.change_view), name='site_change'),
    path('site/<path:object_id>/delete/', hq_admin_site.admin_view(site_admin.delete_view), name='site_delete'),
    path('site/<path:object_id>/history/', hq_admin_site.admin_view(site_admin.history_view), name='site_history'),
    
    # UserSite management
    path('usersite/', hq_admin_site.admin_view(usersite_admin.changelist_view), name='usersite_changelist'),
    path('usersite/add/', hq_admin_site.admin_view(usersite_admin.add_view), name='usersite_add'),
    path('usersite/<path:object_id>/change/', hq_admin_site.admin_view(usersite_admin.change_view), name='usersite_change'),
    path('usersite/<path:object_id>/delete/', hq_admin_site.admin_view(usersite_admin.delete_view), name='usersite_delete'),
    path('usersite/<path:object_id>/history/', hq_admin_site.admin_view(usersite_admin.history_view), name='usersite_history'),
]
