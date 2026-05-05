"""
Views de Users — UC-AUTH-01
"""
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from .serializers import RegisterSerializer


class RegisterView(APIView):
    """POST /api/v1/auth/register/ — UC-AUTH-01."""
    permission_classes = [AllowAny]
    throttle_scope = 'register'

    @extend_schema(
        summary='Registrar cuenta de comprador',
        description=(
            'Crea una cuenta nueva con is_active=False hasta verificar el email '
            '(UC-AUTH-01). El email se normaliza a minúsculas. Los mensajes de '
            'unicidad son intencionalmente ambiguos para prevenir enumeración de usuarios.'
        ),
        request=RegisterSerializer,
        responses={
            201: OpenApiResponse(description='Cuenta creada. Se envía email de verificación.'),
            400: OpenApiResponse(description='Error de validación (formato o unicidad).'),
        },
        tags=['auth'],
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {
                    'message': 'Cuenta creada. Revisa tu email para activarla.',
                    'user_id': user.pk,
                },
                status=201,
            )
        return Response(serializer.errors, status=400)
