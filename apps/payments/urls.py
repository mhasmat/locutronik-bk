from django.urls import path
from .views import (
    CreateCheckoutView, MercadoPagoWebhookView, checkout_result_view
)

urlpatterns = [
    path('webhook/', MercadoPagoWebhookView.as_view(), name='mp-webhook'),

    # Placeholders para back_urls de MP (mientras no hay frontend)
    path('checkout/success/', lambda r: checkout_result_view(r, 'success'), name='checkout-success'),
    path('checkout/failure/', lambda r: checkout_result_view(r, 'failure'), name='checkout-failure'),
    path('checkout/pending/', lambda r: checkout_result_view(r, 'pending'), name='checkout-pending'),
]