from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AdminCreateSettlementView, AdminPendingSettlementsView, AdminProducerPendingOrdersView, OrderPrintView, OrderViewSet, PosCashRegisterView, PosCloseCashRegisterView, PosCreateOrderView, PosLiquidateEventView, PosOrderSearchView, TicketValidateView, TicketQRView, TicketDownloadView
from apps.payments.views import CreateCheckoutView


router = DefaultRouter()
router.register('', OrderViewSet, basename='order')

# ⚠️ Los path() explícitos van PRIMERO para que no los capture el router
urlpatterns = [
    path('validate-ticket/', TicketValidateView.as_view(), name='validate-ticket'),

    path('<uuid:order_id>/checkout/', CreateCheckoutView.as_view(), name='order-checkout'),
    path('<uuid:order_id>/tickets/<uuid:ticket_id>/qr/', TicketQRView.as_view(), name='ticket-qr'),    
    path('<uuid:order_id>/tickets/<uuid:ticket_id>/download/', TicketDownloadView.as_view(), name='ticket-download'),
    path('<uuid:order_id>/print/', OrderPrintView.as_view(), name='order-print'),
    
    path('pos/', PosCreateOrderView.as_view(), name='pos-create-order'),
    path('search/', PosOrderSearchView.as_view(), name='pos-search'),
    path('pos/cash-register/', PosCashRegisterView.as_view(), name='pos-cash-register'),
    path('pos/close-cash-register/', PosCloseCashRegisterView.as_view(), name='pos-close-cash-register'),
    path('pos/liquidate/', PosLiquidateEventView.as_view(), name='pos-liquidate'),

    path('admin/settlements/pending/', AdminPendingSettlementsView.as_view(), name='admin-pending-settlements'),
    path('admin/settlements/pending/<int:producer_id>/', AdminProducerPendingOrdersView.as_view(), name='admin-producer-pending-orders'),
    path('admin/settlements/create/', AdminCreateSettlementView.as_view(), name='admin-create-settlement'),

] + router.urls