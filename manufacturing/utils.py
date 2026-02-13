from django.contrib.admin.models import LogEntry, CHANGE, ADDITION, DELETION
from django.contrib.contenttypes.models import ContentType

def log_model_change(user, model_instance, action_flag, change_message):
    """Reusable function to log changes to admin history"""
    if not user or not user.is_authenticated:
        return  # Don't log if no user
    
    LogEntry.objects.create(
        user=user,
        content_type=ContentType.objects.get_for_model(model_instance),
        object_id=model_instance.id,
        object_repr=str(model_instance),
        action_flag=action_flag,
        change_message=change_message
    )

def log_field_change(user, model_instance, field_name, old_value, new_value):
    """Log a specific field change"""
    change_msg = f'{field_name}: "{old_value}" → "{new_value}"'
    log_model_change(user, model_instance, CHANGE, change_msg)
