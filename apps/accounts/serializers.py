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

class UpdateProfileSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(required=False)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone', 'document_number')

    def validate_email(self, value):
        if not value:
            return value
        # Validar que el nuevo email no esté en uso por otro usuario (ignorando mayúsculas)
        if User.objects.filter(email__iexact=value).exclude(id=self.instance.id).exists():
            raise serializers.ValidationError("Este email ya está registrado por otro usuario.")
        return value

    def validate_phone(self, value):
        if value:
            normalized = normalize_argentine_phone(value)
            if not normalized:
                raise serializers.ValidationError('El teléfono no es válido.')
            return normalized
        return value


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)

    def validate_current_password(self, value):
        # Verifica que la contraseña actual sea correcta
        if not self.context['request'].user.check_password(value):
            raise serializers.ValidationError("La contraseña actual es incorrecta.")
        return value

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


class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name', 
            'is_producer', 'is_pos_operator', 'is_staff', 'phone', 'document_number', 'date_joined'
        )
        read_only_fields = ('id', 'username', 'date_joined')