"""Vistas admin — addons.authz.

Superficie del panel admin gateada por capacidad (nunca por ``is_staff``, que
ya no existe en ``IdentityUser`` U-D). Todas exigen ``permissions.full``:

- ``GET  /api/v2/admin/roles/`` — catálogo de roles para el selector de
  asignación usuario→rol (UC-ADM-02, G-PERM-01). Read-only.
- ``GET  /api/v2/admin/permissions/`` — matriz roles×capacidades para el editor
  ``/admin/permissions`` de la UI. Devuelve ``{roles:[{role, permissions}],
  permissions:[{code, level}]}``.
- ``PUT  /api/v2/admin/roles/<code>/permissions/`` — edita el set graduado de
  capacidades de un rol (reemplaza). Los roles son editables en runtime **con
  contención de escalada por nivel** (H-UI-PERM-01, DEC-11): un delegado con
  ``permissions.full`` solo puede conceder un sustantivo hasta SU propio nivel
  en ese sustantivo, y solo las acciones nombradas que él posee; el superadmin
  no tiene ese límite y su rol solo lo edita otro superadmin.
"""
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from addons.authz.admin_serializers import (
    AdminRoleSerializer, RolePermissionsWriteSerializer, capability_rows,
    is_noun,
)
from addons.authz.models import AccessLevel, Capability, Role, RoleAssignment, RoleCapability
from addons.authz.permissions import HasCapability
from addons.authz.services import (
    SUPERADMIN_ROLE_CODE, invalidate_capabilities, is_superadmin,
    resolve_capabilities, resolve_capability_levels,
)
from addons.users.audit import audit_log_business

# Gestionar permisos = nivel FULL del sustantivo ``permissions`` (DEC-11).
PERMISSIONS_MANAGE = 'permissions.full'


def _active_capability_codes():
    """Set de códigos de capacidad activos (sustantivos + acciones nombradas)."""
    return set(
        Capability.objects.filter(is_active=True).values_list('code', flat=True)
    )


def _grantable_for_user(user, active_codes):
    """``[{code, level}]`` que ``user`` (delegado no-superadmin) puede conceder:
    los sustantivos que posee (con su nivel máximo como techo) + sus acciones
    nombradas. Ordenado por ``code``."""
    active_named = {c for c in active_codes if not is_noun(c)}
    own_levels = resolve_capability_levels(user)          # {noun: AccessLevel}
    own_named = active_named & resolve_capabilities(user)
    rows = [
        {'code': noun, 'level': level.name}
        for noun, level in own_levels.items()
        if noun in active_codes
    ]
    rows += [{'code': code, 'level': None} for code in own_named]
    return sorted(rows, key=lambda r: r['code'])


def _grantable_for_superadmin(active_codes):
    """``[{code, level}]`` de todo el catálogo activo: sustantivos a ``FULL``,
    acciones nombradas con ``level: null``."""
    rows = [
        {'code': c, 'level': 'FULL'} if is_noun(c) else {'code': c, 'level': None}
        for c in active_codes
    ]
    return sorted(rows, key=lambda r: r['code'])


class AdminRoleListView(ListAPIView):
    """Catálogo de roles (read-only) para el selector de ``/admin/permissions``.

    Gateado por ``permissions.full`` — la misma capacidad que la asignación
    (``AdminUserViewSet.permissions``): quien puede asignar roles puede ver el
    catálogo. Sin paginación: el número de roles es pequeño y estable.

    **Contención de escalada:** el rol ``superadmin`` (que concede TODAS las
    capacidades) se oculta a quien no es superadmin. El candado real está en la
    escritura (``AdminUserViewSet.permissions``); este filtro evita exponer el
    id en el picker. Simétrico con el guard ``CANNOT_GRANT_SUPERADMIN``.
    """

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = PERMISSIONS_MANAGE
    serializer_class = AdminRoleSerializer
    pagination_class = None

    def get_queryset(self):
        qs = (Role.objects
              .prefetch_related('role_capabilities__capability')
              .order_by('code'))
        if not is_superadmin(self.request.user):
            qs = qs.exclude(code=SUPERADMIN_ROLE_CODE)
        return qs


class AdminPermissionCatalogView(APIView):
    """``GET /api/v2/admin/permissions/`` — matriz roles×capacidades (UC-ADM-02).

    Alimenta el editor ``/admin/permissions`` de la UI. Contrato::

        {"roles": [{"role": "<code>", "permissions": [{"code", "level"}, ...]}],
         "permissions": [{"code": "<code>", "level": "<AccessLevel|null>"}, ...]}

    ``roles`` es el catálogo (superadmin oculto para el no-superadmin, igual que
    ``AdminRoleListView``). ``permissions`` es el set que el caller puede
    **conceder**: para superadmin, todo el catálogo activo con su techo; para un
    delegado, los sustantivos que posee (con su nivel como techo) + sus acciones
    nombradas (coherente con la contención de escalada del PUT).
    """

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = PERMISSIONS_MANAGE

    def get(self, request):
        superadmin = is_superadmin(request.user)

        roles_qs = (Role.objects
                    .prefetch_related('role_capabilities__capability')
                    .order_by('code'))
        if not superadmin:
            roles_qs = roles_qs.exclude(code=SUPERADMIN_ROLE_CODE)
        roles = [
            {'role': r.code, 'permissions': capability_rows(r)}
            for r in roles_qs
        ]

        active = _active_capability_codes()
        if superadmin:
            grantable = _grantable_for_superadmin(active)
        else:
            grantable = _grantable_for_user(request.user, active)

        return Response({'roles': roles, 'permissions': grantable})


