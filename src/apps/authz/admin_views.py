"""Vistas admin — apps.authz.

Superficie del panel admin gateada por capacidad (nunca por ``is_staff``, que
ya no existe en ``IdentityUser`` U-D). Todas exigen ``permissions.manage``:

- ``GET  /api/v2/admin/roles/`` — catálogo de roles para el selector de
  asignación usuario→rol (UC-ADM-02, G-PERM-01). Read-only.
- ``GET  /api/v2/admin/permissions/`` — matriz roles×capacidades para el editor
  ``/admin/permissions`` de la UI. Devuelve ``{roles:[{role, permissions}],
  permissions:[codes]}``.
- ``PUT  /api/v2/admin/roles/<code>/permissions/`` — edita el set de capacidades
  de un rol (reemplaza). Antes los roles eran estáticos-por-seed; ahora son
  editables en runtime **con contención de escalada** (H-UI-PERM-01): un
  delegado con ``permissions.manage`` solo puede togglear capacidades que él
  mismo posee (no puede concederse/quitar capacidades por encima de sí mismo);
  el superadmin no tiene ese límite y su rol solo lo edita otro superadmin.
"""
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authz.admin_serializers import (
    AdminRoleSerializer, RolePermissionsWriteSerializer,
)
from apps.authz.models import Capability, Role, RoleAssignment
from apps.authz.permissions import HasCapability
from apps.authz.services import (
    SUPERADMIN_ROLE_CODE, invalidate_capabilities, is_superadmin,
    resolve_capabilities,
)
from apps.users.audit import audit_log_business

PERMISSIONS_MANAGE = 'permissions.manage'


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
    required_capability = PERMISSIONS_MANAGE
    serializer_class = AdminRoleSerializer
    pagination_class = None

    def get_queryset(self):
        qs = Role.objects.prefetch_related('capabilities').order_by('code')
        if not is_superadmin(self.request.user):
            qs = qs.exclude(code=SUPERADMIN_ROLE_CODE)
        return qs


class AdminPermissionCatalogView(APIView):
    """``GET /api/v2/admin/permissions/`` — matriz roles×capacidades (UC-ADM-02).

    Alimenta el editor ``/admin/permissions`` de la UI. Contrato::

        {"roles": [{"role": "<code>", "permissions": ["<cap.code>", ...]}, ...],
         "permissions": ["<cap.code>", ...]}

    ``roles`` es el catálogo (superadmin oculto para el no-superadmin, igual que
    ``AdminRoleListView``). ``permissions`` es el set de capacidades que el
    caller puede **conceder**: todas las activas para el superadmin, solo las
    propias para un delegado (coherente con la contención de escalada del PUT).
    """

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = PERMISSIONS_MANAGE

    def get(self, request):
        superadmin = is_superadmin(request.user)

        roles_qs = Role.objects.prefetch_related('capabilities').order_by('code')
        if not superadmin:
            roles_qs = roles_qs.exclude(code=SUPERADMIN_ROLE_CODE)
        roles = [
            {'role': r.code,
             'permissions': sorted(c.code for c in r.capabilities.all())}
            for r in roles_qs
        ]

        all_active = set(
            Capability.objects.filter(is_active=True).values_list('code', flat=True)
        )
        grantable = all_active if superadmin else (all_active & resolve_capabilities(request.user))

        return Response({'roles': roles, 'permissions': sorted(grantable)})


class AdminRolePermissionsView(APIView):
    """``PUT /api/v2/admin/roles/<code>/permissions/`` — edita el set de
    capacidades de un rol (UC-ADM-02, H-UI-PERM-01).

    Body: ``{"permissions": ["<cap.code>", ...]}`` — reemplaza el set completo
    (mismo criterio ``set()`` que la asignación de roles a usuario). Guards:

    - ``permissions.manage`` (gate de la vista).
    - El rol ``superadmin`` solo lo edita otro superadmin (403).
    - Códigos inexistentes/inactivos → 400.
    - **Contención de escalada:** un delegado no-superadmin solo puede
      *cambiar* capacidades que él mismo posee. Toda capacidad en el diff
      (``current △ desired``) fuera de su set efectivo → 403. Así no puede
      concederle a un rol una capacidad que él no tiene (auto-promoción vía
      rol), ni revocar una que no controla. El superadmin no tiene ese límite.

    Purga la cache de capacidades de todos los usuarios con el rol y audita el
    cambio (``ADMIN_ROLE_PERMISSIONS_CHANGED``).
    """

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = PERMISSIONS_MANAGE

    def put(self, request, role_code):
        role = Role.objects.filter(code=role_code).first()
        if role is None:
            return Response(
                {'detail': 'Rol no encontrado.', 'codigo_error': 'ROLE_NOT_FOUND'},
                status=404,
            )

        superadmin = is_superadmin(request.user)
        if role.code == SUPERADMIN_ROLE_CODE and not superadmin:
            return Response(
                {'detail': 'Solo un superadministrador puede editar el rol de '
                           'superusuario.',
                 'codigo_error': 'CANNOT_EDIT_SUPERADMIN'},
                status=403,
            )

        ser = RolePermissionsWriteSerializer(data=request.data)
        if not ser.is_valid():
            return Response(
                {'detail': 'Payload inválido.',
                 'codigo_error': 'INVALID_PAYLOAD',
                 'errors': ser.errors},
                status=400,
            )
        desired = set(ser.validated_data['permissions'])

        all_active = set(
            Capability.objects.filter(is_active=True).values_list('code', flat=True)
        )
        unknown = desired - all_active
        if unknown:
            return Response(
                {'detail': 'Capacidades inexistentes o inactivas: '
                           + ', '.join(sorted(unknown)),
                 'codigo_error': 'UNKNOWN_CAPABILITY'},
                status=400,
            )

        current = set(role.capabilities.values_list('code', flat=True))

        # Contención de escalada (H-UI-PERM-01): un delegado solo puede togglear
        # capacidades que él mismo posee. Las capacidades fuera de su set quedan
        # congeladas en su valor actual — si el diff las toca, es escalada.
        if not superadmin:
            own = resolve_capabilities(request.user)
            escalating = (current ^ desired) - own
            if escalating:
                return Response(
                    {'detail': 'No puedes conceder ni revocar capacidades que '
                               'tú mismo no posees: ' + ', '.join(sorted(escalating)),
                     'codigo_error': 'CANNOT_GRANT_UNHELD_CAPABILITY'},
                    status=403,
                )

        role.capabilities.set(Capability.objects.filter(code__in=desired))

        # Purgar la cache de capacidades de cada usuario con el rol (indirect
        # entitlement mutado). Purga por usuario distinto (un rol puede estar
        # asignado a muchos).
        for uid in (RoleAssignment.objects.filter(role=role)
                    .values_list('user_id', flat=True).distinct()):
            invalidate_capabilities(uid)

        audit_log_business(
            request.user,
            'ADMIN_ROLE_PERMISSIONS_CHANGED',
            request,
            target_type='role',
            target_id=role.pk,
            extra={'role_code': role.code, 'permissions': sorted(desired)},
        )

        return Response({'role': role.code, 'permissions': sorted(desired)})
