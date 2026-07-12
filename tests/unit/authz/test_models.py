"""Tests — apps.authz modelos (Opción B, DEC-AUTHZ-01, MOD-027).

Cubre integridad de las 7 entidades: catálogo Module/Capability, agrupación
Role (M2M), grants directos + revocaciones con clave única (user, capability),
y AuthzEvent append-only (DEC-07).
"""
import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from apps.authz.models import (
    AuthzEvent, Capability, DirectEntitlement, EntitlementRevocation, Module,
    Role, RoleAssignment,
)

pytestmark = pytest.mark.django_db
User = get_user_model()


def _user(email='a@e.com', **kw):
    # Party (T-201): IdentityUser sólo tiene email como identificador.
    return User.objects.create_user(email=email, password='x', **kw)


def _cap(code='orders.refund', **kw):
    mod = kw.pop('module', None) or Module.objects.create(code='orders', name='Órdenes')
    return Capability.objects.create(module=mod, code=code, name=code, **kw)


def test_capability_code_unique():
    _cap(code='orders.refund')
    with pytest.raises(IntegrityError):
        Module_ = Module.objects.create(code='other', name='Other')
        Capability.objects.create(module=Module_, code='orders.refund', name='dup')


def test_role_groups_capabilities():
    c1 = _cap(code='orders.view')
    c2 = _cap(code='orders.refund', module=c1.module)
    role = Role.objects.create(code='ops', name='Operaciones')
    role.capabilities.add(c1, c2)
    assert role.capabilities.count() == 2
    assert set(c1.roles.values_list('code', flat=True)) == {'ops'}


def test_role_assignment_unique_per_user_role():
    u = _user()
    role = Role.objects.create(code='ops', name='Ops')
    RoleAssignment.objects.create(user=u, role=role)
    with pytest.raises(IntegrityError):
        RoleAssignment.objects.create(user=u, role=role)


def test_direct_entitlement_unique_per_user_capability():
    u = _user()
    cap = _cap()
    DirectEntitlement.objects.create(user=u, capability=cap)
    with pytest.raises(IntegrityError):
        DirectEntitlement.objects.create(user=u, capability=cap)


def test_revocation_coexists_with_grant():
    """Grant + revocación de la misma (user, capability) coexisten (tablas
    distintas): el resolver resta la revocación del grant."""
    u = _user()
    cap = _cap()
    DirectEntitlement.objects.create(user=u, capability=cap)
    EntitlementRevocation.objects.create(user=u, capability=cap, reason='baja')
    assert DirectEntitlement.objects.filter(user=u, capability=cap).exists()
    assert EntitlementRevocation.objects.filter(user=u, capability=cap).exists()


def test_authz_event_is_append_only():
    ev = AuthzEvent.objects.create(action=AuthzEvent.ACTION_DENY, capability_code='pos.cash_close')
    with pytest.raises(PermissionError):
        ev.reason = 'x'  # no-op attr; el guard salta en save()
        ev.save()
    with pytest.raises(PermissionError):
        ev.delete()
