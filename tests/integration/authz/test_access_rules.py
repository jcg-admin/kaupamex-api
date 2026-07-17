"""Motor de record rules nativo (L3) — ``AccessRule`` (DEC-KX-02).

Estilo Odoo ``ir.rule`` reimplementado nativo: modelo + rol (grupo) + dominio
(filtro serializable), editable en runtime, aplicable a cualquier dimensión.
Aditivo: concede visibilidad de un subconjunto de filas dentro de la company
ya resuelta (L1). Reglas de distintos roles del usuario se combinan con OR
(semántica de grupos de ``ir.rule``); sin reglas → sin restricción.
"""
import pytest

from addons.authz.models import AccessRule, Module, Role, RoleAssignment
from addons.authz.record_rules import access_q_for, apply_access_rules
from tests.factories.user_factory import UserFactory

pytestmark = pytest.mark.django_db


def test_no_rules_returns_none():
    """Sin AccessRule para el usuario → None (L3 no restringe; refina L1/L2)."""
    user = UserFactory()
    assert access_q_for('authz.module', user) is None


def test_literal_domain_filters_queryset():
    """Un dominio literal acota el queryset a las filas que matchea."""
    user = UserFactory()
    role = Role.objects.create(code='r-x', name='X')
    RoleAssignment.objects.create(user=user, role=role)
    Module.objects.create(code='rule-a', name='A')
    Module.objects.create(code='rule-b', name='B')
    Module.objects.create(code='rule-c', name='C')
    AccessRule.objects.create(
        role=role, model_label='authz.module',
        domain={'code__in': ['rule-a', 'rule-b']},
    )
    qs = apply_access_rules(Module.objects.filter(code__startswith='rule-'), user)
    assert set(qs.values_list('code', flat=True)) == {'rule-a', 'rule-b'}


def test_user_placeholder_resolves_to_pk():
    """El placeholder ``$user`` se resuelve al pk del usuario en runtime."""
    user = UserFactory()
    other = UserFactory()
    role = Role.objects.create(code='r-y', name='Y')
    RoleAssignment.objects.create(user=user, role=role)
    RoleAssignment.objects.create(user=other, role=role)
    # Regla: cada quien ve solo SUS propias asignaciones de rol.
    AccessRule.objects.create(
        role=role, model_label='authz.roleassignment',
        domain={'user_id': '$user'},
    )
    qs = apply_access_rules(RoleAssignment.objects.all(), user)
    assert qs.count() >= 1
    assert all(ra.user_id == user.pk for ra in qs)


def test_rules_across_roles_are_or_combined():
    """Reglas de distintos roles del usuario se combinan con OR (ir.rule)."""
    user = UserFactory()
    r1 = Role.objects.create(code='r-1', name='1')
    r2 = Role.objects.create(code='r-2', name='2')
    RoleAssignment.objects.create(user=user, role=r1)
    RoleAssignment.objects.create(user=user, role=r2)
    Module.objects.create(code='or-1', name='1')
    Module.objects.create(code='or-2', name='2')
    Module.objects.create(code='or-3', name='3')
    AccessRule.objects.create(role=r1, model_label='authz.module', domain={'code': 'or-1'})
    AccessRule.objects.create(role=r2, model_label='authz.module', domain={'code': 'or-2'})
    qs = apply_access_rules(Module.objects.filter(code__startswith='or-'), user)
    assert set(qs.values_list('code', flat=True)) == {'or-1', 'or-2'}


def test_inactive_rule_is_ignored():
    """Una regla ``is_active=False`` no restringe (como si no existiera)."""
    user = UserFactory()
    role = Role.objects.create(code='r-z', name='Z')
    RoleAssignment.objects.create(user=user, role=role)
    Module.objects.create(code='off-1', name='1')
    Module.objects.create(code='off-2', name='2')
    AccessRule.objects.create(
        role=role, model_label='authz.module',
        domain={'code': 'off-1'}, is_active=False,
    )
    qs = apply_access_rules(Module.objects.filter(code__startswith='off-'), user)
    assert set(qs.values_list('code', flat=True)) == {'off-1', 'off-2'}
