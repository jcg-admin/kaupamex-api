"""Views — addons.authz_oauth (login federado OAuth2 + CRUD de proveedores).

Adaptación de Odoo ``auth_oauth/controllers/main.py`` (LGPL-3, 182 loc, leído
completo):

- ``list_providers`` (main.py:29-46) → acción pública ``public`` del ViewSet
  (los botones de login los pinta el SPA).
- ``/auth_oauth/signin`` (main.py:96-151) → ``oauth_signin`` (FBV): valida el
  access_token contra el proveedor, firma/da de alta al usuario y abre la
  sesión Django. Sus ``oauth_error`` 1/2/3 se sellan como ``codigo_error``.
- ``/auth_oauth/oea`` (main.py:153-182) → NO portado: login vía el proveedor
  de cuentas de la casa Odoo.com; sin análogo aquí.

``oauth_signin`` y ``public`` son superficie **pre-auth** (``auth='none'`` en
la referencia): ``AllowAny`` explícito y documentado — la invariante "nunca
``IsAuthenticated`` a secas, siempre capacidad" gobierna vistas de datos; un
login no puede exigir sesión. El CRUD admin sí va gateado
(``permissions.oauth``, sensible).
"""
import logging

from django.contrib.auth import authenticate, login
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from exceptions import AccessDenied, UserError

from addons.authz.permissions import CapabilityRequiredMixin
from addons.authz_oauth.models import OauthProvider
from addons.authz_oauth.models.res_users import auth_oauth
from addons.authz_oauth.serializers import (
    OauthProviderPublicSerializer,
    OauthProviderSerializer,
    OauthSigninSerializer,
)

_logger = logging.getLogger(__name__)


@extend_schema(tags=['authz-oauth'])
class OauthProviderViewSet(CapabilityRequiredMixin, ModelViewSet):
    """CRUD admin de proveedores (≙ views/auth_oauth_views.xml +
    security/ir.model.access.csv de la referencia)."""

    required_capability = 'permissions.oauth'
    queryset = OauthProvider.objects.all()
    serializer_class = OauthProviderSerializer

    @extend_schema(
        summary='Proveedores habilitados para la página de login',
        responses={200: OauthProviderPublicSerializer(many=True)},
        auth=[],
    )
    @action(detail=False, methods=['get'],
            permission_classes=[AllowAny], url_path='public')
    def public(self, request):
        """≙ ``list_providers`` (main.py:29-46). Público a propósito: es lo
        que la referencia sirve en su página de login anónima."""
        providers = OauthProvider.objects.filter(enabled=True)
        serializer = OauthProviderPublicSerializer(
            providers, many=True,
            context={'redirect_uri': request.build_absolute_uri(
                '/api/v2/authz/oauth/signin/')},
        )
        return Response(serializer.data)


@extend_schema(
    tags=['authz-oauth'],
    summary='Login federado: valida el access_token y abre sesión',
    request=OauthSigninSerializer,
    responses={
        200: OpenApiResponse(description='Sesión abierta; login del usuario'),
        403: OpenApiResponse(
            description='OAUTH_ACCESS_DENIED (token inválido o alta no '
                        'permitida) — el oauth_error=3 de la referencia'),
        502: OpenApiResponse(
            description='OAUTH_PROVIDER_ERROR (el proveedor respondió '
                        'error) — el oauth_error=2 de la referencia'),
    },
    auth=[],
)
@api_view(['POST'])
@permission_classes([AllowAny])
def oauth_signin(request):
    """≙ ``OAuthController.signin`` (main.py:96-151)."""
    serializer = OauthSigninSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    provider_id = serializer.validated_data['provider']

    if not OauthProvider.objects.filter(
            pk=provider_id, enabled=True).exists():
        return Response(
            {'codigo_error': 'OAUTH_ACCESS_DENIED',
             'detail': 'Proveedor inexistente o deshabilitado.'},
            status=status.HTTP_403_FORBIDDEN)

    params = {'access_token': serializer.validated_data['access_token']}
    try:
        login_name, access_token = auth_oauth(provider_id, params)
    except AccessDenied:
        # ≙ oauth_error=3: credenciales no válidas / alta no permitida.
        _logger.info('OAuth2: access denied for provider %s', provider_id)
        return Response(
            {'codigo_error': 'OAUTH_ACCESS_DENIED',
             'detail': 'Acceso denegado por el proveedor o alta no '
                       'permitida.'},
            status=status.HTTP_403_FORBIDDEN)
    except Exception:  # ≙ oauth_error=2 (main.py:144-147, mismo catch ancho)
        _logger.exception('Exception during OAuth signin')
        return Response(
            {'codigo_error': 'OAUTH_PROVIDER_ERROR',
             'detail': 'El proveedor OAuth respondió un error.'},
            status=status.HTTP_502_BAD_GATEWAY)

    user = authenticate(request, oauth_token=access_token)
    if user is None:
        return Response(
            {'codigo_error': 'OAUTH_ACCESS_DENIED',
             'detail': 'No se pudo autenticar al usuario federado.'},
            status=status.HTTP_403_FORBIDDEN)
    login(request, user)
    return Response({'login': login_name})
