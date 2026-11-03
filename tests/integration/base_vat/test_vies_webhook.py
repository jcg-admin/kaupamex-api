"""El webhook de vuelta del VIES.

≙ ``BaseVatWebhookController.webhook_update_vies``
(``odoo19c: addons/base_vat/controllers/webhook.py``): público y sin CSRF,
porque su autenticación es el ``webhook_token`` que esta base firmó al
consultar. Un token válido actualiza el estado de los partners con ese VAT;
uno falso no toca nada.
"""

import pytest
from rest_framework.test import APIClient

from addons.base.models.res_partner import ResPartner
from orm.environments import env
from tools.misc import hash_sign

pytestmark = pytest.mark.django_db

URL = '/base_vat/1/webhook_update_vies'
VAT = 'BE0477472701'


def _partner():
    return ResPartner.objects.create(name='Partner VIES webhook', vat=VAT)


def test_a_signed_token_updates_every_partner_with_that_vat():
    first, second = _partner(), _partner()
    token = hash_sign(env(), 'vies_check', VAT, expiration_hours=1)
    params = {'webhook_token': token, 'status': 'valid'}
    response = APIClient().get(URL, params)
    assert response.status_code == 200
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.vies_valid is True and second.vies_valid is True


def test_a_token_from_another_scope_changes_nothing():
    partner = _partner()
    token = hash_sign(env(), 'otro', VAT, expiration_hours=1)
    params = {'webhook_token': token, 'status': 'valid'}
    response = APIClient().post(URL, params)
    assert response.status_code == 200
    partner.refresh_from_db()
    assert partner.vies_valid is False
