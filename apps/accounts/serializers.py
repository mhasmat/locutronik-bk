from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name',
                  'is_producer', 'phone', 'document_number')
        read_only_fields = ('id', 'is_producer')  # is_producer se cambia solo desde admin


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password_confirm',
                  'first_name', 'last_name', 'phone')

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('password_confirm'):
            raise serializers.ValidationError({'password': 'Las contraseñas no coinciden.'})
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