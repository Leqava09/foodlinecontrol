# costing/urls.py

from django.urls import path
from . import views
from .views import (
    billing_document_preview,
    email_billing_document,
)
app_name = 'costing'

urlpatterns = [
    path(
        'api/batch-summary-items/<str:production_date_str>/',
        views.batch_summary_items_api,
        name='batch_summary_items_api',
    ),
    path(
        'api/batch-approvals/save/',
        views.save_batch_approvals,
        name='save-batch-approvals',
    ),
    path(
        'admin/batch-price-approval/<int:pk>/update/',
        views.update_batch_price_approval,
        name='admin_update_batch_price_approval',
    ),
    path(
        "api/batch-pricing-preview/<str:pk>/",
        views.batch_pricing_preview_api,
        name="batch_pricing_preview_api",
    ),
    path(
        "billing/<int:pk>/<str:doc_type>/",
        views.billing_document_preview,
        name="billing_document_preview",
    ),
    path('billing/email/<int:pk>/<str:doc_type>/', email_billing_document, name='email_billing_document'),
    path('api/dates-to-batch-costings/', views.dates_to_batch_costings, name='dates_to_batch_costings'),
    path('api/get-site-invoice-data/', views.get_site_invoice_data, name='get_site_invoice_data'),
]
