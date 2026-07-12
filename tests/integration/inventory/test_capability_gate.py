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
from apps.authz.models import Capability, Module, Role, RoleAssignment

import pytest

pytestmark = pytest.mark.integration

INV_DASHBOARD = '/api/v2/admin/inventory/'


def _user_with_caps(email, codes):
    """Usuario NO-superadmin con exactamente las capacidades ``codes`` (dominio
    inventory) vía un rol dedicado. Como no es superadmin, ``HasCapability`` se
    evalúa de verdad (sin bypass del resolver)."""
    module, _ = Module.objects.get_or_create(
        code='inventory', defaults={'name': 'Inventario'},
    )
    caps = []
    for code in codes:
        cap, _ = Capability.objects.get_or_create(
            code=code, defaults={'module': module, 'name': code},
        )
        caps.append(cap)
    role, _ = Role.objects.get_or_create(
        code=f'role_{"_".join(c.replace(".", "_") for c in codes)}',
        defaults={'name': 'Test inventory role'},
    )
    role.capabilities.set(caps)
    u = get_user_model().objects.create_user(email=email, password='TestPass123!')
    RoleAssignment.objects.create(user=u, role=role)
    return u


class TestInventoryManageCapabilityGate:
    """El candado ``inventory.manage`` gobierna el acceso al inventario para
    usuarios granulares (no-superadmin)."""

    def test_manager_with_inventory_manage_can_access(self, api_client, db):
        # Camino POSITIVO: un usuario con inventory.manage SÍ gestiona inventario.
        manager = _user_with_caps(
            'inv_manager@practicayoruba.mx', ['inventory.manage'],
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
