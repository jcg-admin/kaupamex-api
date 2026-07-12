"""Vistas admin — apps.authz.

Superficie del panel admin gateada por capacidad (nunca por ``is_staff``, que
ya no existe en ``IdentityUser`` U-D):

- ``GET /api/v2/admin/roles/`` — catálogo de roles disponibles para el selector
  de asignación de permisos (UC-ADM-02, G-PERM-01). Read-only: el catálogo se
  siembra con ``seed_authz`` (los roles son estáticos por diseño); la
  asignación se hace en ``POST /api/v2/admin/users/<pk>/permissions/``.
"""
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from apps.authz.admin_serializers import AdminRoleSerializer
from apps.authz.models import Role
from apps.authz.permissions import HasCapability
from apps.authz.services import SUPERADMIN_ROLE_CODE, is_superadmin


class AdminRoleListView(ListAPIView):
    """Catálogo de roles (read-only) para el selector de ``/admin/permissions``.

    Gateado por ``permissions.manage`` — la misma capacidad que la asignación
    (``AdminUserViewSet.permissions``): quien puede asignar roles puede ver el
    catálogo. Sin paginación: el número de roles es pequeño y estable.

    **Contención de escalada:** el rol ``superadmin`` (que concede TODAS las
    capacidades) se oculta a quien no es superadmin. Un delegado con
    ``permissions.manage`` no debe poder descubrir ni, por tanto, asignar
    superadmin — eso sería auto-promoción. El candado real está en la escritura
    (``AdminUserViewSet.permissions``); este filtro evita exponer el id en el
    picker. Simétrico con el guard ``CANNOT_GRANT_SUPERADMIN``.
    """

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'permissions.manage'
    serializer_class = AdminRoleSerializer
    pagination_class = None

    def get_queryset(self):
        qs = Role.objects.prefetch_related('capabilities').order_by('code')
        if not is_superadmin(self.request.user):
            qs = qs.exclude(code=SUPERADMIN_ROLE_CODE)
        return qs
