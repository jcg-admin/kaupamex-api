"""Vistas — apps.authz.

Endpoints del usuario autenticado (nunca ``{usuario_id}`` — evita IDOR):

- ``GET /api/v2/authz/me/capabilities/`` — el set de capacidades resueltas.
- ``GET /api/v2/authz/me/menu/`` — el árbol de menú admin podado por esas
  capacidades (DEC-08/09). El menú es proyección UX; el candado real sigue
  siendo ``HasCapability`` en cada vista.
"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authz.models import MenuItem
from apps.authz.serializers import MenuItemNodeSerializer
from apps.authz.services import is_superadmin, resolve_capabilities


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
