from django.urls import path
from . import views

app_name = 'manufacturing'

urlpatterns = [
    # API Endpoints
    path('api/batch-date/', views.get_batch_date, name='api_batch_date'),
    path('api/delete-batch/<int:batch_id>/', views.delete_batch_ajax, name='delete_batch_ajax'),
 
    # Batch Detail View (All Forms with Tabs) - Site-specific
    path('batch/<str:site_slug>/<str:production_date>/detail/', views.production_batch_detail_view, name='batch_detail'),
    path('product-size/<int:pk>/', views.product_size_api, name='product_size_api'),
    path('product-sku-options/<int:pk>/', views.product_sku_options_api, name='product_sku_options_api'),
]