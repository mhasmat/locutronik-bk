import uuid
from django.conf import settings
from django.db import models
from apps.events.models import Event, TicketType


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('paid', 'Pagada'),
        ('cancelled', 'Cancelada'),
        ('expired', 'Expirada'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders')
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name='orders')

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)

    # Datos de pago (a completar con el webhook)
    payment_provider = models.CharField(max_length=50, blank=True)
    payment_reference = models.CharField(max_length=200, blank=True)

    email_sent = models.BooleanField(default=False)

    # 👇 NUEVOS CAMPOS
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name='pos_orders',
        help_text="Operador de POS que realizó la venta (null si fue online)"
    )
    payment_method = models.CharField(
        max_length=20, 
        default='mercadopago',
        help_text="mercadopago, cash, transfer, etc."
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Orden {self.id} - {self.user} - {self.status}"

    # Nuevo: snapshot de los items al momento de crear la orden
    items_snapshot = models.JSONField(
        default=list,
        help_text="Detalle de items al crear la orden (para generar tickets tras el pago)."
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'expires_at']),  # para el cleanup
        ]


class Ticket(models.Model):
    STATUS_CHOICES = [
        ('valid', 'Válido'),
        ('used', 'Usado'),
        ('cancelled', 'Cancelado'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='tickets')
    ticket_type = models.ForeignKey(TicketType, on_delete=models.PROTECT, related_name='tickets')

    price = models.DecimalField(max_digits=10, decimal_places=2)
    fee = models.DecimalField(max_digits=10, decimal_places=2)

    qr_code = models.CharField(max_length=255, unique=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='valid')
    sold_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-sold_at']

    def __str__(self):
        return f"Ticket {self.id} - {self.ticket_type.name}"