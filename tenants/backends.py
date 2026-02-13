"""
Custom authentication backend for HQ users.
Authenticates using hq_username and hq_password instead of Django User credentials.
"""
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model
from tenants.models import UserSite

User = get_user_model()


class HQAuthenticationBackend(BaseBackend):
    """
    Authenticate HQ users using hq_username and hq_password.
    """
    
    def authenticate(self, request, hq_username=None, hq_password=None, **kwargs):
        """
        Authenticate user with hq_username and hq_password.
        Returns User object if successful, None otherwise.
        """
        if not hq_username or not hq_password:
            return None
        
        try:
            # Find UserSite with matching hq_username
            user_site = UserSite.objects.get(
                hq_username=hq_username,
                is_hq_user=True,
                is_archived=False
            )
            
            # Check if password is correct
            if user_site.check_hq_password(hq_password):
                # Return the associated Django User (or create a minimal one if needed)
                # For now, we'll return None and handle this in the view
                return user_site
            
        except UserSite.DoesNotExist:
            pass
        
        return None
    
    def get_user(self, user_id):
        """
        Get user by ID (not used for HQ auth, but required by backend interface).
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
