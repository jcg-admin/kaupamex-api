"""
Views — SiteSettings (UC-CFG-03)

GET  /api/v1/config/settings/   — retorna la configuracion actual (admin only)
PATCH /api/v1/config/settings/  — actualiza campos (admin only)
"""
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from .models import SiteSettings
from .serializers import SiteSettingsSerializer


class SiteSettingsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Obtener configuración global',
        description=(
            'Retorna el singleton SiteSettings con los parámetros globales del sistema: '
            'tasa de IVA, moneda, timeout de órdenes, días de devolución y umbral de envío gratis. '
            'Solo accesible para administradores.'
        ),
        responses={
            200: SiteSettingsSerializer,
            401: OpenApiResponse(description='No autenticado.'),
            403: OpenApiResponse(description='El usuario no es administrador.'),
        },
        tags=['config'],
    )
    def get(self, request):
        settings = SiteSettings.get_current()
        serializer = SiteSettingsSerializer(settings)
        return Response(serializer.data)

    @extend_schema(
        summary='Actualizar configuración global',
        description=(
            'Actualiza uno o más parámetros del singleton SiteSettings. '
            'Los cambios tienen efecto inmediato para nuevas solicitudes. '
            'Las órdenes ya creadas conservan los valores del momento en que se crearon.'
        ),
        request=SiteSettingsSerializer,
        responses={
            200: SiteSettingsSerializer,
            400: OpenApiResponse(description='Error de validación (rango o formato inválido).'),
            401: OpenApiResponse(description='No autenticado.'),
            403: OpenApiResponse(description='El usuario no es administrador.'),
        },
        tags=['config'],
    )
    def patch(self, request):
        settings = SiteSettings.get_current()
        serializer = SiteSettingsSerializer(settings, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)
