from django.apps import AppConfig

class ManufacturingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'manufacturing'
    
    def ready(self):
        """Import signals when app is ready"""
        import manufacturing.signals  # ← ADD THIS LINE
