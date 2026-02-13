"""
Custom URL routing for site-aware smart-selects chaining endpoints.
"""

from django.urls import path
from . import views

urlpatterns = [
    # Custom chaining endpoint for Product that filters by site
    path(
        'chaining/<str:app>/<str:model>/<str:parent_field>/<str:current_app>/'
        '<str:current_model>/<str:field>/<int:parent_id>/',
        views.site_aware_chaining_view,
        name='site_aware_chaining'
    ),
]
