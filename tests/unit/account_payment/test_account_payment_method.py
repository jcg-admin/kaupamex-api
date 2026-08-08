"""Contrato de ``account_payment`` sobre ``account.payment.method`` — la
fusión de ``_get_payment_method_information`` (``chain_method`` con
``combine`` de diccionario, ver el docstring de
``src/addons/account_payment/models/account_payment_method.py``).

Portación de ``odoo19c: account_payment/models/account_payment_method.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``).
"""
import pytest

from addons.account.models import AccountPaymentMethod
from addons.account_payment.models.account_payment_method import (
    apply_account_payment_extensions as apply_account_payment_,
)
from addons.payment.models import PaymentGateway

pytestmark = pytest.mark.django_db

apply_account_payment_()


class TestGetPaymentMethodInformation:
    def test_base_manual_entry_survives_the_merge(self):
        # ≙ test_account_payment_methods_and_terms.py::
        #   test_get_payment_method_information — no debe romperse por la
        #   extensión encadenada de este addon.
        m = AccountPaymentMethod.objects.create(
            name='Manual', code='manual', payment_type='inbound')
        info = m._get_payment_method_information()
        assert info['manual']['mode'] == 'multi'
        assert info['manual']['type'] == ('bank', 'cash', 'credit')

    def test_every_gateway_marked_electronic(self):
        m = AccountPaymentMethod.objects.create(
            name='Manual 2', code='manual2', payment_type='inbound')
        info = m._get_payment_method_information()
        for gateway_code, _label in PaymentGateway.GATEWAYS:
            key = gateway_code.lower()
            assert info[key] == {'mode': 'electronic', 'type': ('bank',)}

    def test_mercadopago_and_paypal_present(self):
        m = AccountPaymentMethod.objects.create(
            name='Manual 3', code='manual3', payment_type='inbound')
        info = m._get_payment_method_information()
        assert 'mercadopago' in info
        assert 'paypal' in info
