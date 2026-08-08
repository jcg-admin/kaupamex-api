"""Serializers admin — addons.authz.

Superficie del panel admin (capacidad ``permissions.full``): el catálogo de
roles disponibles para el selector de ``/admin/permissions`` (UC-ADM-02).
Complementa ``addons.authz.controllers.serializers`` (superficie del usuario autenticado).

**DEC-11 (sustantivo + nivel).** Las capacidades CRUD se exponen como
``{code, level}`` donde ``code`` es el sustantivo y ``level`` el nombre del
``AccessLevel`` (``VIEW``/``CREATE``/``EDIT``/``FULL``). Las acciones nombradas
(``code`` con punto) son membresía y llevan ``level: null``.
"""
from rest_framework import serializers

from addons.authz.models import AccessLevel, Role

# Niveles asignables (se excluye ``NONE``, que es la ausencia de nivel).
GRANTABLE_LEVEL_NAMES = [lv.name for lv in AccessLevel if lv != AccessLevel.NONE]


def is_noun(code):
    """``True`` si ``code`` es un sustantivo graduado (sin punto); ``False`` si
    es una acción nombrada (con punto → membresía)."""
    return '.' not in code


def capability_rows(role):
    """``[{code, level}]`` de un rol: ``level`` = nombre del ``AccessLevel`` para
    sustantivos graduados; ``None`` para acciones nombradas (membresía).

    Requiere ``role.role_capabilities`` prefetch-eado con ``capability`` para
    evitar N+1. Ordenado por ``code`` (contrato estable)."""
    rows = []
    for rc in role.role_capabilities.all():
        code = rc.capability.code
        if is_noun(code):
            rows.append({'code': code, 'level': AccessLevel(rc.level).name})
        else:
            rows.append({'code': code, 'level': None})
    return sorted(rows, key=lambda r: r['code'])


class AdminRoleSerializer(serializers.ModelSerializer):
    """Un rol del catálogo: ``id`` (para el POST de asignación), ``code``,
    ``name`` y la lista de ``capabilities`` como ``[{code, level}]``."""

    capabilities = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ['id', 'code', 'name', 'capabilities']

    def get_capabilities(self, obj) -> list:
        return capability_rows(obj)


class RolePermissionEntrySerializer(serializers.Serializer):
    """Una entrada del set de permisos de un rol: ``{code, level?}``.

    ``level`` es obligatorio y válido (``VIEW``/``CREATE``/``EDIT``/``FULL``)
    cuando ``code`` es un sustantivo; se ignora para acciones nombradas."""

    code = serializers.CharField(allow_blank=False)
    level = serializers.ChoiceField(
        choices=GRANTABLE_LEVEL_NAMES, required=False, allow_null=True,
    )


class RolePermissionsWriteSerializer(serializers.Serializer):
    """Input de ``PUT /api/v2/admin/roles/<code>/permissions/`` (UC-ADM-02).

    ``permissions`` es el set COMPLETO de ``{code, level}`` que el rol debe
    tener tras el cambio (reemplaza, no acumula). La validación de
    existencia/activación de cada código y la contención de escalada por nivel
    viven en la vista."""

    permissions = RolePermissionEntrySerializer(many=True)

    def validate_permissions(self, entries):
        for entry in entries:
            code = entry['code']
            if is_noun(code) and not entry.get('level'):
                raise serializers.ValidationError(
                    f"El sustantivo '{code}' requiere un 'level' "
                    f"({', '.join(GRANTABLE_LEVEL_NAMES)}).",
                )
        return entries


class UserRolesWriteSerializer(serializers.Serializer):
    """Cuerpo de ``POST /admin/users/<pk>/permissions/`` — reemplaza el set.

    Es reemplazo, no adición: el cliente manda el conjunto completo que debe
    quedar. Un ``roles: []`` deja al usuario sin roles, y ésa es la vía por la
    que se revoca — por eso el guard de escalada tiene que mirar también la
    lista vacía, no sólo la presencia del rol superadmin.
    """

    roles = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=True,
        help_text='Ids de los roles que el usuario debe tener tras la '
                  'operación.',
    )
