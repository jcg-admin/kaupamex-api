"""Views — addons.authz_passkey.

Dos superficies:

- **Gestión de MIS passkeys** (listar/registrar/renombrar/borrar) —
  ``account.security``; el ``@check_identity`` de la referencia sobre
  crear/borrar se porta como ``_check_identity`` explícito (la capacidad NO
  es sensible en el catálogo, así que el gate data-driven DEC-12 no cubre
  este caso solo). El borrado sólo de las propias, con el mismo log de
  auditoría que ``unlink``/``action_delete_passkey``.
- **Login con passkey** (pre-auth, ``AllowAny`` — el ``web_totp``/login de
  la referencia es ``auth='public'``): GET de opciones (challenge en
  sesión) + POST con la respuesta WebAuthn → sesión Django via
  ``PasskeyBackend``.
"""
import logging

from django.contrib.auth import authenticate, login
from drf_spectacular.utils import OpenApiResponse, extend_schema
from webauthn.helpers import bytes_to_base64url
from rest_framework import status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.mixins import DestroyModelMixin, ListModelMixin, UpdateModelMixin
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from addons.authz.exceptions import ReauthRequired
from addons.authz.permissions import CapabilityRequiredMixin
from addons.authz_reauth.reauth import (
    _reauth_ttl,
    _session_key,
    has_active_reauth_session,
)
from addons.authz_passkey.models import PasskeyKey
from addons.authz_passkey.controllers.serializers import (
    PasskeyKeySerializer,
    PasskeyRegisterSerializer,
    PasskeySigninSerializer,
)

_logger = logging.getLogger(__name__)


def _check_identity(request):
    """Porta el ``@check_identity`` de la referencia (crear/borrar passkey
    exige re-autenticarse). ``account.security`` NO es sensible en el
    catálogo — gobierna también lecturas del menú de seguridad — así que el
    gate data-driven de DEC-12 no dispara aquí solo; este check explícito
    es la traducción del decorador, con el mismo contrato 403
    REAUTH_REQUIRED del resto del árbol."""
    if not has_active_reauth_session(request.user, _session_key(request)):
        raise ReauthRequired(window_seconds=_reauth_ttl())


@extend_schema(tags=['authz-passkey'])
class PasskeyViewSet(CapabilityRequiredMixin, ListModelMixin,
                     UpdateModelMixin, DestroyModelMixin, GenericViewSet):
    """Passkeys del usuario autenticado. Sin ``create`` genérico: el alta es
    el par ``registration-options`` + ``register`` (flujo WebAuthn), y sin
    ``retrieve`` (la lista basta — no hay detalle que no esté en ella)."""

    required_capability = 'account.security'
    serializer_class = PasskeyKeySerializer
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        # Sólo las propias — ≙ action_delete_passkey (create_uid == user).
        return PasskeyKey.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        # ≙ @check_identity de action_delete_passkey + el log de unlink
        # (auth_passkey_key.py:42-50, 126-143).
        _check_identity(self.request)
        _logger.info(
            'Passkey (#%d) deleted by %s (#%d) from %s',
            instance.id, self.request.user.login, self.request.user.id,
            self.request.META.get('REMOTE_ADDR', 'n/a'))
        instance.delete()

    @extend_schema(
        summary='Opciones de registro WebAuthn (challenge en sesión)',
        request=None,
        responses={200: OpenApiResponse(
            description='PublicKeyCredentialCreationOptions')},
    )
    @action(detail=False, methods=['post'], url_path='registration-options')
    def registration_options(self, request):
        """≙ ``_start_registration`` via ``action_create_passkey``
        (``@check_identity``)."""
        _check_identity(request)
        return Response(PasskeyKey.start_registration(request, request.user))

    @extend_schema(
        summary='Registrar la passkey (respuesta del navegador)',
        request=PasskeyRegisterSerializer,
        responses={
            201: PasskeyKeySerializer,
            403: OpenApiResponse(description='PASSKEY_CHALLENGE_INVALID'),
        },
    )
    @action(detail=False, methods=['post'])
    def register(self, request):
        """≙ ``auth.passkey.key.create.make_key`` (auth_passkey_key.py:
        160-194)."""
        _check_identity(request)
        serializer = PasskeyRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            verification = PasskeyKey.verify_registration_options(
                request, serializer.validated_data['registration'])
        except Exception as exc:  # AccessDenied (challenge) o error webauthn
            _logger.info('Passkey registration failed for %r: %s',
                         request.user.login, exc)
            return Response(
                {'codigo_error': 'PASSKEY_CHALLENGE_INVALID',
                 'detail': 'La verificación del registro falló.'},
                status=status.HTTP_403_FORBIDDEN)
        passkey = PasskeyKey.objects.create(
            user=request.user,
            name=serializer.validated_data['name'],
            credential_identifier=bytes_to_base64url(
                verification['credential_id']),
            public_key=bytes_to_base64url(
                verification['credential_public_key']),
        )
        _logger.info(
            'Passkey (#%d) created by %s (#%d) from %s',
            passkey.id, request.user.login, request.user.id,
            request.META.get('REMOTE_ADDR', 'n/a'))
        return Response(PasskeyKeySerializer(passkey).data,
                        status=status.HTTP_201_CREATED)


@extend_schema(
    tags=['authz-passkey'],
    summary='Opciones de autenticación WebAuthn (challenge en sesión)',
    request=None,
    responses={200: OpenApiResponse(
        description='PublicKeyCredentialRequestOptions')},
    auth=[],
)
@api_view(['POST'])
@permission_classes([AllowAny])
def auth_options(request):
    """≙ ``_start_auth`` — pre-auth."""
    return Response(PasskeyKey.start_auth(request))


@extend_schema(
    tags=['authz-passkey'],
    summary='Login con passkey: verifica la respuesta y abre sesión',
    request=PasskeySigninSerializer,
    responses={
        200: OpenApiResponse(description='Sesión abierta; login del usuario'),
        403: OpenApiResponse(description='PASSKEY_ACCESS_DENIED'),
    },
    auth=[],
)
@api_view(['POST'])
@permission_classes([AllowAny])
def passkey_signin(request):
    """≙ ``_login`` + ``_check_credentials`` tipo webauthn — pre-auth."""
    serializer = PasskeySigninSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = authenticate(
        request,
        webauthn_response=serializer.validated_data['webauthn_response'])
    if user is None:
        return Response(
            {'codigo_error': 'PASSKEY_ACCESS_DENIED',
             'detail': 'Unknown passkey o verificación fallida.'},
            status=status.HTTP_403_FORBIDDEN)
    login(request, user)
    return Response({'login': user.login})
