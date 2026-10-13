from rest_framework import serializers


class TicketTypeSummarySerializer(serializers.Serializer):
    ticket_type_id = serializers.IntegerField()
    name = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    quantity_total = serializers.IntegerField()
    quantity_sold = serializers.IntegerField()
    quantity_available = serializers.IntegerField()
    gross_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    platform_fee = serializers.DecimalField(max_digits=12, decimal_places=2)


class EventSummarySerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
    event_name = serializers.CharField()
    event_start = serializers.DateTimeField()
    status = serializers.CharField()

    tickets_sold = serializers.IntegerField()
    tickets_available = serializers.IntegerField()
    tickets_total = serializers.IntegerField()

    gross_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    platform_fee = serializers.DecimalField(max_digits=12, decimal_places=2)
    net_to_organizer = serializers.DecimalField(max_digits=12, decimal_places=2)

    orders_paid = serializers.IntegerField()
    orders_pending = serializers.IntegerField()

    ticket_types = TicketTypeSummarySerializer(many=True)


class TicketSaleSerializer(serializers.Serializer):
    ticket_id = serializers.UUIDField()
    order_id = serializers.UUIDField()
    ticket_type = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    fee = serializers.DecimalField(max_digits=10, decimal_places=2)
    status = serializers.CharField()
    buyer_username = serializers.CharField()
    sold_at = serializers.DateTimeField()
    used_at = serializers.DateTimeField(allow_null=True)


class PayoutSerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
    event_name = serializers.CharField()

    gross_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    platform_fee = serializers.DecimalField(max_digits=12, decimal_places=2)
    net_to_organizer = serializers.DecimalField(max_digits=12, decimal_places=2)

    tickets_sold = serializers.IntegerField()
    average_ticket_price = serializers.DecimalField(max_digits=10, decimal_places=2)

    # Si en el futuro agregás comisiones de MP o retenciones, se descuentan acá
    mp_processing_fee = serializers.DecimalField(max_digits=12, decimal_places=2)
    final_payout = serializers.DecimalField(max_digits=12, decimal_places=2)