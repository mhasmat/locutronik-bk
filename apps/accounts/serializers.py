from django.contrib.auth import get_user_model
from rest_framework import serializers
from .utils import normalize_argentine_phone

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    phone_display = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name',
                  'is_producer', 'phone', 'phone_display', 'document_number')
        read_only_fields = ('id', 'is_producer')  # is_producer se cambia solo desde admin

    def get_phone_display(self, obj):
        from .utils import format_phone_display
        return format_phone_display(obj.phone) if obj.phone else ''

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    phone = serializers.CharField(required=True, allow_blank=False)

    class Meta:
        model = User
        fields = (
            'username', 'email', 'password', 'password_confirm',
            'first_name', 'last_name', 'phone',
        )

    def validate_phone(self, value):
        normalized = normalize_argentine_phone(value)
        if not normalized:
            raise serializers.ValidationError(
                'El teléfono no es válido. Usá formato argentino, ej: +54 9 11 2345-6789.'
            )
        return normalized

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('password_confirm'):
            raise serializers.ValidationError(
                {'password': 'Las contraseñas no coinciden.'}
            )
        return attrs

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class RegisterProducerSerializer(RegisterSerializer):
    """Registro específico para productores: activa is_producer automáticamente."""

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        user.is_producer = True
        user.save(update_fields=['is_producer'])
        return user