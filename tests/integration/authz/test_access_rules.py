"""Motor de record rules nativo (L3) — ``AccessRule`` (DEC-KX-02).

Estilo Odoo ``ir.rule`` reimplementado nativo: modelo + rol (grupo) + dominio
(filtro serializable), editable en runtime, aplicable a cualquier dimensión.
Aditivo: concede visibilidad de un subconjunto de filas dentro de la company
ya resuelta (L1). Reglas de distintos roles del usuario se combinan con OR
(semántica de grupos de ``ir.rule``); sin reglas → sin restricción.
"""
import pytest
from django.db import IntegrityError, transaction

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


# ---------------------------------------------------------------------------
# Paridad ir.rule (SOL-094): operaciones CRUD + reglas globales (AND).
# ---------------------------------------------------------------------------


def test_global_rule_applies_without_role():
    """Una regla global (``role=None``) aplica aunque el usuario no tenga roles."""
    user = UserFactory()
    Module.objects.create(code='g-1', name='1')
    Module.objects.create(code='g-2', name='2')
    AccessRule.objects.create(role=None, model_label='authz.module', domain={'code': 'g-1'})
    qs = apply_access_rules(Module.objects.filter(code__startswith='g-'), user)
    assert set(qs.values_list('code', flat=True)) == {'g-1'}


def test_global_and_role_rule_are_and_combined():
    """Global (AND) se cruza con la de rol (OR): la fila debe satisfacer ambas."""
    user = UserFactory()
    role = Role.objects.create(code='r-ga', name='GA')
    RoleAssignment.objects.create(user=user, role=role)
    Module.objects.create(code='ga-keep', name='K', is_active=True)
    Module.objects.create(code='ga-role-only', name='R', is_active=True)
    Module.objects.create(code='ga-global-only', name='G', is_active=False)
    # Global: solo modulos activos. De rol: solo los que empiezan con 'ga-'.
    AccessRule.objects.create(role=None, model_label='authz.module', domain={'is_active': True})
    AccessRule.objects.create(role=role, model_label='authz.module', domain={'code__startswith': 'ga-'})
    qs = apply_access_rules(Module.objects.filter(code__startswith='ga-'), user)
    # 'ga-global-only' es 'ga-' (pasa rol) pero is_active=False (falla global) → excluido.
    assert set(qs.values_list('code', flat=True)) == {'ga-keep', 'ga-role-only'}


def test_perm_filters_by_mode():
    """Una regla con ``perm_write=False`` acota lectura pero no escritura."""
    user = UserFactory()
    role = Role.objects.create(code='r-pm', name='PM')
    RoleAssignment.objects.create(user=user, role=role)
    Module.objects.create(code='pm-1', name='1')
    Module.objects.create(code='pm-2', name='2')
    AccessRule.objects.create(
        role=role, model_label='authz.module', domain={'code': 'pm-1'},
        perm_read=True, perm_write=False, perm_create=False, perm_unlink=False,
    )
    read_qs = apply_access_rules(Module.objects.filter(code__startswith='pm-'), user, mode='read')
    write_qs = apply_access_rules(Module.objects.filter(code__startswith='pm-'), user, mode='write')
    assert set(read_qs.values_list('code', flat=True)) == {'pm-1'}          # regla aplica a read
    assert set(write_qs.values_list('code', flat=True)) == {'pm-1', 'pm-2'}  # sin regla write → sin restricción


def test_unlink_mode_uses_perm_unlink():
    """El modo ``unlink`` (borrar) usa ``perm_unlink`` (paridad ir.rule 'Delete')."""
    user = UserFactory()
    role = Role.objects.create(code='r-un', name='UN')
    RoleAssignment.objects.create(user=user, role=role)
    Module.objects.create(code='un-1', name='1')
    Module.objects.create(code='un-2', name='2')
    AccessRule.objects.create(
        role=role, model_label='authz.module', domain={'code': 'un-1'},
        perm_read=False, perm_write=False, perm_create=False, perm_unlink=True,
    )
    unlink_qs = apply_access_rules(Module.objects.filter(code__startswith='un-'), user, mode='unlink')
    read_qs = apply_access_rules(Module.objects.filter(code__startswith='un-'), user, mode='read')
    assert set(unlink_qs.values_list('code', flat=True)) == {'un-1'}         # aplica a unlink
    assert set(read_qs.values_list('code', flat=True)) == {'un-1', 'un-2'}   # no aplica a read


def test_universal_domain_grants_all():
    """Regla de dominio universal (``{}``) no restringe — patrón operador L0."""
    user = UserFactory()
    role = Role.objects.create(code='r-op', name='OP')
    RoleAssignment.objects.create(user=user, role=role)
    Module.objects.create(code='op-1', name='1')
    Module.objects.create(code='op-2', name='2')
    AccessRule.objects.create(role=role, model_label='authz.module', domain={})
    qs = apply_access_rules(Module.objects.filter(code__startswith='op-'), user)
    assert set(qs.values_list('code', flat=True)) == {'op-1', 'op-2'}


def test_invalid_mode_raises():
    """Un modo fuera de ``AccessRule.MODES`` es un error (paridad ir.rule)."""
    user = UserFactory()
    with pytest.raises(ValueError):
        access_q_for('authz.module', user, mode='delete')


def test_at_least_one_perm_constraint():
    """Una regla sin ninguna operación marcada viola la constraint (ir.rule)."""
    role = Role.objects.create(code='r-np', name='NP')
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AccessRule.objects.create(
                role=role, model_label='authz.module', domain={},
                perm_read=False, perm_write=False, perm_create=False, perm_unlink=False,
            )
