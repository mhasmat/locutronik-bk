from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
import secrets
import string

from .serializers import (
    AdminUserSerializer, ChangePasswordSerializer, User, UserSerializer, RegisterSerializer, RegisterProducerSerializer
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


from rest_framework import generics
from .serializers import UserSerializer, UpdateProfileSerializer

class ProfileView(generics.RetrieveUpdateAPIView):
    """
    GET /api/auth/me/ -> Ver perfil
    PATCH /api/auth/me/ -> Actualizar perfil
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return UserSerializer
        return UpdateProfileSerializer


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


class AdminUserListView(generics.ListAPIView):
    """GET /api/auth/admin/users/ -> Listar todos los usuarios"""
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = AdminUserSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get('search')
        if search:
            from django.db.models import Q
            qs = qs.filter(Q(username__icontains=search) | Q(email__icontains=search))
        return qs

class AdminUserUpdateRoleView(generics.UpdateAPIView):
    """PATCH /api/auth/admin/users/<id>/ -> Cambiar roles (hacerlo productor o POS)"""
    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [permissions.IsAdminUser]

class AdminResetPasswordView(generics.GenericAPIView):
    """POST /api/auth/admin/users/<id>/reset-password/ -> Blanquear contraseña"""
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({'detail': 'Usuario no encontrado.'}, status=404)
        
        # Generamos una contraseña temporal aleatoria
        alphabet = string.ascii_letters + string.digits
        new_password = ''.join(secrets.choice(alphabet) for i in range(10))
        
        user.set_password(new_password)
        user.save()
        
        return Response({
            'detail': 'Contraseña blanqueada correctamente.',
            'temporary_password': new_password # El admin debe copiarla y pasársela al usuario
        }, status=status.HTTP_200_OK)