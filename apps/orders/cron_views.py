from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status


class CronAuthMixin:
    def check_token(self, request):
        expected = settings.CRON_SECRET_TOKEN
        received = request.headers.get('X-Cron-Token', '')
        return bool(expected) and received == expected


class ExpireOrdersCronView(CronAuthMixin, APIView):
    """POST /api/cron/expire-orders/ — expira órdenes vencidas."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not self.check_token(request):
            return Response(
                {'detail': 'No autorizado.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        from apps.orders.models import Order
        from apps.orders.services import cancel_order

        now = timezone.now()

        # Limitar a 50 órdenes por ejecución para no colgar el worker
        expired_qs = Order.objects.filter(
            status='pending',
            expires_at__lt=now,
        ).order_by('expires_at')[:50]

        count = 0
        for order in expired_qs:
            if cancel_order(order, new_status='expired'):
                count += 1

        return Response({'detail': f'{count} órdenes expiradas.'})


class SyncMpPaymentsCronView(CronAuthMixin, APIView):
    """POST /api/cron/sync-mp-payments/ — reconcilia pagos aprobados."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not self.check_token(request):
            return Response(
                {'detail': 'No autorizado.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        from apps.payments.tasks import sync_mp_payments_task

        # Solo últimas 3 horas, para no procesar cientos de órdenes
        result = sync_mp_payments_task.__wrapped__(hours=3)
        return Response({'detail': result})


class SendPendingEmailsCronView(CronAuthMixin, APIView):
    """POST /api/cron/send-pending-emails/ — envía emails pendientes."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not self.check_token(request):
            return Response(
                {'detail': 'No autorizado.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        from apps.orders.models import Order
        from apps.orders.tasks import send_purchase_confirmation

        # Solo procesamos 5 emails por ejecución
        # (evita timeouts cuando hay muchas órdenes)
        since = timezone.now() - timedelta(hours=24)
        pending = Order.objects.filter(
            status='paid',
            paid_at__gte=since,
            email_sent=False,
        ).order_by('paid_at')[:5]

        sent_count = 0
        error_count = 0

        for order in pending:
            try:
                send_purchase_confirmation.__wrapped__(str(order.id))
                order.email_sent = True
                order.save(update_fields=['email_sent'])
                sent_count += 1
            except Exception as e:
                print(f"[CRON EMAIL] Error en orden {order.id}: {e}")
                error_count += 1

        return Response({
            'sent': sent_count,
            'errors': error_count,
        })