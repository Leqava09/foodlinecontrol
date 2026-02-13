"""
Tenants Admin - This file intentionally does NOT register Site/UserSite
with the default admin.site.

Site and UserSite are registered ONLY in HQ Admin (/hq/admin/)
See: tenants/hq_admin.py

This keeps the site-level admin clean - only site-specific apps show up.
"""
from django.contrib import admin
from .models import Site, UserSite

# DO NOT register Site or UserSite here!
# They are registered in hq_admin.py with the HQ admin site.
# This ensures they don't appear in the regular /admin/ at all.

