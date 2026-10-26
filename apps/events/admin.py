from django.contrib import admin
from .models import Venue, Event, TicketType, PlatformConfig


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'capacity')
    search_fields = ('name', 'city')


class TicketTypeInline(admin.TabularInline):
    model = TicketType
    extra = 1


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    # 👇 Quitamos platform_fee_percent de la lista
    list_display = ('name', 'organizer', 'start_time', 'status', 'fee_type', 'fee_value')
    list_filter = ('status', 'start_time', 'fee_type')
    search_fields = ('name', 'organizer__username')
    inlines = [TicketTypeInline]


@admin.register(TicketType)
class TicketTypeAdmin(admin.ModelAdmin):
    list_display = ('event', 'name', 'price', 'quantity_total', 'quantity_available')
    list_filter = ('event',)


@admin.register(PlatformConfig)
class PlatformConfigAdmin(admin.ModelAdmin):
    """
    Configuración global de la plataforma.
    Solo debería haber un registro (ID=1) que se edita, no se crean nuevos.
    """
    list_display = ('fee_type', 'fee_value', 'mp_locutronik_account')

    def has_add_permission(self, request):
        # Bloquea el botón de "Agregar" si ya existe un registro
        if PlatformConfig.objects.exists():
            return False
        return True

    def has_delete_permission(self, request, obj=None):
        # Bloquea el botón de "Eliminar" para no romper el sistema
        return False