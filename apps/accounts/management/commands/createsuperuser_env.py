import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Crea un superusuario desde variables de entorno."

    def handle(self, *args, **options):
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

        if not all([username, email, password]):
            self.stdout.write(self.style.WARNING(
                "Faltan variables DJANGO_SUPERUSER_* — saltando creacion."
            ))
            return

        if User.objects.filter(username=username).exists():
            self.stdout.write(f"Usuario '{username}' ya existe.")
            return

        User.objects.create_superuser(username, email, password)
        self.stdout.write(self.style.SUCCESS(
            f"Superusuario '{username}' creado correctamente."
        ))