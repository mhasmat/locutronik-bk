from rest_framework import serializers
from .models import Order, Ticket, Settlement


class OrderItemInputSerializer(serializers.Serializer):
    ticket_type = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, max_value=20)


class OrderCreateSerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
    items = OrderItemInputSerializer(many=True, allow_empty=False)


class TicketSerializer(serializers.ModelSerializer):
    ticket_type_name = serializers.CharField(source='ticket_type.name', read_only=True)

    class Meta:
        model = Ticket
        fields = ('id', 'ticket_type', 'ticket_type_name',
                  'price', 'fee', 'qr_code', 'status', 'sold_at', 'used_at')


class OrderDetailSerializer(serializers.ModelSerializer):
    event_name = serializers.CharField(source='event.name', read_only=True)
    event_start = serializers.DateTimeField(source='event.start_time', read_only=True)
    tickets = TicketSerializer(many=True, read_only=True)
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            'id', 'event', 'event_name', 'event_start',
            'subtotal', 'platform_fee', 'total_amount',
            'status', 'created_at', 'expires_at', 'paid_at',
            'is_expired', 'items_snapshot', 'tickets',
        )

    def get_is_expired(self, obj):
        from django.utils import timezone
        return obj.status == 'pending' and obj.expires_at < timezone.now()


class OrderListSerializer(serializers.ModelSerializer):
    event_name = serializers.CharField(source='event.name', read_only=True)

    class Meta:
        model = Order
        fields = ('id', 'event', 'event_name', 'total_amount',
                  'status', 'created_at', 'expires_at')

class PendingOrderSerializer(serializers.ModelSerializer):
    event_name = serializers.CharField(source='event.name', read_only=True)
    class Meta:
        model = Order
        fields = (
            'id', 'event_name', 'subtotal', 'platform_fee', 'total_amount',
            'payment_method', 'paid_at', 'payment_provider'
        )

class SettlementListSerializer(serializers.ModelSerializer):
    producer_username = serializers.CharField(source='producer.username', read_only=True)
    
    class Meta:
        model = Settlement
        fields = (
            'id', 'producer', 'producer_username', 'settlement_type',
            'total_gross', 'total_fee', 'total_net',
            'cash_amount', 'transfer_amount',
            'created_at'
        )