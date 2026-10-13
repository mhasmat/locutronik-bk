from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from apps.orders.models import Order
from apps.orders.services import confirm_order_payment
from .services import get_mp_sdk


@shared_task(name='apps.payments.tasks.sync_mp_payments_task')
def sync_mp_payments_task(hours=2):
    """
    Reconcilia órdenes pending/expired con pagos aprobados en MP.
    Corre cada 10 minutos para las últimas 2 horas.
    """
    since = timezone.now() - timedelta(hours=hours)

    orders = Order.objects.filter(
        status__in=['pending', 'expired'],
        payment_provider='mercadopago',
        created_at__gte=since,
    ).exclude(payment_reference='')

    if not orders.exists():
        return "Sin órdenes para reconciliar."

    sdk = get_mp_sdk()
    confirmed = 0

    for order in orders:
        try:
            result = sdk.payment().search({
                'external_reference': str(order.id),
                'sort': 'date_created',
                'criteria': 'desc',
            })

            if result.get('status') != 200:
                continue

            payments = result['response'].get('results', [])
            if not payments:
                continue

            payment = payments[0]
            if payment.get('status') == 'approved':
                if order.status == 'expired':
                    order.status = 'pending'
                    order.save(update_fields=['status'])

                if confirm_order_payment(order, 'mercadopago', str(payment.get('id'))):
                    confirmed += 1
        except Exception:
            # No rompemos el loop si una orden falla
            continue

    return f"{confirmed} órdenes reconciliadas."