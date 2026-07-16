"""Clases de permiso DRF — apps.platform.authz.

Reemplazan ``rest_framework.permissions.IsAdminUser`` (que dependía de
``user.is_staff``, campo que ya no existe en ``IdentityUser`` U-D). El acceso
admin se gobierna por **capacidad** (``HasCapability``); la propiedad del
comprador por **objeto** (``IsOwnerOrAdmin``).

Diseño ratificado en :ref:`analisis-enforcement-hascapability-isowner`.
"""
from rest_framework.permissions import (
    SAFE_METHODS,
    BasePermission,
    IsAuthenticated,
)

from apps.platform.authz.services import assert_session_fresh, has_capability


class HasCapability(BasePermission):
    """Autoriza si el usuario posee la capacidad requerida por la vista.

    La vista declara su capacidad de una de dos formas:

    - ``permission_map = {'list': 'catalogue.view', 'create': 'catalogue.create'}``
      para ``ViewSet``/``@action`` (se resuelve por ``view.action``); o
    - ``required_capability = 'domain.verb'`` para vistas de una sola acción.

    **Fail-closed:** si la vista no declara ninguna, deniega (403) — una
    capacidad olvidada nunca abre acceso.
    """

    message = 'No tienes la capacidad requerida para esta acción.'

    def _needed(self, view):
        """Capacidad requerida **declarada por la vista** (``permission_map`` por
        acción, o ``required_capability`` de vista de una sola acción).

        Las variantes que llevan la capacidad en la **instancia de permiso**
        (``RequireCapability`` / ``@require_capability``) NO pasan por aquí:
        sobrescriben ``_needed`` para devolver su propio código (ver el factory).
        Así cada mecanismo tiene un único origen, sin mezclar vista y self.
        """
        pmap = getattr(view, 'permission_map', None)
        if pmap:
            action = getattr(view, 'action', None)
            if action in pmap:
                return pmap[action]
        return getattr(view, 'required_capability', None)

    def has_permission(self, request, view):
        needed = self._needed(view)
        if not has_capability(request.user, needed):
            return False
        # DEC-12: acciones sensibles mutantes exigen una sesión elevada fresca.
        # ``assert_session_fresh`` lanza ReauthRequired (403 REAUTH_REQUIRED) si
        # falta; para lo no-sensible es un no-op. Superadmin NO exento.
        assert_session_fresh(request, needed, request.method not in SAFE_METHODS)
        return True


def RequireCapability(code):
    """Factory: declara la capacidad inline en ``permission_classes``.

    Uso: ``permission_classes = [IsAuthenticated, RequireCapability('audit.view')]``

    La capacidad vive en la **instancia de permiso**, no en la vista, así que la
    subclase **sobrescribe** ``_needed`` para devolver ``code`` directamente (el
    ``_needed`` base sólo mira la vista). Origen único, sin mezclar vista y self.
    """
    return type(
        f'HasCap_{code.replace(".", "_")}',
        (HasCapability,),
        {'_needed': lambda self, view: code},
    )


def _obj_belongs_to(obj, user):
    owner_id = getattr(obj, 'user_id', None)
    return owner_id is not None and owner_id == getattr(user, 'pk', None)


class IsOwnerOrAdmin(BasePermission):
    """Objeto propio del comprador, o admin con capacidad sobre el dominio.

    Segunda línea de defensa sobre el ``filter(user=request.user)`` del queryset
    (cierra H-API-PERM-05). La vista declara ``admin_capability`` para el bypass
    admin. NO aplica a POS (una venta no "pertenece" al cajero — usa
    ``HasCapability`` con ``pos.*``).
    """

    def has_object_permission(self, request, view, obj):
        if _obj_belongs_to(obj, request.user):
            return True
        return has_capability(request.user, getattr(view, 'admin_capability', None))


# ─── Azúcar declarativa sobre HasCapability (no lo reemplaza) ─────────────────
# El mapeo pretix ↔ catálogo DB (analisis-mapeo-registro-permisos-pretix-vs-
# catalogo-db) recomienda estas ergonomías: el permission class es el motor; la
# azúcar sólo evita repetir ``permission_classes`` en cada vista. El chequeo real
# —capacidad DEC-11 + gate de re-auth DEC-12— lo sigue haciendo ``HasCapability``.


class CapabilityRequiredMixin:
    """Mixin declarativo: la vista sólo declara ``required_capability`` (o
    ``permission_map``) y hereda ``permission_classes = [IsAuthenticated,
    HasCapability]``.

    Reemplaza el boilerplate repetido::

        class FooView(APIView):
            permission_classes = [IsAuthenticated, HasCapability]
            required_capability = 'payments.edit'

    por::

        class FooView(CapabilityRequiredMixin, APIView):
            required_capability = 'payments.edit'

    **Colocar el mixin ANTES** de ``APIView``/``ViewSet`` en la herencia (para
    que su ``permission_classes`` gane). NO reemplaza a ``HasCapability`` — lo
    declara; el chequeo (incl. gate DEC-12) sigue en el permission class.
    """
    permission_classes = [IsAuthenticated, HasCapability]


def require_capability(code):
    """Decorador para vistas función ``@api_view``: fija
    ``permission_classes = [IsAuthenticated, RequireCapability(code)]``.

    Cubre el caso que el mixin (herencia de clase) no alcanza — handlers
    function-based. **Aplicar DEBAJO de** ``@api_view`` (más interno) para que
    DRF lea el ``permission_classes`` al envolver::

        @api_view(['POST'])
        @require_capability('inventory.adjust')
        def adjust(request): ...

    Para ``@action`` de un ``ViewSet``, preferir el kwarg nativo
    ``@action(..., permission_classes=[IsAuthenticated, RequireCapability(code)])``
    (DRF sólo lee las permission_classes de acción por ese kwarg). El chequeo
    real —incl. gate DEC-12— lo hace ``HasCapability``.
    """
    def decorator(view_func):
        view_func.permission_classes = [IsAuthenticated, RequireCapability(code)]
        return view_func
    return decorator
