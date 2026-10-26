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

    # guardar en ID de MP del productor
    mp_user_id = models.CharField(
        max_length=100, blank=True, null=True,
        help_text="ID de cuenta de Mercado Pago (Collector ID) obtenido vía OAuth."
    )

    def __str__(self):
        return self.username
