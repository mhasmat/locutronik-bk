from django.core.management.base import BaseCommand
from apps.orders.tasks import expire_pending_orders


class Command(BaseCommand):
    help = "Expira órdenes pending vencidas y devuelve el stock."

    def handle(self, *args, **options):
        result = expire_pending_orders()
        self.stdout.write(self.style.SUCCESS(result))