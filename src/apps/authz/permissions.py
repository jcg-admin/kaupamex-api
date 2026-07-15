"""Clases de permiso DRF — apps.authz.

Reemplazan ``rest_framework.permissions.IsAdminUser`` (que dependía de
``user.is_staff``, campo que ya no existe en ``IdentityUser`` U-D). El acceso
admin se gobierna por **capacidad** (``HasCapability``); la propiedad del
comprador por **objeto** (``IsOwnerOrAdmin``).

Diseño ratificado en :ref:`analisis-enforcement-hascapability-isowner`.
"""
from rest_framework.permissions import BasePermission

from apps.authz.services import has_capability


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
        pmap = getattr(view, 'permission_map', None)
        if pmap:
            action = getattr(view, 'action', None)
            if action in pmap:
                return pmap[action]
        return getattr(view, 'required_capability', None)

    def has_permission(self, request, view):
        return has_capability(request.user, self._needed(view))


def RequireCapability(code):
    """Factory: declara la capacidad inline en ``permission_classes``.

    Uso: ``permission_classes = [IsAuthenticated, RequireCapability('audit.view')]``
    """
    return type(
        f'HasCap_{code.replace(".", "_")}',
        (HasCapability,),
        {'required_capability': code},
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
