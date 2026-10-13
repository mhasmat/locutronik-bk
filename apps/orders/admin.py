from django.contrib import admin
from .models import Order, Ticket


class TicketInline(admin.TabularInline):
    model = Ticket
    extra = 0
    readonly_fields = ('id', 'price', 'fee', 'qr_code', 'sold_at')
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'event', 'total_amount', 'platform_fee', 'status', 'created_at')
    list_filter = ('status', 'event', 'created_at')
    search_fields = ('id', 'user__username', 'payment_reference')
    readonly_fields = ('id', 'created_at')
    inlines = [TicketInline]


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'ticket_type', 'price', 'fee', 'status', 'sold_at')
    list_filter = ('status', 'ticket_type__event')
    search_fields = ('id', 'order__id', 'qr_code')
    readonly_fields = ('id', 'sold_at')