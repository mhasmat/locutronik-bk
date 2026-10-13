from django.conf import settings
from django.db import models


class Venue(models.Model):
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=500)
    city = models.CharField(max_length=100, blank=True)
    capacity = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Event(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Borrador'),
        ('published', 'Publicado'),
        ('cancelled', 'Cancelado'),
        ('finished', 'Finalizado'),
    ]

    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='organized_events'
    )
    venue = models.ForeignKey(Venue, on_delete=models.PROTECT, related_name='events')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='events/', blank=True, null=True)

    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    sale_start_time = models.DateTimeField()
    sale_end_time = models.DateTimeField()

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # Porcentaje del fee que cobra la plataforma (ej: 8.00 = 8%)
    platform_fee_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=8.00
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['status', 'start_time']),
        ]

    def __str__(self):
        return f"{self.name} ({self.start_time:%Y-%m-%d})"


class TicketType(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='ticket_types')
    name = models.CharField(max_length=100)  # "Campo", "Platea Alta", etc.
    description = models.CharField(max_length=200, blank=True)

    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_total = models.PositiveIntegerField()
    quantity_available = models.PositiveIntegerField()

    max_per_user = models.PositiveIntegerField(default=4)

    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('event', 'name')

    def __str__(self):
        return f"{self.event.name} - {self.name}"

    @property
    def is_sold_out(self):
        return self.quantity_available <= 0