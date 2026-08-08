"""Contrato de ``account_payment`` sobre ``account.journal`` —
``_get_available_payment_method_lines`` (reconstruido, sin base que
extender — ver el docstring de ``src/addons/account_payment/models/
account_journal.py``) y el guard de borrado ``_unlink_except_linked_to_
payment_provider``.

Portación de ``odoo19c: account_payment/models/account_journal.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``).

**No estás solo en este modelo** (nota del orquestador): otro addon de la
misma tanda también extiende ``account.journal``. Estos tests sólo afirman
que LO DE ESTE addon está presente/funciona — nunca que es el único
contribuyente (``chain_method``/``_get_available_payment_method_lines`` no
se compara contra un conteo exacto de hooks instalados).
"""
import pytest
from django.db import transaction

from addons.account.models import (
    AccountJournal,
    AccountPaymentMethod,
    AccountPaymentMethodLine,
)
from addons.account_payment.models.account_journal import (
    apply_account_payment_extensions as apply_account_payment_,
)
from addons.account_payment.models.links import PaymentGatewayJournal
from addons.base.models import ResCompany
from addons.payment.models import PaymentGateway
from exceptions import UserError

pytestmark = pytest.mark.django_db

apply_account_payment_()


@pytest.fixture
def company():
    return ResCompany.objects.create(code='acme-aj', name='ACME AJ')


@pytest.fixture
def journal(company):
    return AccountJournal.objects.create(
        name='Banco', code='BNKAJ', type='bank', company=company)


@pytest.fixture
def inbound_method():
    return AccountPaymentMethod.objects.create(
        name='MercadoPago', code='mercadopago', payment_type='inbound')


class TestGetAvailablePaymentMethodLines:
    def test_returns_lines_of_matching_payment_type(self, journal, inbound_method):
        line = AccountPaymentMethodLine.objects.create(
            payment_method=inbound_method, journal=journal)
        result = journal._get_available_payment_method_lines('inbound')
        assert line in result

    def test_excludes_lines_of_other_payment_type(self, journal, inbound_method):
        outbound_method = AccountPaymentMethod.objects.create(
            name='Transferencia', code='transfer', payment_type='outbound')
        AccountPaymentMethodLine.objects.create(
            payment_method=outbound_method, journal=journal)
        result = journal._get_available_payment_method_lines('inbound')
        assert not result.filter(payment_method=outbound_method).exists()

    def test_excludes_line_of_inactive_provider(self, journal, inbound_method):
        line = AccountPaymentMethodLine.objects.create(
            payment_method=inbound_method, journal=journal)
        gateway = PaymentGateway.objects.create(
            gateway='PAYPAL', name='PayPal', is_active=False)
        PaymentGatewayJournal.objects.create(gateway=gateway, journal=journal)
        line.payment_provider = gateway
        result = journal._get_available_payment_method_lines('inbound')
        assert line not in result

    def test_keeps_line_of_active_provider(self, journal, inbound_method):
        line = AccountPaymentMethodLine.objects.create(
            payment_method=inbound_method, journal=journal)
        gateway = PaymentGateway.objects.create(
            gateway='MERCADOPAGO', name='MercadoPago', is_active=True)
        line.payment_provider = gateway
        result = journal._get_available_payment_method_lines('inbound')
        assert line in result


class TestUnlinkExceptLinkedToPaymentProvider:
    def test_delete_allowed_without_gateway(self, journal):
        pk = journal.pk
        journal.delete()
        assert not AccountJournal.objects.filter(pk=pk).exists()

    def test_delete_allowed_with_inactive_gateway(self, journal):
        gateway = PaymentGateway.objects.create(
            gateway='PAYPAL', name='PayPal', is_active=False)
        PaymentGatewayJournal.objects.create(gateway=gateway, journal=journal)
        pk = journal.pk
        journal.delete()
        assert not AccountJournal.objects.filter(pk=pk).exists()

    def test_delete_blocked_with_active_gateway(self, journal):
        gateway = PaymentGateway.objects.create(
            gateway='MERCADOPAGO', name='MercadoPago', is_active=True)
        PaymentGatewayJournal.objects.create(gateway=gateway, journal=journal)
        # `atomic()` interno por la misma razón que en
        # `test_account_payment_method_line.py`: el guard corre en `pre_delete`,
        # dentro del bloque atómico de `Collector.delete()`, y sin acotar el
        # rollback la consulta siguiente aborta con `TransactionManagementError`.
        with pytest.raises(UserError):
            with transaction.atomic():
                journal.delete()
        assert AccountJournal.objects.filter(pk=journal.pk).exists()