class AdminRolePermissionsView(APIView):
    """``PUT /api/v2/admin/roles/<code>/permissions/`` — edita el set graduado
    de capacidades de un rol (UC-ADM-02, H-UI-PERM-01, DEC-11).

    Body: ``{"permissions": [{"code": "<noun|named>", "level": "<AccessLevel>"},
    ...]}`` — reemplaza el set completo. Para acciones nombradas (``code`` con
    punto) el ``level`` se ignora (membresía → ``FULL``). Guards:

    - ``permissions.full`` (gate de la vista).
    - El rol ``superadmin`` solo lo edita otro superadmin (403).
    - Códigos inexistentes/inactivos → 400.
    - **Contención de escalada por nivel:** un delegado no-superadmin solo puede
      conceder un sustantivo hasta SU propio nivel en ese sustantivo, y solo las
      acciones nombradas que él posee. Cambiar (conceder por encima, o
      revocar/alterar un grant que no controla) → 403. El superadmin no tiene
      ese límite.

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

        # Parsear el set deseado en sustantivos graduados + acciones nombradas.
        desired_nouns = {}   # {noun: AccessLevel}
        desired_named = set()
        for entry in ser.validated_data['permissions']:
            code = entry['code']
            if is_noun(code):
                desired_nouns[code] = AccessLevel[entry['level']]
            else:
                desired_named.add(code)
        desired_codes = set(desired_nouns) | desired_named

        active = _active_capability_codes()
        unknown = desired_codes - active
        if unknown:
            return Response(
                {'detail': 'Capacidades inexistentes o inactivas: '
                           + ', '.join(sorted(unknown)),
                 'codigo_error': 'UNKNOWN_CAPABILITY'},
                status=400,
            )

        # Estado actual del rol (graduado).
        current_nouns = {}
        current_named = set()
        for rc in role.role_capabilities.select_related('capability').all():
            code = rc.capability.code
            if is_noun(code):
                current_nouns[code] = AccessLevel(rc.level)
            else:
                current_named.add(code)

        # Contención de escalada por nivel (H-UI-PERM-01, DEC-11).
        if not superadmin:
            escalating = self._escalating(
                request.user, current_nouns, desired_nouns,
                current_named, desired_named, active,
            )
            if escalating:
                return Response(
                    {'detail': 'No puedes conceder ni revocar capacidades por '
                               'encima de tu propio nivel: '
                               + ', '.join(sorted(escalating)),
                     'codigo_error': 'CANNOT_GRANT_UNHELD_CAPABILITY'},
                    status=403,
                )

        # Reemplazar el set completo: limpiar las filas through y recrearlas con
        # su nivel (los sustantivos con su AccessLevel; las nombradas a FULL).
        role.capabilities.clear()
        cap_by_code = {
            c.code: c
            for c in Capability.objects.filter(code__in=desired_codes)
        }
        for noun, level in desired_nouns.items():
            RoleCapability.objects.create(
                role=role, capability=cap_by_code[noun], level=level,
            )
        for code in desired_named:
            RoleCapability.objects.create(
                role=role, capability=cap_by_code[code], level=AccessLevel.FULL,
            )

        # Purgar la cache de capacidades de cada usuario con el rol.
        for uid in (RoleAssignment.objects.filter(role=role)
                    .values_list('user_id', flat=True).distinct()):
            invalidate_capabilities(uid)

        permissions = capability_rows(role)
        audit_log_business(
            request.user,
            'ADMIN_ROLE_PERMISSIONS_CHANGED',
            request,
            target_type='role',
            target_id=role.pk,
            extra={'role_code': role.code, 'permissions': permissions},
        )

        return Response({'role': role.code, 'permissions': permissions})

    @staticmethod
    def _escalating(user, current_nouns, desired_nouns, current_named,
                    desired_named, active_codes):
        """Códigos que el delegado no puede conceder/revocar sin escalar.

        Sustantivo: cambiar su nivel exige que TANTO el nivel viejo como el
        nuevo estén dentro del techo del delegado (su propio nivel en ese
        sustantivo). Acción nombrada: alterar la membresía exige que el
        delegado la posea."""
        own_levels = resolve_capability_levels(user)             # {noun: AccessLevel}
        active_named = {c for c in active_codes if not is_noun(c)}
        own_named = active_named & resolve_capabilities(user)

        escalating = set()
        for noun in set(current_nouns) | set(desired_nouns):
            cur = current_nouns.get(noun, AccessLevel.NONE)
            des = desired_nouns.get(noun, AccessLevel.NONE)
            if cur == des:
                continue  # sin cambio
            ceiling = own_levels.get(noun, AccessLevel.NONE)
            if des > ceiling or cur > ceiling:
                escalating.add(noun)

        for code in current_named ^ desired_named:  # añadidas xor quitadas
            if code not in own_named:
                escalating.add(code)
        return escalating
