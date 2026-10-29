import json
from rest_framework import serializers
from django.utils import timezone
from .models import Venue, Event, TicketType, PlatformConfig


class VenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = ('id', 'name', 'address', 'city', 'capacity')


class TicketTypeSerializer(serializers.ModelSerializer):
    is_sold_out = serializers.BooleanField(read_only=True)

    class Meta:
        model = TicketType
        fields = (
            'id', 'name', 'description',
            'price', 'quantity_total', 'quantity_available',
            'max_per_user', 'is_active', 'is_sold_out',
        )
        read_only_fields = ('quantity_available',)


class EventListSerializer(serializers.ModelSerializer):
    venue = VenueSerializer(read_only=True)
    organizer_username = serializers.CharField(source='organizer.username', read_only=True)
    min_price = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = (
            'id', 'name', 'image', 'start_time', 'end_time',
            'status', 'venue', 'organizer_username', 'min_price',
            'fee_type', 'fee_value', 'fee_mode' # 👈
        )

    def get_min_price(self, obj):
        tt = obj.ticket_types.filter(is_active=True).order_by('price').first()
        return str(tt.price) if tt else None


class EventDetailSerializer(serializers.ModelSerializer):
    venue = VenueSerializer()
    ticket_types = TicketTypeSerializer(many=True, read_only=True)
    organizer_username = serializers.CharField(source='organizer.username', read_only=True)

    class Meta:
        model = Event
        fields = (
            'id', 'name', 'description', 'image',
            'venue', 'ticket_types',
            'start_time', 'end_time', 'sale_start_time', 'sale_end_time',
            'status', 'fee_type', 'fee_value', 'fee_mode',# 👈
            'organizer', 'organizer_username',
            'created_at', 'updated_at',
        )
        read_only_fields = ('organizer', 'created_at', 'updated_at')


class TicketTypeInputSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = TicketType
        fields = (
            'id', 'name', 'description', 'price',
            'quantity_total', 'max_per_user', 'is_active',
        )


class EventCreateUpdateSerializer(serializers.ModelSerializer):
    ticket_types = TicketTypeInputSerializer(many=True, required=False)
    image = serializers.ImageField(required=True)

    class Meta:
        model = Event
        fields = (
            'id', 'name', 'description', 'image', 'venue',
            'start_time', 'end_time', 'sale_start_time', 'sale_end_time',
            'status', 'ticket_types',
            'fee_type', 'fee_value', 'fee_mode' # 👈
        )

    def to_internal_value(self, data):
        # 1. Convertimos el QueryDict inmutable a un diccionario normal
        if hasattr(data, 'dict'):
            data = data.dict()
        else:
            data = dict(data)

        # 2. Parseamos ticket_types si viene como string JSON
        if 'ticket_types' in data:
            val = data['ticket_types']
            print(f"🔍 DEBUG: ticket_types recibido como: {type(val)} -> {val}")
            if isinstance(val, str):
                try:
                    import json
                    data['ticket_types'] = json.loads(val)
                except json.JSONDecodeError as e:
                    print(f"❌ ERROR parseando ticket_types: {e}")
                    data['ticket_types'] = []

        # 3. Manejamos la imagen
        if 'image' in data:
            img = data.get('image')
            if not img or img == 'null' or img == '' or isinstance(img, str):
                data.pop('image', None)

        return super().to_internal_value(data)

    def validate_image(self, value):
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError('La imagen no puede superar los 5 MB.')
        allowed_types = ['image/jpeg', 'image/png', 'image/webp']
        if hasattr(value, 'content_type') and value.content_type not in allowed_types:
            raise serializers.ValidationError('Formato no soportado. Usá JPG, PNG o WEBP.')
        return value

    def validate(self, attrs):
        if self.instance is None and 'image' not in attrs:
            raise serializers.ValidationError({'image': 'La imagen es obligatoria para crear un evento.'})

        # 👇 VALIDACIONES DE COMISIÓN
        fee_type = attrs.get('fee_type', 'percentage')
        fee_value = attrs.get('fee_value', 8.00)
        
        if fee_type == 'percentage':
            if not (5.00 <= float(fee_value) <= 20.00):
                raise serializers.ValidationError({'fee_value': 'El porcentaje debe estar entre 5% y 20%.'})
        else:
            if not (1000.00 <= float(fee_value) <= 100000.00):
                raise serializers.ValidationError({'fee_value': 'El monto fijo debe estar entre $1.000 y $100.000.'})

        
        start = attrs.get('start_time')
        end = attrs.get('end_time')
        sale_start = attrs.get('sale_start_time')
        sale_end = attrs.get('sale_end_time')

        if start and end and end <= start:
            raise serializers.ValidationError({'end_time': 'Debe ser posterior al inicio.'})
        if sale_start and sale_end and sale_end <= sale_start:
            raise serializers.ValidationError({'sale_end_time': 'Debe ser posterior al inicio de venta.'})
        if sale_end and start and sale_end > start:
            raise serializers.ValidationError({'sale_end_time': 'La venta debe cerrar antes del inicio del evento.'})

        ticket_types = attrs.get('ticket_types', [])
        names = [tt.get('name', '').strip().lower() for tt in ticket_types if tt.get('name')]
        if len(names) != len(set(names)):
            raise serializers.ValidationError({'ticket_types': 'No puede haber dos tipos de entrada con el mismo nombre.'})

        return attrs

    def create(self, validated_data):
        ticket_types_data = validated_data.pop('ticket_types', [])
        event = Event.objects.create(**validated_data)

        for tt_data in ticket_types_data:
            tt_data.pop('id', None)
            tt_data['quantity_available'] = tt_data.get('quantity_total', 0)
            TicketType.objects.create(event=event, **tt_data)

        return event

    def update(self, instance, validated_data):
        ticket_types_data = validated_data.pop('ticket_types', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if ticket_types_data is None:
            return instance

        existing = {tt.id: tt for tt in instance.ticket_types.all()}
        seen_names = set()

        for tt_data in ticket_types_data:
            tt_id = tt_data.pop('id', None)
            name = tt_data.get('name', '').strip()

            if name.lower() in seen_names:
                raise serializers.ValidationError({'ticket_types': f'El nombre "{name}" está repetido.'})
            seen_names.add(name.lower())

            if tt_id and tt_id not in existing:
                raise serializers.ValidationError({'ticket_types': f'El ticket type con id={tt_id} no pertenece a este evento.'})

            if tt_id:
                tt = existing[tt_id]
                for field in ('name', 'description', 'price', 'max_per_user', 'is_active'):
                    if field in tt_data:
                        setattr(tt, field, tt_data[field])

                if 'quantity_total' in tt_data:
                    new_total = tt_data['quantity_total']
                    diff = new_total - tt.quantity_total
                    tt.quantity_total = new_total
                    tt.quantity_available = max(0, tt.quantity_available + diff)

                tt.save()
            else:
                tt_data['quantity_available'] = tt_data.get('quantity_total', 0)
                TicketType.objects.create(event=instance, **tt_data)

        return instance