import io
import qrcode
import datetime

from django.db.models import Q, Sum, Count
from django.http import HttpResponse
from .ticket_image import generate_ticket_image
from django.utils import timezone

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Order, Ticket, CashRegister
from .serializers import (
    OrderCreateSerializer, OrderDetailSerializer, OrderListSerializer
)
from .services import create_order, cancel_order

from django.contrib.auth import get_user_model
from .services import create_order, confirm_order_payment
from rest_framework.permissions import BasePermission
from django.http import HttpResponse
from .ticket_image import generate_thermal_ticket


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


class TicketDownloadView(APIView):
    """
    GET /api/orders/<order_id>/tickets/<ticket_id>/download/
    Genera y descarga la imagen completa del ticket en PNG.
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

        try:
            # Generamos la imagen en memoria
            pdf_bytes = generate_ticket_image(ticket)
            
            # La devolvemos como archivo adjunto
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="entrada-{str(ticket.id)[:8]}.pdf"'
            return response
        except Exception as e:
            return Response({'detail': f'Error generando la entrada: {str(e)}'}, status=500)


class IsPosOperator(BasePermission):
    """Permiso personalizado para operadores de POS y Admins."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and 
                    (request.user.is_pos_operator or request.user.is_staff))

class PosCreateOrderView(APIView):
    """
    POST /api/orders/pos/
    Crea una orden presencial pagada en el acto.
    """
    permission_classes = [IsPosOperator]

    def post(self, request):
        event_id = request.data.get('event_id')
        items = request.data.get('items', [])
        payment_method = request.data.get('payment_method', 'cash')
        guest_email = request.data.get('guest_email', '')

        if not event_id or not items:
            return Response({'detail': 'Faltan datos del evento o los tickets.'}, status=400)

        # 1. Buscamos o creamos el "Cliente Genérico POS"
        User = get_user_model()
        pos_user, _ = User.objects.get_or_create(
            username='pos_cliente',
            defaults={
                'email': 'pos@locutronik.local',
                'first_name': 'Cliente',
                'last_name': 'Presencial',
                'is_active': False
            }
        )

        # 2. Creamos la orden usando tu servicio existente (esto reserva el stock)
        order, error = create_order(pos_user, event_id, items)
        if error:
            return Response({'detail': error}, status=400)

        # 3. La pagamos inmediatamente (genera los tickets)
        order.created_by = request.user
        order.payment_method = payment_method
        if guest_email:
            # Lo guardamos temporalmente en el snapshot o en el user genérico si querés
            pass 
        order.save()

        confirm_order_payment(order, payment_provider=payment_method, payment_reference='POS-VENTA')

        return Response({
            'detail': 'Venta presencial exitosa.',
            'order_id': str(order.id),
            'total': order.total_amount
        }, status=201)

class PosOrderSearchView(APIView):
    """GET /api/orders/search/?q=..."""
    permission_classes = [IsPosOperator] # El permiso que creamos antes

    def get(self, request):
        query = request.query_params.get('q', '').strip()
        if not query:
            return Response([])

        # Buscamos por ID exacto o por email del comprador
        orders = Order.objects.filter(
            Q(id__icontains=query) | Q(user__email__icontains=query)
        ).filter(status='paid').order_by('-paid_at')[:10] # Traemos las últimas 10

        serializer = OrderDetailSerializer(orders, many=True)
        return Response(serializer.data)

