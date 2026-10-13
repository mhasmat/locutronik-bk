from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from apps.orders.models import Order
from apps.orders.services import confirm_order_payment
from apps.payments.services import get_payment_info, get_mp_sdk


class Command(BaseCommand):
    help = (
        "Reconcilia órdenes pending/expired con pagos aprobados en Mercado Pago. "
        "Útil como red de seguridad si el webhook falló."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Solo revisar órdenes de las últimas N horas (default: 24).',
        )

    def handle(self, *args, **options):
        hours = options['hours']
        since = timezone.now() - timedelta(hours=hours)

        orders = Order.objects.filter(
            status__in=['pending', 'expired'],
            payment_provider='mercadopago',
            created_at__gte=since,
        ).exclude(payment_reference='')

        count = orders.count()
        self.stdout.write(f"Órdenes a revisar (últimas {hours}h): {count}")

        if count == 0:
            return

        sdk = get_mp_sdk()
        confirmed = 0
        checked = 0

        for order in orders:
            checked += 1
            self.stdout.write(
                f"\n[{checked}/{count}] Orden {order.id} (status={order.status})"
            )

            result = sdk.payment().search({
                'external_reference': str(order.id),
                'sort': 'date_created',
                'criteria': 'desc',
            })

            if result.get('status') != 200:
                self.stdout.write(self.style.WARNING(
                    f"  Error al buscar pagos: {result.get('status')}"
                ))
                continue

            payments = result['response'].get('results', [])
            if not payments:
                self.stdout.write("  Sin pagos asociados.")
                continue

            # Tomamos el más reciente
            payment = payments[0]
            status = payment.get('status')
            pid = payment.get('id')
            self.stdout.write(f"  Pago {pid} → status='{status}'")

            if status == 'approved':
                # Si estaba expired, la pasamos a pending para poder confirmarla
                if order.status == 'expired':
                    order.status = 'pending'
                    order.save(update_fields=['status'])
                    self.stdout.write("  Orden reactivada a 'pending'.")

                if confirm_order_payment(order, 'mercadopago', str(pid)):
                    confirmed += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"  ✓ Orden {order.id} confirmada y tickets generados."
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f"  La orden {order.id} no se pudo confirmar."
                    ))

        self.stdout.write(self.style.SUCCESS(
            f"\n--- Resumen ---"
            f"\nRevisadas: {checked}"
            f"\nConfirmadas: {confirmed}"
        ))