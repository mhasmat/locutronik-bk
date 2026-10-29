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

    FEE_TYPE_CHOICES = [
        ('percentage', 'Porcentaje (%)'),
        ('fixed', 'Monto Fijo ($)'),
    ]
    
    FEE_MODE_CHOICES = [
        ('sum', 'Sumar a la Entrada'),
        ('subtract', 'Deducir de la Entrada'),
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

    # 👇 NUEVOS CAMPOS DE COMISIÓN
    fee_type = models.CharField(max_length=20, choices=FEE_TYPE_CHOICES, default='percentage')
    fee_value = models.DecimalField(max_digits=10, decimal_places=2, default=8.00)
    fee_mode = models.CharField(max_length=20, choices=FEE_MODE_CHOICES, default='sum')    

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
    max_per_user = models.PositiveIntegerField(default=5)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('event', 'name')

    def __str__(self):
        return f"{self.event.name} - {self.name}"

    @property
    def is_sold_out(self):
        return self.quantity_available <= 0


# Crear el modelo de configuración de comisiones
class PlatformConfig(models.Model):    
    FEE_TYPE_CHOICES = [
        ('percentage', 'Porcentaje (%)'),
        ('fixed', 'Monto Fijo ($)'),
    ]    
    fee_type = models.CharField(max_length=20, choices=FEE_TYPE_CHOICES, default='percentage')
    fee_value = models.DecimalField(max_digits=10, decimal_places=2, default=8.00)
    
    # Cuenta de MP de Locutronik (opcional, si querés que cambie)
    mp_locutronik_account = models.CharField(max_length=100, blank=True, null=True)

    def save(self, *args, **kwargs):
        # Asegurarnos de que solo haya un registro (ID=1)
        self.id = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Comisión global: {self.fee_value} {'%' if self.fee_type == 'percentage' else '$'}"