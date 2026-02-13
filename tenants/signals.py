"""
Signals for multi-site tenant management.

Auto-creates dummy UserSite records on all sites when an HQ user is created.
This allows HQ users to appear as regular site users, while being unaware to the sites
that these users are actually HQ-managed.
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from tenants.models import UserSite, Site
import logging

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=UserSite)
def validate_hq_credentials(sender, instance, **kwargs):
    """
    Validate that HQ credentials are only set when is_hq_user=True.
    Auto-hash password if provided.
    """
    # If is_hq_user but no hq_username, raise error
    if instance.is_hq_user and not instance.hq_username:
        logger.warning(f"UserSite {instance.user.username}: is_hq_user=True but no hq_username provided")
    
    # If HQ password is provided as plain text, hash it
    if instance.hq_password and not instance.hq_password.startswith('pbkdf2_'):
        # It's not already hashed, so hash it
        instance.set_hq_password(instance.hq_password)
    
    # If NOT is_hq_user, clear HQ credentials (site users don't need them)
    if not instance.is_hq_user:
        instance.hq_username = None
        instance.hq_password = None


# DISABLED - This signal was causing issues with HQ user creation
# @receiver(post_save, sender=UserSite)
# def auto_create_dummy_site_records(sender, instance, created, **kwargs):
#     """
#     When an HQ user (is_hq_user=True) is created or updated:
#     1. Create dummy UserSite records on ALL sites (so sites see them as regular users)
#     2. When is_hq_user is changed to False, delete dummy records
#     
#     This allows:
#     - HQ users to access all sites
#     - Sites to show HQ users as regular site users (unaware of HQ)
#     - HQ users to appear on sites they weren't explicitly assigned to
#     """
#     # Only process if this is the master HQ UserSite
#     if instance.is_archived:
#         return  # Don't process archived users
#     
#     if instance.is_hq_user:
#         # This is an HQ user - create dummy records on all sites
#         all_sites = Site.objects.filter(is_active=True, is_archived=False)
#         
#         for site in all_sites:
#             # Check if dummy record already exists
#             dummy, was_created = UserSite.objects.get_or_create(
#                 user=instance.user,
#                 assigned_site=site,
#                 defaults={
#                     'is_hq_user': False,  # Dummy records are NOT marked as HQ users
#                     'hq_username': None,
#                     'hq_password': None,
#                 }
#             )
#             
#             if was_created:
#                 logger.info(
#                     f"Created dummy UserSite for HQ user {instance.user.username} on site {site.name}"
#                 )
#     else:
#         # This is a regular site user - ensure no dummy records exist
#         # Delete any dummy records for this user on other sites
#         # (Keep only the assigned site record)
#         UserSite.objects.filter(
#             user=instance.user,
#             assigned_site__isnull=False
#         ).exclude(assigned_site=instance.assigned_site).delete()


# DISABLED - This signal was also causing issues
# @receiver(post_save, sender=Site)
# def create_dummy_records_for_new_site(sender, instance, created, **kwargs):
#     """
#     When a new site is created:
#     Create dummy UserSite records for ALL existing HQ users on this new site.
#     """
#     if not created or instance.is_archived:
#         return
#     
#     # Get all HQ users
#     hq_users = UserSite.objects.filter(
#         is_hq_user=True,
#         is_archived=False
#     ).select_related('user')
#     
#     # Create dummy records on the new site
#     for user_site in hq_users:
#         dummy, was_created = UserSite.objects.get_or_create(
#             user=user_site.user,
#             assigned_site=instance,
#             defaults={
#                 'is_hq_user': False,
#                 'hq_username': None,
#                 'hq_password': None,
#             }
#         )
#         
#         if was_created:
#             logger.info(
#                 f"Created dummy UserSite for HQ user {user_site.user.username} on new site {instance.name}"
#             )


@receiver(pre_save, sender=UserSite)
def handle_hq_user_change(sender, instance, **kwargs):
    """
    When is_hq_user is changed from False to True:
    Auto-create dummy records on all sites.
    
    This runs BEFORE post_save, so we just flag the change.
    """
    try:
        old_instance = UserSite.objects.get(pk=instance.pk)
        # Store the old is_hq_user value for post_save to check
        instance._was_hq_user = old_instance.is_hq_user
    except UserSite.DoesNotExist:
        # This is a new instance
        instance._was_hq_user = False
