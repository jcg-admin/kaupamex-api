"""Contrato de ``account_payment`` sobre ``payment.provider`` (≙
``PaymentGateway`` aquí) — la propiedad ``journal`` (DEC-SALE-01, vía
``PaymentGatewayJournal``, asignación directa sin cómputo — ver el
docstring de ``src/addons/account_payment/models/payment_provider.py``) y
``_get_provider_payment_method``.

Portación de ``odoo19c: account_payment/models/payment_provider.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``).
"""
import pytest

from addons.account.models import AccountJournal, AccountPaymentMethod
from addons.account_payment.models.payment_provider import (
    apply_account_payment_extensions as apply_account_payment_,
)
from addons.base.models import ResCompany
from addons.payment.models import PaymentGateway

pytestmark = pytest.mark.django_db

apply_account_payment_()


@pytest.fixture
def company():
    return ResCompany.objects.create(code='acme-pp', name='ACME PP')


@pytest.fixture
def journal(company):
    return AccountJournal.objects.create(
        name='Banco', code='BNKPP', type='bank', company=company)


@pytest.fixture
def gateway():
    return PaymentGateway.objects.create(
        gateway='MERCADOPAGO', name='MercadoPago', is_active=True)


class TestJournalProperty:
    def test_default_is_none(self, gateway):
        assert gateway.journal is None

    def test_set_persists(self, gateway, journal):
        gateway.journal = journal
        again = PaymentGateway.objects.get(pk=gateway.pk)
        assert again.journal.pk == journal.pk

    def test_two_gateways_can_share_a_journal(self, gateway, journal):
        other = PaymentGateway.objects.create(
            gateway='PAYPAL', name='PayPal', is_active=True)
        gateway.journal = journal
        other.journal = journal
        assert gateway.journal.pk == journal.pk
        assert other.journal.pk == journal.pk


class TestGetProviderPaymentMethod:
    def test_returns_none_when_absent(self, gateway):
        assert gateway._get_provider_payment_method('mercadopago') is None

    def test_returns_the_matching_method(self, gateway):
        method = AccountPaymentMethod.objects.create(
            name='MercadoPago', code='mercadopago', payment_type='inbound')
        found = gateway._get_provider_payment_method('mercadopago')
        assert found.pk == method.pk

    def test_callable_as_classmethod_too(self):
        # ≙ odoo19c @api.model — se llama sin instancia en la referencia.
        method = AccountPaymentMethod.objects.create(
            name='PayPal', code='paypal', payment_type='inbound')
        found = PaymentGateway._get_provider_payment_method('paypal')
        assert found.pk == method.pk
