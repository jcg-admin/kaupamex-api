"""
Tests del management command mp_sandbox_charge.

Dos niveles:
  - Unit (corren en CI, sin red): validación de --status/--method, error
    accionable si no hay gateway, y coherencia de los mapeos.
  - Integración opt-in (NO corre en CI): cobro real contra MP sandbox.
    Saltado salvo que RUN_MP_SANDBOX=1 y existan las MP_TEST_* en env/.env.

BD: kaupamex_qa (config.settings.testing).
"""
import os
import hmac
import hashlib
import json

import pytest
import decouple
from django.core.management.base import CommandError
from django.test import Client

from addons.payment.models import PaymentGateway
from addons.orders.models import Order
from addons.payment.models import Payment, WebhookEvent
from addons.payment_mercado_pago.management.commands.mp_sandbox_charge import (
    run_sandbox_charge, TEST_CARDS, STATUS_NAMES, EXPECTED_MP_STATUS,
)

pytestmark = pytest.mark.integration

MP_WEBHOOK_URL = '/api/v1/payments/webhooks/mercadopago/'


def _mp_signature(client_secret, payment_id, request_id, ts):
    """Replica el manifest del SDK oficial: id (minúsculas) + request-id + ts,
    segmentos ausentes omitidos, trailing ';'. Header usa 'ts=..,v1=..'."""
    parts = []
    if payment_id:
        parts.append(f'id:{str(payment_id).lower()}')
    if request_id:
        parts.append(f'request-id:{request_id}')
    parts.append(f'ts:{ts}')
    manifest = ';'.join(parts) + ';'
    return hmac.new(client_secret.encode(), manifest.encode(),
                    hashlib.sha256).hexdigest()


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


@pytest_sandbox
class TestMpSandboxWebhookLive:
    """Webhook end-to-end contra MP **real**: a diferencia de los tests
    mockeados de test_payment_webhooks.py, aquí ``verify_payment`` consulta
    el pago real en el sandbox de MP. Cierra el hueco de "webhook con datos
    reales de MP", no solo la firma/idempotencia (ya cubiertas en CI)."""

    def _post_webhook(self, client, secret, mp_payment_id, order_number, req_id):
        ts = '1700000000000'
        sig = _mp_signature(secret, mp_payment_id, req_id, ts)
        body = {'type': 'payment', 'data': {'id': str(mp_payment_id)},
                'external_reference': order_number}
        return client.post(
            f'{MP_WEBHOOK_URL}?data.id={mp_payment_id}&type=payment',
            data=json.dumps(body), content_type='application/json',
            HTTP_X_SIGNATURE=f'ts={ts},v1={sig}', HTTP_X_REQUEST_ID=req_id)

    def test_webhook_confirms_approved_and_is_idempotent(self, db):
        gw = _seed_sandbox_gateway()
        secret = gw.get_credentials().get('client_secret')
        assert secret, 'define MP_TEST_CLIENT_SECRET para el test de webhook'

        charged = run_sandbox_charge(status='APRO', method='master', keep=True)
        mp_payment_id = charged['gateway_payment_id']
        order_number = charged['order_number']
        assert charged['mp_status'] == 'approved', charged

        client = Client()
        # 1er webhook: verify_payment REAL contra MP → approved → 200
        res1 = self._post_webhook(client, secret, mp_payment_id, order_number, 'req-mp-1')
        assert res1.status_code == 200, res1.content
        assert Order.objects.get(order_number=order_number).status == 'PAID'
        assert WebhookEvent.objects.filter(event_id=str(mp_payment_id)).count() == 1

        # Reintento REAL de MP: reusa el mismo request-id (la unicidad de dedup
        # es (gateway, event_id, transmission_id)) → already_processed.
        res2 = self._post_webhook(client, secret, mp_payment_id, order_number, 'req-mp-1')
        assert res2.status_code == 200, res2.content
        assert res2.json().get('status') == 'already_processed', res2.content
        assert WebhookEvent.objects.filter(event_id=str(mp_payment_id)).count() == 1

        # firma inválida → 401
        res3 = client.post(
            f'{MP_WEBHOOK_URL}?data.id={mp_payment_id}&type=payment',
            data=json.dumps({'type': 'payment', 'data': {'id': str(mp_payment_id)}}),
            content_type='application/json',
            HTTP_X_SIGNATURE='ts=1,v1=deadbeef', HTTP_X_REQUEST_ID='req-3')
        assert res3.status_code == 401, res3.content

        # cleanup (keep=True no limpió): hard delete
        for p in Payment.objects.filter(order__order_number=order_number):
            (p.hard_delete if hasattr(p, 'hard_delete') else p.delete)()
        Order.all_objects.filter(order_number=order_number).first().hard_delete()
        WebhookEvent.objects.filter(event_id=str(mp_payment_id)).delete()
