import json
from rest_framework import serializers
from django.utils import timezone
from .models import Venue, Event, TicketType


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
    """Serializer liviano para listados."""
    venue = VenueSerializer(read_only=True)
    organizer_username = serializers.CharField(source='organizer.username', read_only=True)
    min_price = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = (
            'id', 'name', 'image', 'start_time', 'end_time',
            'status', 'venue', 'organizer_username', 'min_price',
        )

    def get_min_price(self, obj):
        tt = obj.ticket_types.filter(is_active=True).order_by('price').first()
        return str(tt.price) if tt else None


class EventDetailSerializer(serializers.ModelSerializer):
    """Serializer completo, con tipos de ticket anidados."""
    venue = VenueSerializer()
    ticket_types = TicketTypeSerializer(many=True, read_only=True)
    organizer_username = serializers.CharField(source='organizer.username', read_only=True)

    class Meta:
        model = Event
        fields = (
            'id', 'name', 'description', 'image',
            'venue', 'ticket_types',
            'start_time', 'end_time', 'sale_start_time', 'sale_end_time',
            'status', 'platform_fee_percent',
            'organizer', 'organizer_username',
            'created_at', 'updated_at',
        )
        read_only_fields = ('organizer', 'created_at', 'updated_at')


class TicketTypeInputSerializer(serializers.ModelSerializer):
    """
    Serializer específico para el input de ticket_types.
    A diferencia del serializer de lectura, este SÍ permite enviar 'id'
    para actualizar uno existente.
    """
    id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = TicketType
        fields = (
            'id', 'name', 'description', 'price',
            'quantity_total', 'max_per_user', 'is_active',
        )


class EventCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer para crear/editar. El organizador se asigna automáticamente."""
    ticket_types = TicketTypeInputSerializer(many=True, required=False)
    image = serializers.ImageField(required=True)

    class Meta:
        model = Event
        fields = (
            'id', 'name', 'description', 'image', 'venue',
            'start_time', 'end_time', 'sale_start_time', 'sale_end_time',
            'status', 'platform_fee_percent', 'ticket_types',
        )

    def to_internal_value(self, data):
        # Si viene de un formulario multipart, ticket_types es un string JSON
        if 'ticket_types' in data and isinstance(data['ticket_types'], str):
            try:
                data = data.copy() # Hacemos una copia mutable
                data['ticket_types'] = json.loads(data['ticket_types'])
            except json.JSONDecodeError:
                pass
        return super().to_internal_value(data)

    def validate_image(self, value):
        """Validación de tamaño y tipo de imagen."""
        # Tamaño máximo: 5 MB
        max_size = 5 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError(
                'La imagen no puede superar los 5 MB.'
            )

        # Tipos permitidos
        allowed_types = ['image/jpeg', 'image/png', 'image/webp']
        if hasattr(value, 'content_type') and value.content_type not in allowed_types:
            raise serializers.ValidationError(
                'Formato no soportado. Usá JPG, PNG o WEBP.'
            )

        return value

    def validate(self, attrs):
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

        # Validar nombres de ticket_types duplicados en el payload
        ticket_types = attrs.get('ticket_types', [])
        names = [tt.get('name', '').strip().lower() for tt in ticket_types if tt.get('name')]
        if len(names) != len(set(names)):
            raise serializers.ValidationError({
                'ticket_types': 'No puede haber dos tipos de entrada con el mismo nombre.'
            })

        return attrs

    def create(self, validated_data):
        ticket_types_data = validated_data.pop('ticket_types', [])
        event = Event.objects.create(**validated_data)

        for tt_data in ticket_types_data:
            tt_data.pop('id', None)  # Ignoramos ids en creación
            tt_data['quantity_available'] = tt_data.get('quantity_total', 0)
            TicketType.objects.create(event=event, **tt_data)

        return event

    def update(self, instance, validated_data):
        ticket_types_data = validated_data.pop('ticket_types', None)

        # Actualizar los campos del evento
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if ticket_types_data is None:
            return instance

        # Procesar ticket_types
        existing = {tt.id: tt for tt in instance.ticket_types.all()}
        seen_names = set()

        for tt_data in ticket_types_data:
            tt_id = tt_data.pop('id', None)
            name = tt_data.get('name', '').strip()

            if name.lower() in seen_names:
                raise serializers.ValidationError({
                    'ticket_types': f'El nombre "{name}" está repetido.'
                })
            seen_names.add(name.lower())

            # Validar que el id (si viene) pertenece a este evento
            if tt_id and tt_id not in existing:
                raise serializers.ValidationError({
                    'ticket_types': f'El ticket type con id={tt_id} no pertenece a este evento.'
                })

            if tt_id:
                # Actualizar existente
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
                # Crear nuevo
                tt_data['quantity_available'] = tt_data.get('quantity_total', 0)
                TicketType.objects.create(event=instance, **tt_data)

        return instance