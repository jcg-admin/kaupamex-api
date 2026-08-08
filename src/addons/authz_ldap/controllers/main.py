"""Views — addons.authz_ldap (CRUD de configuraciones LDAP).

Superficie de configuración del addon: lo que en la referencia hacen
``views/ldap_installer_views.xml`` (editor de ``res.company.ldap``) y el
botón *Test connection* (``test_ldap_connection``). Recurso CRUD → ViewSet +
router (backend-drf). Gate: ``permissions.ldap`` (sensible) en TODAS las
acciones — la referencia reserva el modelo entero a ``base.group_system``
(``ir.model.access.csv``: una sola fila, system, CRUD completo), así que no
hay split lectura/escritura que preservar.
"""
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from addons.authz.permissions import CapabilityRequiredMixin
from addons.authz_ldap.models import CompanyLdap
from addons.authz_ldap.controllers.serializers import CompanyLdapSerializer


@extend_schema(tags=['authz-ldap'])
class CompanyLdapViewSet(CapabilityRequiredMixin, ModelViewSet):

    required_capability = 'permissions.ldap'
    queryset = CompanyLdap.objects.select_related('company').order_by(
        'sequence')
    serializer_class = CompanyLdapSerializer

    @extend_schema(
        summary='Probar la conexión LDAP de esta configuración',
        request=None,
        responses={
            200: OpenApiResponse(description='ok=True, conexión exitosa'),
            502: OpenApiResponse(
                description='ok=False + codigo_error '
                            '(LDAP_SERVER_DOWN | LDAP_INVALID_CREDENTIALS | '
                            'LDAP_TIMEOUT | LDAP_ERROR | LDAP_UNAVAILABLE)'),
        },
    )
    @action(detail=True, methods=['post'], url_path='test-connection')
    def test_connection(self, request, pk=None):
        """≙ ``test_ldap_connection`` (res_company_ldap.py:266-350). El 502
        distingue "el upstream LDAP no responde/acepta" del 400 de payload."""
        result = self.get_object().test_ldap_connection()
        http_status = (status.HTTP_200_OK if result.get('ok')
                       else status.HTTP_502_BAD_GATEWAY)
        return Response(result, status=http_status)
