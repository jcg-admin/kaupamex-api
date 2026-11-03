"""El token del webhook de Peppol es el de la fuente.

≙ ``_generate_webhook_token`` y ``_get_user_from_token``
(``odoo19c: addons/account_peppol/models/account_edi_proxy_user.py:584-611``):
``hash_sign`` de ``[company.id, endpoint]`` en el ámbito
``account_peppol_webhook`` por 30 días, y la vuelta con
``verify_hash_signed`` más la guarda de que la URL empiece por el endpoint.
"""

import pytest

from addons.account_edi_proxy_client.models.account_edi_proxy_user import (
    AccountEdiProxyUser)
from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.res_company import ResCompany
from orm.environments import env
from tools.misc import verify_hash_signed

pytestmark = pytest.mark.django_db


@pytest.fixture
def company():
    SystemParameter.set_param('web.base.url', 'https://kaupamex.test')
    return ResCompany.objects.create(name='Kaupamex QA Peppol')


def test_the_token_is_hash_sign_of_company_and_endpoint(company):
    token = AccountEdiProxyUser._generate_webhook_token(company)
    payload = verify_hash_signed(env(), 'account_peppol_webhook', token)
    assert payload == [company.pk, 'https://kaupamex.test/peppol/webhook']
    assert verify_hash_signed(env(), 'otro_ambito', token) is None


def test_a_url_outside_the_signed_endpoint_is_refused(company):
    token = AccountEdiProxyUser._generate_webhook_token(company)
    assert AccountEdiProxyUser._get_user_from_token(
        token, 'https://otro.test/peppol/webhook') is None


def test_a_malformed_token_is_refused():
    assert AccountEdiProxyUser._get_user_from_token(
        'AAAA', 'https://kaupamex.test/peppol/webhook') is None


def test_the_endpoint_keeps_the_path_of_the_base_url():
    """La fuente concatena ``get_base_url() + '/peppol/webhook'``: una
    instalación servida bajo una ruta la conserva. ``urljoin`` la perdía."""
    SystemParameter.set_param('web.base.url', 'https://kaupamex.test/erp')
    company = ResCompany.objects.create(name='Kaupamex QA Peppol ruta')
    expected = 'https://kaupamex.test/erp/peppol/webhook'
    assert company._get_peppol_webhook_endpoint() == expected
