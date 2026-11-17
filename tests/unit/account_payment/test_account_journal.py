"""Contrato de ``account_payment`` sobre ``account.journal`` —
``_get_available_payment_method_lines`` (encadenado sobre la base de
``account``) y el guard de borrado ``_unlink_except_linked_to_
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
from orm.environments import env, sudo

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser():
    """Los datos se escriben como superusuario, como en las pruebas de la
    fuente: con ``account.journal`` sobre ``BaseModel`` la ACL aplica."""
    with sudo():
        yield


apply_account_payment_()


@pytest.fixture
def company():
    return ResCompany.objects.create(code='acme-aj', name='ACME AJ')


@pytest.fixture
def journal(company):
    """Diario ya volcado: sus líneas por defecto están calculadas, como en
    una preparación de la fuente que ya pasó por ``flush``. Si el cómputo
    quedara pendiente, su ``Command.clear()`` desligaría las líneas que la
    prueba añade después."""
    journal = AccountJournal.create({'name': 'Banco', 'code': 'BNKAJ',
                                     'type': 'bank', 'company_id': company.pk})
    env().flush_all()
    return journal


@pytest.fixture
def inbound_method():
    return AccountPaymentMethod.objects.create(
        name='MercadoPago', code='mercadopago', payment_type='inbound'
    )


class TestGetAvailablePaymentMethodLines:
    def test_returns_lines_of_matching_payment_type(
        self, journal, inbound_method
    ):
        line = AccountPaymentMethodLine.create({
            'payment_method_id': inbound_method.pk, 'journal_id': journal.pk,
        })
        result = journal._get_available_payment_method_lines('inbound')
        assert line in result

    def test_excludes_lines_of_other_payment_type(
        self, journal, inbound_method
    ):
        outbound_method = AccountPaymentMethod.objects.create(
            name='Transferencia', code='transfer', payment_type='outbound'
        )
        AccountPaymentMethodLine.create({
            'payment_method_id': outbound_method.pk, 'journal_id': journal.pk,
        })
        result = journal._get_available_payment_method_lines('inbound')
        assert not result.filtered(
            lambda line: line.payment_method_id == outbound_method.pk)

    def test_excludes_line_of_inactive_provider(self, journal, inbound_method):
        line = AccountPaymentMethodLine.create({
            'payment_method_id': inbound_method.pk, 'journal_id': journal.pk,
        })
        gateway = PaymentGateway.objects.create(
            gateway='PAYPAL', name='PayPal', is_active=False
        )
        PaymentGatewayJournal.objects.create(gateway=gateway, journal=journal)
        line.payment_provider = gateway
        result = journal._get_available_payment_method_lines('inbound')
        assert line not in result

    def test_keeps_line_of_active_provider(self, journal, inbound_method):
        line = AccountPaymentMethodLine.create({
            'payment_method_id': inbound_method.pk, 'journal_id': journal.pk,
        })
        gateway = PaymentGateway.objects.create(
            gateway='MERCADOPAGO', name='MercadoPago', is_active=True
        )
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
            gateway='PAYPAL', name='PayPal', is_active=False
        )
        PaymentGatewayJournal.objects.create(gateway=gateway, journal=journal)
        pk = journal.pk
        journal.delete()
        assert not AccountJournal.objects.filter(pk=pk).exists()

    def test_delete_blocked_with_active_gateway(self, journal):
        gateway = PaymentGateway.objects.create(
            gateway='MERCADOPAGO', name='MercadoPago', is_active=True
        )
        PaymentGatewayJournal.objects.create(gateway=gateway, journal=journal)
        # `atomic()` interno por la misma razón que en
        # `test_account_payment_method_line.py`: el guard corre en
        # `pre_delete`,
        # dentro del bloque atómico de `Collector.delete()`, y sin acotar el
        # rollback la consulta siguiente aborta con
        # `TransactionManagementError`.
        with pytest.raises(UserError):
            with transaction.atomic():
                journal.delete()
        assert AccountJournal.objects.filter(pk=journal.pk).exists()
