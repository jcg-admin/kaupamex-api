"""
Tests — Inventory capability gate (positive + negative granular path)

DEC-AUTHZ-01 / DEC-ENF-01: las vistas de inventario exigen la capacidad
``inventory.manage`` vía ``HasCapability`` (``apps/inventory/views.py``,
mixin ``_AdminOnly`` + vistas V2). Superadmin hace bypass del resolver, así
que las suites que usan ``admin_client`` prueban el acceso de superadmin —
NO el camino granular (un usuario NO-superadmin con exactamente
``inventory.manage``).

Este módulo cierra ese hueco: verifica el camino positivo (un usuario con el
permiso correcto SÍ puede gestionar el inventario) y el negativo (sin el
permiso → 403), sin bypass de superadmin.
"""
from django.contrib.auth import get_user_model
from addons.authz.models import (
    AccessLevel, Capability, Module, Role, RoleAssignment, RoleCapability,
)

import pytest

pytestmark = pytest.mark.integration

INV_DASHBOARD = '/api/v2/admin/inventory/'

# Verbo CRUD → nivel (DEC-11); ``manage`` es el alias legado del tope (FULL).
_VERB_LEVEL = {
    'view': AccessLevel.VIEW, 'create': AccessLevel.CREATE,
    'edit': AccessLevel.EDIT, 'full': AccessLevel.FULL,
}


def _user_with_caps(email, codes):
    """Usuario NO-superadmin con exactamente las capacidades ``codes`` vía un
    rol dedicado. Como no es superadmin, ``HasCapability`` se evalúa de verdad
    (sin bypass del resolver).

    DEC-11: un código legado ``X.verbo`` se traduce a sustantivo ``X`` al nivel
    del verbo (``inventory.manage`` → ``inventory`` @ FULL)."""
    role, _ = Role.objects.get_or_create(
        code=f'role_{"_".join(c.replace(".", "_") for c in codes)}',
        defaults={'name': 'Test inventory role'},
    )
    for code in codes:
        noun, _, verb = code.partition('.')
        if verb in _VERB_LEVEL:                # sustantivo graduado
            target, level = noun, _VERB_LEVEL[verb]
        else:                                  # acción nombrada (membresía)
            target, level = code, AccessLevel.FULL
        module, _ = Module.objects.get_or_create(
            code=target.split('.', 1)[0],
            defaults={'name': target},
        )
        cap, _ = Capability.objects.get_or_create(
            code=target, defaults={'module': module, 'name': target},
        )
        RoleCapability.objects.update_or_create(
            role=role, capability=cap, defaults={'level': level},
        )
    u = get_user_model().objects.create_user(email=email, password='TestPass123!')
    RoleAssignment.objects.create(user=u, role=role)
    return u


class TestInventoryManageCapabilityGate:
    """El candado ``inventory.manage`` gobierna el acceso al inventario para
    usuarios granulares (no-superadmin)."""

    def test_manager_with_inventory_manage_can_access(self, api_client, db):
        # Camino POSITIVO: un usuario con inventory.manage SÍ gestiona inventario.
        manager = _user_with_caps(
            'inv_manager@practicayoruba.mx', ['inventory.full'],
        )
        api_client.force_login(manager)
        res = api_client.get(INV_DASHBOARD)
        assert res.status_code == 200

    def test_user_without_inventory_manage_is_denied(self, api_client, db):
        # Camino NEGATIVO: un usuario sin la capacidad recibe 403.
        outsider = _user_with_caps(
            'inv_outsider@practicayoruba.mx', ['reports.view'],
        )
        api_client.force_login(outsider)
        res = api_client.get(INV_DASHBOARD)
        assert res.status_code == 403
