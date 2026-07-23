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
from addons.authz_menu.models import MenuItem
from addons.authz_reauth.models import ReauthSession
from addons.authz.serializers import MenuItemNodeSerializer
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

    Un item es visible si (a) no requiere capacidad, o (b) el usuario tiene la
    capacidad (superadmin ve todo). Una sección (nivel 0) se descarta si no le
    queda ningún hijo visible — así un usuario de solo-soporte ve únicamente su
    sección.

    ``?audience=admin`` (default) sirve el menú del panel; ``?audience=account``
    sirve el menú de cuenta del comprador (DEC-AUTHZ-BUYER). Ambos son
    registro-dirigidos: agregar una entrada es sembrar una fila, sin tocar el
    UI. Filtrar por audiencia evita que el admin vea ítems de cuenta mezclados
    (y viceversa).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        caps = resolve_capabilities(request.user)
        superadmin = is_superadmin(request.user)

        audience = request.query_params.get('audience', MenuItem.AUDIENCE_ADMIN)
        valid_audiences = {c[0] for c in MenuItem.AUDIENCE_CHOICES}
        if audience not in valid_audiences:
            audience = MenuItem.AUDIENCE_ADMIN

        # Cargar todo el árbol activo de la audiencia en una query; armar el
        # índice por parent.
        items = list(
            MenuItem.objects.filter(is_active=True, audience=audience)
            .select_related('required_capability')
            .order_by('parent_id', 'order', 'id')
        )
        children_by_parent = {}
        for item in items:
            children_by_parent.setdefault(item.parent_id, []).append(item)

        def visible(item):
            cap = item.required_capability.code if item.required_capability_id else None
            if superadmin or cap is None:
                return True
            # DEC-11: un sustantivo (sin punto) gatea el menú por LECTURA
            # (``noun.view``); una acción nombrada (con punto) por membresía.
            needed = cap if '.' in cap else f'{cap}.view'
            return needed in caps

        def build(parent_id):
            out = []
            for item in children_by_parent.get(parent_id, []):
                kids = build(item.id)
                # Item hoja: visible por su propia capacidad.
                # Sección (sin route): visible solo si tiene hijos visibles.
                is_section = not item.route
                if is_section:
                    if not kids:
                        continue
                elif not visible(item):
                    continue
                item._visible_children = kids
                out.append(item)
            return out

        tree = build(None)
        return Response(MenuItemNodeSerializer(tree, many=True).data)


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
