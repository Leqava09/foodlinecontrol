from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # Existing AJAX endpoints
    path('ajax/get-batch-qty/', views.get_batch_qty, name='get_batch_qty'),
    path('get-unit/<int:stock_item_id>/', views.get_unit, name='get_unit'),
    path('get-currency/', views.get_site_currency, name='get_site_currency'),
    path('stockitem/<int:pk>/', views.get_stockitem, name='get_stockitem'), 
    path('api/stockitem/<int:pk>/json/', views.get_stockitem, name='get_stockitem_json'),
    path('get-stockitem/', views.get_stockitem_by_batch, name='get_stockitem_batch'),
    path('get-prod-batches/<str:date_string>/', views.get_prod_batches, name='get_prod_batches'),
    path('finished/get-batches/', views.get_finished_batches_for_date, name='get_finished_batches_for_date'),
    path(
        'admin-api/batch-ready/',
        views.batch_ready_dispatch_api,
        name='batch_ready_dispatch_api',
    ),
    path('api/finished-product/available/<str:batch_id>/', views.api_finished_product_available, name='api_finished_product_available'),
    path('available_stock/', views.available_stock, name='available_stock'),
    path('api/delivery-sites/', views.api_delivery_sites, name='api_delivery_sites'),
    path('api/batches-for-date/', views.api_batches_for_date, name='api_batches_for_date'),
    
    # Purchase Order document endpoints
    path('po/<int:pk>/preview/', views.po_document_preview, name='po_document_preview'),
    path('po/<int:pk>/email/', views.email_po_document, name='email_po_document'),
]