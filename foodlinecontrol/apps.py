from django.apps import AppConfig

class GoshenErpConfig(AppConfig):
    name = "foodlinecontrol"

    def ready(self):
        # Import admin override when app is ready
        from . import auth_admin  # noqa
        from . import auth_signals  # noqa - Register user signals
        
        # Monkey-patch admin site to move DeletionRequest under auth section
        from django.contrib import admin
        
        original_get_app_list = admin.site.get_app_list
        
        def patched_get_app_list(request, app_label=None):
            """Move DeletionRequest from foodlinecontrol to auth section"""
            app_list = original_get_app_list(request, app_label)
            
            auth_app = None
            foodlinecontrol_app = None
            deletion_request_model = None
            
            for app in app_list:
                if app['app_label'] == 'auth':
                    auth_app = app
                elif app['app_label'] == 'foodlinecontrol':
                    foodlinecontrol_app = app
            
            # Move DeletionRequest from foodlinecontrol to auth
            if foodlinecontrol_app and auth_app:
                for model in foodlinecontrol_app.get('models', []):
                    if model.get('object_name') == 'DeletionRequest':
                        deletion_request_model = model
                        break
                
                if deletion_request_model:
                    # Remove from foodlinecontrol
                    foodlinecontrol_app['models'] = [
                        m for m in foodlinecontrol_app.get('models', [])
                        if m.get('object_name') != 'DeletionRequest'
                    ]
                    
                    # Add to auth
                    auth_app['models'].append(deletion_request_model)
                    
                    # If foodlinecontrol has no more models, remove it
                    if not foodlinecontrol_app.get('models'):
                        app_list = [a for a in app_list if a['app_label'] != 'foodlinecontrol']
            
            return app_list
        
        admin.site.get_app_list = patched_get_app_list