class OrderPrintView(APIView):
    """
    GET /api/orders/<order_id>/print/
    Genera un PDF optimizado para impresora térmica de 80mm.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id)
            
            # 👇 Lógica de permisos mejorada
            is_owner = (request.user == order.user)
            is_organizer = (request.user == order.event.organizer)
            is_pos_or_admin = (getattr(request.user, 'is_pos_operator', False) or getattr(request.user, 'is_staff', False))

            if not (is_owner or is_organizer or is_pos_or_admin):
                return Response({'detail': 'No autorizado para imprimir esta orden.'}, status=403)
            
            ticket = order.tickets.first()
            if not ticket:
                return Response({'detail': 'La orden no tiene tickets generados.'}, status=400)
                
            pdf_bytes = generate_thermal_ticket(ticket)
            
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="ticket-{str(order.id)[:8]}.pdf"'
            return response
            
        except Order.DoesNotExist:
            return Response({'detail': 'Orden no encontrada.'}, status=404)


class PosCashRegisterView(APIView):
    """GET /api/orders/pos/cash-register/?date=YYYY-MM-DD -> Resumen Z"""
    permission_classes = [IsPosOperator]

    def get(self, request):
        date_str = request.query_params.get('date') or timezone.now().date().isoformat()
        try:
            target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'detail': 'Formato de fecha inválido.'}, status=400)

        # Órdenes POS del día
        orders = Order.objects.filter(status='paid', created_by__isnull=False, paid_at__date=target_date)

        totals = orders.aggregate(
            total_revenue=Sum('total_amount'),
            total_fee=Sum('platform_fee'),
            total_producer=Sum('subtotal'),
            total_tickets=Count('tickets')
        )
        
        cash_amount = orders.filter(payment_method='cash').aggregate(amount=Sum('total_amount'))['amount'] or 0
        transfer_amount = orders.filter(payment_method='transfer').aggregate(amount=Sum('total_amount'))['amount'] or 0

        # ¿Ya existe un cierre para esta fecha?
        existing_close = CashRegister.objects.filter(closed_at__date=target_date).first()

        return Response({
            'date': target_date,
            'summary': {
                'total_revenue': totals['total_revenue'] or 0,
                'total_fee': totals['total_fee'] or 0,
                'total_producer': totals['total_producer'] or 0,
                'total_tickets': totals['total_tickets'] or 0,
                'cash_amount': cash_amount,
                'transfer_amount': transfer_amount,
            },
            'is_closed': bool(existing_close),
            'closed_details': existing_close.notes if existing_close else None,
        })

class PosCloseCashRegisterView(APIView):
    """POST /api/orders/pos/cash-register/close/"""
    permission_classes = [IsPosOperator]

    def post(self, request):
        date_str = request.data.get('date')
        actual_cash = float(request.data.get('actual_cash', 0))
        notes = request.data.get('notes', '')

        try:
            target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return Response({'detail': 'Fecha inválida.'}, status=400)
            
        if CashRegister.objects.filter(closed_at__date=target_date).exists():
             return Response({'detail': 'Esta caja ya fue cerrada.'}, status=400)

        orders = Order.objects.filter(status='paid', created_by__isnull=False, paid_at__date=target_date)
        expected_cash = orders.filter(payment_method='cash').aggregate(amount=Sum('total_amount'))['amount'] or 0

        diff = actual_cash - float(expected_cash)

        register = CashRegister.objects.create(
            operator=request.user,
            closed_at=timezone.now(),
            expected_cash=expected_cash,
            actual_cash=actual_cash,
            difference=diff,
            notes=notes
        )

        return Response({'detail': 'Caja cerrada correctamente.', 'difference': diff})

class PosLiquidateEventView(APIView):
    """
    POST /api/orders/pos/liquidate/
    Marca todas las órdenes de un evento en una fecha específica como liquidadas.
    """
    permission_classes = [IsPosOperator]

    def post(self, request):
        event_id = request.data.get('event_id')
        date_str = request.data.get('date')

        if not event_id or not date_str:
            return Response({'detail': 'Faltan datos (event_id y date).'}, status=400)

        try:
            target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'detail': 'Formato de fecha inválido.'}, status=400)

        # Buscamos las órdenes vendidas por el POS para ese evento y fecha, que NO estén liquidadas
        orders = Order.objects.filter(
            status='paid',
            created_by__isnull=False,
            event_id=event_id,
            paid_at__date=target_date,
            liquidated_at__isnull=True
        )

        count = orders.count()
        if count == 0:
            return Response({'detail': 'No hay órdenes pendientes de liquidar para este evento en esta fecha.'}, status=400)

        # Las marcamos como liquidadas
        orders.update(liquidated_at=timezone.now())

        return Response({
            'detail': f'{count} órdenes liquidadas correctamente.',
            'event_id': event_id
        }, status=200)