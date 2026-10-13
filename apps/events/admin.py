from django.contrib import admin
from .models import Venue, Event, TicketType


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'capacity')
    search_fields = ('name', 'city')


class TicketTypeInline(admin.TabularInline):
    model = TicketType
    extra = 1


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'organizer', 'start_time', 'status', 'platform_fee_percent')
    list_filter = ('status', 'start_time')
    search_fields = ('name', 'organizer__username')
    inlines = [TicketTypeInline]


@admin.register(TicketType)
class TicketTypeAdmin(admin.ModelAdmin):
    list_display = ('event', 'name', 'price', 'quantity_total', 'quantity_available')
    list_filter = ('event',)