import io
import qrcode

from django.http import HttpResponse
from django.utils import timezone

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Order, Ticket
from .serializers import (
    OrderCreateSerializer, OrderDetailSerializer, OrderListSerializer
)
from .services import create_order, cancel_order


class OrderViewSet(viewsets.GenericViewSet,
                   viewsets.mixins.ListModelMixin,
                   viewsets.mixins.RetrieveModelMixin):
    """
    - list: mis órdenes
    - retrieve: detalle de una orden
    - create: crear orden (con reserva de stock)
    - cancel: cancelar orden pendiente
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            Order.objects
            .filter(user=self.request.user)
            .select_related('event')
            .prefetch_related('tickets')
        )

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        if self.action == 'list':
            return OrderListSerializer
        return OrderDetailSerializer

    def create(self, request, *args, **kwargs):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order, error = create_order(
            user=request.user,
            event_id=serializer.validated_data['event_id'],
            items=serializer.validated_data['items'],
        )

        if error:
            return Response({'detail': error}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            OrderDetailSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        order = self.get_object()
        if cancel_order(order):
            return Response({'detail': 'Orden cancelada correctamente.'})
        return Response(
            {'detail': 'Solo se pueden cancelar órdenes pendientes.'},
            status=status.HTTP_400_BAD_REQUEST,
        )


class TicketValidateView(APIView):
    """
    POST /api/orders/validate-ticket/
    Body: { "qr_code": "..." }
    Solo el productor dueño del evento puede validar.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        qr_code = request.data.get('qr_code', '').strip()
        if not qr_code:
            return Response({'detail': 'qr_code requerido.'}, status=400)

        try:
            ticket = Ticket.objects.select_related('order__event', 'order__user').get(
                qr_code=qr_code
            )
        except Ticket.DoesNotExist:
            return Response({'detail': 'Ticket inválido.'}, status=404)

        # Verificar que el que valida sea el organizador del evento
        if ticket.order.event.organizer != request.user:
            return Response(
                {'detail': 'No sos el organizador de este evento.'},
                status=403,
            )

        if ticket.status == 'used':
            return Response({
                'detail': 'Este ticket ya fue usado.',
                'used_at': ticket.used_at,
            }, status=400)

        if ticket.status == 'cancelled':
            return Response({'detail': 'Ticket cancelado.'}, status=400)

        ticket.status = 'used'
        ticket.used_at = timezone.now()
        ticket.save(update_fields=['status', 'used_at'])

        return Response({
            'detail': 'Acceso permitido.',
            'ticket': {
                'id': str(ticket.id),
                'ticket_type': ticket.ticket_type.name,
                'holder': ticket.order.user.username,
                'event': ticket.order.event.name,
            },
        })


class TicketQRView(APIView):
    """
    GET /api/orders/<order_id>/tickets/<ticket_id>/qr/
    Devuelve la imagen PNG del QR del ticket.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, order_id, ticket_id):
        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            return Response({'detail': 'Orden no encontrada.'}, status=404)

        try:
            ticket = order.tickets.get(id=ticket_id)
        except Ticket.DoesNotExist:
            return Response({'detail': 'Ticket no encontrado.'}, status=404)

        img = qrcode.make(ticket.qr_code)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return HttpResponse(buf.getvalue(), content_type='image/png')