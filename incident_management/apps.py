from django.apps import AppConfig

class IncidentManagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'incident_management'
    verbose_name = 'Incident Management'
    
    def ready(self):
        import incident_management.signals  # noqa