"""
Tests del management command mp_sandbox_charge.

Dos niveles:
  - Unit (corren en CI, sin red): validación de --status/--method, error
    accionable si no hay gateway, y coherencia de los mapeos.
  - Integración opt-in (NO corre en CI): cobro real contra MP sandbox.
    Saltado salvo que RUN_MP_SANDBOX=1 y existan las MP_TEST_* en env/.env.

BD: practicayoruba_qa (config.settings.testing).
"""
import os

import pytest
import decouple
from django.core.management.base import CommandError

from apps.settings_app.models import PaymentGateway
from apps.payments.management.commands.mp_sandbox_charge import (
    run_sandbox_charge, TEST_CARDS, STATUS_NAMES, EXPECTED_MP_STATUS,
)

pytestmark = pytest.mark.integration


# --------------------------------------------------------------------------
# Unit — corren en CI, sin red
# --------------------------------------------------------------------------
class TestMpSandboxChargeValidation:
    def test_invalid_status_raises(self, db):
        with pytest.raises(CommandError):
            run_sandbox_charge(status='NOPE', method='master')

    def test_invalid_method_raises(self, db):
        with pytest.raises(CommandError):
            run_sandbox_charge(status='APRO', method='amex')

    def test_no_active_gateway_raises(self, db):
        # status/method válidos, pero sin gateway activo → error accionable
        PaymentGateway.objects.filter(gateway='MERCADOPAGO').delete()
        with pytest.raises(CommandError) as exc:
            run_sandbox_charge(status='APRO', method='master')
        assert 'setup_mp_gateway' in str(exc.value)


class TestMpSandboxChargeMaps:
    def test_status_names_have_expected_mp_status(self):
        # todo nombre de titular tiene un status MP esperado
        assert set(EXPECTED_MP_STATUS) == STATUS_NAMES

    def test_test_cards_cover_credit_and_debit(self):
        assert {'master', 'visa', 'debmaster', 'debvisa'} <= set(TEST_CARDS)
        for card in TEST_CARDS.values():
            assert card['number'].isdigit()
            assert card['exp_yy'] >= 2030


# --------------------------------------------------------------------------
# Integración opt-in — cobro real contra MP sandbox (NO en CI)
# --------------------------------------------------------------------------
def _env(name):
    return os.environ.get(name) or decouple.config(name, default='')


_RUN = os.environ.get('RUN_MP_SANDBOX') == '1' and bool(_env('MP_TEST_ACCESS_TOKEN'))

pytest_sandbox = pytest.mark.skipif(
    not _RUN,
    reason='cobro sandbox: definir RUN_MP_SANDBOX=1 + MP_TEST_* en env/.env')


def _seed_sandbox_gateway():
    creds = {
        'access_token': _env('MP_TEST_ACCESS_TOKEN'),
        'public_key':   _env('MP_TEST_PUBLIC_KEY'),
    }
    secret = _env('MP_TEST_CLIENT_SECRET')
    if secret:
        creds['client_secret'] = secret
    gw, _ = PaymentGateway.objects.get_or_create(
        gateway='MERCADOPAGO',
        defaults={'name': 'MercadoPago Sandbox', 'is_active': True})
    gw.is_active = True
    gw.set_credentials(creds)
    gw.save()
    return gw


@pytest_sandbox
class TestMpSandboxChargeLive:
    def test_apro_is_approved(self, db):
        _seed_sandbox_gateway()
        r = run_sandbox_charge(status='APRO', method='master', keep=True)
        assert r['mp_status'] == 'approved', r
        assert r['order_status'] == 'PAID', r

    def test_fund_is_rejected(self, db):
        _seed_sandbox_gateway()
        r = run_sandbox_charge(status='FUND', method='master', keep=True)
        assert r['mp_status'] == 'rejected', r
        assert r['order_status'] == 'PENDING', r
