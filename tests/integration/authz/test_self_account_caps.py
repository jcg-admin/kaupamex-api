"""Integration — capacidades de "cuenta propia" sembradas en TODOS los roles.

Al gatear los endpoints de cuenta propia (perfil/contraseña/sesiones/baja,
recibo/historial de pago) con ``account.*`` (DEC-ENF-01), ``seed_authz`` debe
sembrar esas capacidades en **todos** los roles para que un usuario no-comprador
(p. ej. staff no-superadmin) no quede fuera de su propia cuenta
(decisión ejecutor 2026-07-12).
"""
from addons.authz.models import Capability, Role, RoleAssignment
from addons.authz.services import invalidate_capabilities

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APIClient

pytestmark = pytest.mark.integration

User = get_user_model()
# Reapuntado: el perfil propio es ``/my/account`` de ``portal`` en la
# referencia (odoo19c, LGPL-3), montado aquí como /api/v2/portal/account/.
PROFILE_URL = '/api/v2/portal/account/'
SELF_ACCOUNT = {'account.profile', 'account.password',
                'account.deactivate', 'account.payments'}


def test_seed_grants_self_account_caps_to_preexisting_roles(db):
    # Un rol de staff creado ANTES del seed, con una sola capacidad ajena.
    staff_role = Role.objects.create(code='staff-x', name='Staff X')
    call_command('seed_authz')
    staff_role.refresh_from_db()
    have = set(staff_role.capabilities.values_list('code', flat=True))
    assert SELF_ACCOUNT.issubset(have), have


def test_non_comprador_staff_can_read_own_profile(db):
    # Staff no-superadmin, NO comprador: tras el seed su rol tiene account.profile,
    # así que accede a SU perfil (no queda fuera por el candado).
    staff_role = Role.objects.create(code='staff-y', name='Staff Y')
    call_command('seed_authz')
    u = User.objects.create_user(login='staffy@e.com', password='StaffPass123!')
    RoleAssignment.objects.create(user=u, role=staff_role)
    invalidate_capabilities(u.id)
    client = APIClient()
    client.force_authenticate(u)
    assert client.get(PROFILE_URL).status_code == 200


def test_user_without_any_role_is_denied_own_profile(db):
    # Sin rol alguno → sin account.profile → 403 (el candado aplica).
    call_command('seed_authz')
    u = User.objects.create_user(login='norole@e.com', password='NoRolePass123!')
    client = APIClient()
    client.force_authenticate(u)
    assert client.get(PROFILE_URL).status_code == 403
