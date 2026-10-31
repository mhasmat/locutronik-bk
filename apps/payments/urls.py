from django.urls import path
from .views import (
    CreateCheckoutView, 
    MPOAuthCallbackView, 
    MPOAuthUrlView, 
    MercadoPagoWebhookView, 
    checkout_result_view
)

urlpatterns = [
    # Webhook para recibir notificaciones de MP
    path('webhook/', MercadoPagoWebhookView.as_view(), name='mp-webhook'),

    # Placeholders para back_urls de MP (por si acaso)
    path('checkout/success/', lambda r: checkout_result_view(r, 'success'), name='checkout-success'),
    path('checkout/failure/', lambda r: checkout_result_view(r, 'failure'), name='checkout-failure'),
    path('checkout/pending/', lambda r: checkout_result_view(r, 'pending'), name='checkout-pending'),

    # Rutas nuevas para el Marketplace (Split Payments)
    path('mp/oauth/url/', MPOAuthUrlView.as_view(), name='mp-oauth-url'),
    path('mp/oauth/callback/', MPOAuthCallbackView.as_view(), name='mp-oauth-callback'),
]