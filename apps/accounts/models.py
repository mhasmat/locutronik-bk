from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    is_producer = models.BooleanField(
        default=False,
        help_text="Marca True si el usuario puede crear eventos."
    )

    is_pos_operator = models.BooleanField(
        default=False,
        help_text="Marca True si el usuario opera el Punto de Venta (Boletería)."
    )
    phone = models.CharField(max_length=30, blank=True)
    document_number = models.CharField(max_length=30, blank=True)

    def __str__(self):
        return self.username
