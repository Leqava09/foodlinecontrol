from django.apps import AppConfig

class ProductDetailsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'product_details'
    verbose_name = "Product Details"  # This is the display name
