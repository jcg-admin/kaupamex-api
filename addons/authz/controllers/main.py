"""Vistas — addons.authz.

Endpoints del usuario autenticado (nunca ``{usuario_id}`` — evita IDOR):

- ``GET /api/v2/authz/me/capabilities/`` — el set de capacidades resueltas.
- ``GET /api/v2/authz/me/menu/`` — el árbol de menú admin podado por esas
  capacidades (DEC-08/09). El menú es proyección UX; el candado real sigue
  siendo ``HasCapability`` en cada vista.
"""
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from addons.authz_audit.models import AuthzEvent
from addons.base.models import IrUiMenu
from addons.website.models import WebsiteMenu
from addons.authz_reauth.models import ReauthSession
from addons.authz.controllers.serializers import MenuNodeSerializer
from addons.authz.services import (
    REAUTH_CAP_CODE,
    _client_ip,
    _reauth_ttl,
    _session_key,
    audit_authz_event,
    close_reauth_session,
    is_superadmin,
    open_reauth_session,
    resolve_capabilities,
)


class MyCapabilitiesView(APIView):
    """El set de capacidades del usuario autenticado (para route-guards del SPA)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        caps = resolve_capabilities(request.user)
        return Response({
            'is_superadmin': is_superadmin(request.user),
            'capabilities': sorted(caps),
        })


class MyMenuView(APIView):
    """Árbol de menú podado por las capacidades del usuario.

    Thin controller, como en la referencia: ``web/controllers/home.py:85`` sólo
    llama ``request.env["ir.ui.menu"].load_web_menus(...)``. Todo el mecanismo
    —los dos filtros, la regla de ancestros, el caché por perfil y el
    ensamblado— vive en el manager del modelo, que es donde la referencia lo
    pone.

    ``?audience=`` elige **el modelo**, no un campo: ``admin`` (default) sirve
    ``base.IrUiMenu`` —el backoffice, ``ir.ui.menu``— y ``account`` sirve
    ``website.WebsiteMenu`` —la cara pública, ``website.menu``
    (DEC-AUTHZ-BUYER)—. La referencia mantiene esos dos modelos separados; el
    parámetro se conserva porque es el contrato que ya consume el SPA.

    Ambos son registro-dirigidos: agregar una entrada es sembrar una fila, sin
    tocar el UI.
    """

    permission_classes = [IsAuthenticated]

    #: Exenta del candado por tiempo — ≙ ``auth_timeout/controllers/web_home.py``,
    #: que re-declara ``@http.route(check_identity=False)`` sobre
    #: ``web_load_menus``. El menú es lo que el cliente pide para **dibujar la
    #: pantalla en la que se confirma la identidad**: someterlo al candado deja
    #: al usuario sin superficie donde confirmar.
    check_identity = False

    MENU_MODEL_BY_AUDIENCE = {
        'admin': IrUiMenu,
        'account': WebsiteMenu,
    }

    def get(self, request):
        audience = request.query_params.get('audience', 'admin')
        model = self.MENU_MODEL_BY_AUDIENCE.get(audience, IrUiMenu)

        tree = model.objects.load_menus_tree(
            request.user,
            capabilities=resolve_capabilities(request.user),
            superadmin=is_superadmin(request.user),
        )
        response = Response(MenuNodeSerializer(tree, many=True).data)
        # ``home.py:97`` de la referencia sella la respuesta de ``load_menus``
        # con ``Cache-Control: no-store``. Es seguridad, no rendimiento: el menú
        # depende del perfil, así que un proxy que lo cachee se lo serviría a
        # otro usuario con otras capacidades. El caché vive del lado del
        # servidor y por conjunto de capacidades (``_visible_menu_ids``).
        response['Cache-Control'] = 'no-store'
        return response


class ReauthSessionView(APIView):
    """Sesión reautenticada — DEC-12 shape A.

    Confirma la identidad del usuario para operar acciones **sensibles** durante
    una ventana con TTL. **NO es una elevación de privilegios** (deliberadamente
    no se llama "sudo"): no otorga poderes nuevos, sólo ratifica intención sobre
    lo que el Role del usuario ya autoriza.

    - ``GET`` — estado de la reautenticación de la sesión actual (para el contador
      del SPA): ``{active, expires_at, expires_in}``.
    - ``POST`` — abre/renueva la ventana re-autenticando con **password**.
      Éxito → 200 ``{expires_at, expires_in}``; password inválido → 400
      ``{codigo_error: REAUTH_INVALID_PASSWORD}``.
    - ``DELETE`` — cierra la ventana (204).

    Re-auth de **password** en v1 (la política MFA ya decidida —
    :ref:`analisis-mfa-totp-nativo`— añade el step-up TOTP para admins **cuando
    aterrice la iniciativa MFA**; ``IdentityUser`` aún no tiene device TOTP ni
    ``require_2fa``, así que aquí el factor es password). La apertura/cierre se
    auditan en ``AuthzEvent`` (DEC-07). Este endpoint NO se gatea con
    ``HasCapability`` (sólo ``IsAuthenticated``): es la puerta de la propia
    re-autenticación.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        obj = (
            ReauthSession.objects
            .filter(user=request.user, session_key=_session_key(request),
                    expires_at__gt=timezone.now())
            .first()
        )
        if obj is None:
            return Response({'active': False})
        remaining = int((obj.expires_at - timezone.now()).total_seconds())
        return Response({
            'active': True,
            'expires_at': obj.expires_at.isoformat(),
            'expires_in': max(remaining, 0),
        })

    def post(self, request):
        password = (request.data or {}).get('password') or ''
        if not password or not request.user.check_password(password):
            audit_authz_event(
                request, AuthzEvent.ACTION_DENY, REAUTH_CAP_CODE,
                {'reason': 'invalid_password'},
            )
            return Response(
                {'detail': 'Contraseña incorrecta.',
                 'codigo_error': 'REAUTH_INVALID_PASSWORD'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        obj = open_reauth_session(
            request.user, _session_key(request), _client_ip(request),
        )
        audit_authz_event(
            request, AuthzEvent.ACTION_SENSITIVE_USE, REAUTH_CAP_CODE,
            {'event': 'reauth_open'},
        )
        return Response({
            'expires_at': obj.expires_at.isoformat(),
            'expires_in': _reauth_ttl(),
        })

    def delete(self, request):
        close_reauth_session(request.user, _session_key(request))
        audit_authz_event(
            request, AuthzEvent.ACTION_SENSITIVE_USE, REAUTH_CAP_CODE,
            {'event': 'reauth_close'},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
