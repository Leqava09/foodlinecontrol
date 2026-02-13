from django.apps import AppConfig

class CostingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'costing'
    
    def ready(self):
        import costing.models    
        import costing.signals 
        import inventory.signals 