from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import (
    UserSerializer, RegisterSerializer, RegisterProducerSerializer
)


class RegisterView(generics.CreateAPIView):
    """Registro de usuario comprador."""
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Devolvemos los tokens directamente para no forzar un login extra
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)


class RegisterProducerView(generics.CreateAPIView):
    """Registro de productor (puede crear eventos)."""
    serializer_class = RegisterProducerSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)


class MeView(APIView):
    """Devuelve el usuario autenticado."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

from rest_framework import generics
from .serializers import UserSerializer, RegisterSerializer, RegisterProducerSerializer, UpdateProfileSerializer, ChangePasswordSerializer

class UpdateProfileView(generics.UpdateAPIView):
    """
    PATCH /api/auth/me/
    Permite actualizar los datos del perfil del usuario autenticado.
    """
    serializer_class = UpdateProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(generics.GenericAPIView):
    """
    POST /api/auth/change-password/
    Permite cambiar la contraseña verificando la actual.
    """
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        return Response({'detail': 'Contraseña actualizada correctamente.'}, status=status.HTTP_200_OK)