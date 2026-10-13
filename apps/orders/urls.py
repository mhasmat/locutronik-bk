from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import OrderViewSet, TicketValidateView, TicketQRView
from apps.payments.views import CreateCheckoutView


router = DefaultRouter()
router.register('', OrderViewSet, basename='order')

# ⚠️ Los path() explícitos van PRIMERO para que no los capture el router
urlpatterns = [
    path(
        'validate-ticket/',
        TicketValidateView.as_view(),
        name='validate-ticket',
    ),
    path(
        '<uuid:order_id>/checkout/',
        CreateCheckoutView.as_view(),
        name='order-checkout',
    ),
    path(
        '<uuid:order_id>/tickets/<uuid:ticket_id>/qr/',
        TicketQRView.as_view(),
        name='ticket-qr',
    ),
] + router.urls