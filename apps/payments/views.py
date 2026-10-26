from rest_framework import status
from rest_framework import permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from apps.orders.models import Order
from apps.orders.services import confirm_order_payment
from .services import create_checkout_preference, get_payment_info

from django.contrib.auth import get_user_model
from .services import get_mp_oauth_url, exchange_mp_code_for_token

from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.shortcuts import redirect
from django.conf import settings

class CreateCheckoutView(APIView):
    """
    POST /api/orders/<order_id>/checkout/
    Crea una preferencia de pago en MP y devuelve la URL de checkout.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            return Response(
                {'detail': 'Orden no encontrada.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if order.status != 'pending':
            return Response(
                {'detail': f'La orden no está pendiente (status actual: {order.status}).'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from django.utils import timezone
        if order.expires_at < timezone.now():
            return Response(
                {'detail': 'La orden ya expiró.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        preference_data, error = create_checkout_preference(order)
        if error:
            return Response(
                {'detail': error},
                status=status.HTTP_502_BAD_GATEWAY
            )

        # Guardamos el ID de la preferencia para referencia
        order.payment_provider = 'mercadopago'
        order.payment_reference = preference_data.get('id', '')
        order.save(update_fields=['payment_provider', 'payment_reference'])

        # Devolvemos los datos al frontend
        # En producción usar 'init_point'. En sandbox, 'sandbox_init_point'.
        init_point = preference_data.get('sandbox_init_point') or preference_data.get('init_point')

        return Response({
            'order_id': str(order.id),
            'preference_id': preference_data.get('id'),
            'init_point': init_point,
        }, status=status.HTTP_200_OK)


class MercadoPagoWebhookView(APIView):
    """
    POST /api/payments/webhook/
    Recibe notificaciones de MP. Cuando el pago se aprueba, confirma la orden.

    MP envía el payment_id de dos formas:
      - Legacy:  ?topic=payment&id=123
      - Moderna: ?type=payment&data.id=123
    Y a veces también en el body como JSON.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        # --- Detectar el tipo de notificación ---
        topic = (
            request.query_params.get('type')
            or request.query_params.get('topic')
            or (request.data or {}).get('type')
            or (request.data or {}).get('topic')
        )

        # --- Detectar el payment_id (soporta ambos formatos) ---
        payment_id = (
            request.query_params.get('data.id')
            or request.query_params.get('id')                       # ← legacy
            or ((request.data or {}).get('data') or {}).get('id')
            or (request.data or {}).get('id')
        )

        # --- Log para debug ---
        print(f"[MP WEBHOOK] topic={topic} payment_id={payment_id} "
              f"query={dict(request.query_params)}")

        # merchant_order no es un pago: lo ignoramos (MP manda muchos)
        if topic != 'payment' or not payment_id:
            return Response({'detail': 'Ignorado.'}, status=200)

        # --- Consultar el pago real a MP (nunca confiar en el payload crudo) ---
        payment_data, error = get_payment_info(payment_id)
        if error:
            print(f"[MP WEBHOOK] Error consultando pago {payment_id}: {error}")
            return Response({'detail': error}, status=400)

        external_reference = payment_data.get('external_reference')
        mp_status = payment_data.get('status')

        if not external_reference:
            return Response({'detail': 'Sin external_reference.'}, status=400)

        try:
            order = Order.objects.get(id=external_reference)
        except Order.DoesNotExist:
            return Response({'detail': 'Orden no encontrada.'}, status=404)

        print(f"[MP WEBHOOK] Orden {order.id} | status_mp={mp_status}")

        # --- Solo procesamos si el pago fue aprobado ---
        if mp_status == 'approved':
            confirmed = confirm_order_payment(
                order=order,
                payment_provider='mercadopago',
                payment_reference=str(payment_id),
            )
            if confirmed:
                print(f"[MP WEBHOOK] ✓ Orden {order.id} confirmada, tickets generados.")
            else:
                print(f"[MP WEBHOOK] Orden {order.id} ya estaba confirmada o no es pending.")

        # MP espera siempre 200, si devolvemos error reintenta
        return Response({'detail': 'OK'}, status=200)

class MPOAuthUrlView(APIView):
    """GET /api/payments/mp/oauth/url/"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        url = get_mp_oauth_url(request.user.id)
        return Response({'url': url})


class MPOAuthCallbackView(APIView):
    """GET /api/payments/mp/oauth/callback/ (Llamado por Mercado Pago)"""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        code = request.query_params.get('code')
        user_id = request.query_params.get('state')
        
        if not code or not user_id:
            return redirect(f"{settings.FRONTEND_URL}/productor?error=oauth_failed")
            
        token_data = exchange_mp_code_for_token(code)
        if token_data and 'user_id' in token_data:
            User = get_user_model()
            try:
                user = User.objects.get(id=user_id)
                user.mp_user_id = str(token_data['user_id'])
                # Opcional: guardar el access_token del productor si lo necesitamos luego
                user.save(update_fields=['mp_user_id'])
                
                # Redirigimos al productor con un mensaje de éxito
                return redirect(f"{settings.FRONTEND_URL}/productor?linked=true")
            except User.DoesNotExist:
                pass
                
        return redirect(f"{settings.FRONTEND_URL}/productor?error=user_not_found")


def checkout_result_view(request, status):
    """
    Recibe el resultado de MP y redirige al frontend.
    El frontend vive en FRONTEND_URL.
    """
    order_id = request.GET.get('order_id') or request.GET.get('external_reference')
    payment_id = request.GET.get('payment_id')

    frontend_url = settings.FRONTEND_URL.rstrip('/')
    url = f"{frontend_url}/checkout/{status}/"
    params = []
    if order_id:
        params.append(f"order_id={order_id}")
    if payment_id:
        params.append(f"payment_id={payment_id}")

    if params:
        url += "?" + "&".join(params)

    return redirect(url)    