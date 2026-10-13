from django.conf import settings
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status


class CronAuthMixin:
    """Mixin que valida un token en el header para permitir la ejecución."""

    def check_token(self, request):
        expected = settings.CRON_SECRET_TOKEN
        received = request.headers.get('X-Cron-Token', '')
        if not expected or received != expected:
            return False
        return True


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

        # Importamos acá para no cargar Celery al inicio
        from apps.orders.services import cancel_order
        from apps.orders.models import Order
        from django.utils import timezone

        now = timezone.now()
        expired_qs = Order.objects.filter(status='pending', expires_at__lt=now)

        count = 0
        for order in expired_qs.iterator():
            if cancel_order(order, new_status='expired'):
                count += 1

        return Response({'detail': f'{count} órdenes expiradas.'})


class SyncMpPaymentsCronView(CronAuthMixin, APIView):
    """POST /api/cron/sync-mp-payments/ — reconcilia pagos aprobados con órdenes."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not self.check_token(request):
            return Response(
                {'detail': 'No autorizado.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        from apps.payments.tasks import sync_mp_payments_task

        # Ejecutamos la función directamente (no por Celery)
        result = sync_mp_payments_task.__wrapped__(hours=2)
        return Response({'detail': result})


class SendPendingEmailsCronView(CronAuthMixin, APIView):
    """
    POST /api/cron/send-pending-emails/
    Busca órdenes pagadas que no tengan email enviado y los manda.
    """
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

        # Órdenes pagadas en los últimos 30 min que aún no tienen email enviado
        # Usamos el campo paid_at como referencia + un flag que agregaremos
        from django.utils import timezone
        from datetime import timedelta

        since = timezone.now() - timedelta(minutes=30)
        pending = Order.objects.filter(
            status='paid',
            paid_at__gte=since,
            email_sent=False,   # ← vamos a agregar este campo
        )

        count = 0
        for order in pending:
            try:
                send_purchase_confirmation.__wrapped__(str(order.id))
                order.email_sent = True
                order.save(update_fields=['email_sent'])
                count += 1
            except Exception as e:
                print(f"[CRON] Error enviando email de orden {order.id}: {e}")

        return Response({'detail': f'{count} emails enviados.'})