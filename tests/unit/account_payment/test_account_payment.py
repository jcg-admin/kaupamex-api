"""Contrato de ``account_payment`` sobre ``account.payment`` — las 3
propiedades FK (``payment_transaction``/``payment_token``/
``source_payment``, vía ``AccountPaymentTransaction``, DEC-SALE-01) y los 2
cómputos de reembolso (``amount_available_for_refund``/``refunds_count``).

Portación de ``odoo19c: account_payment/models/account_payment.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``). Ver el docstring
de ``src/addons/account_payment/models/account_payment.py`` para la
cobertura medida y lo NO portado (``action_post``/``_create_payment_
transaction`` — bloqueados por ``payment.Payment.sale_order`` NOT NULL).

Requiere ``addons.account_payment`` en ``INSTALLED_APPS`` (fuera del
alcance de este porte) para que la migración cree sus 4 tablas RELATED —
mismo caveat que ``account_qr_code_sepa``/``account_debit_note``. Se llama
``apply_account_payment_extensions()`` explícitamente en cada módulo de
test, idempotente.
"""
from decimal import Decimal

import pytest

from addons.account.models import AccountJournal, AccountPayment
from addons.account_payment.models.account_payment import (
    apply_account_payment_extensions as apply_account_payment_,
)
from addons.account_payment.models.links import AccountPaymentTransaction
from addons.base.models import ResCompany, ResUsers
from addons.payment.models import Payment, Refund, SavedCard
from addons.sale.models import SaleOrder

pytestmark = pytest.mark.django_db

apply_account_payment_()


@pytest.fixture
def company():
    return ResCompany.objects.create(code='acme-ap', name='ACME AP')


@pytest.fixture
def journal(company):
    return AccountJournal.objects.create(
        name='Banco', code='BNKAP', type='bank', company=company)


@pytest.fixture
def payment(company, journal):
    return AccountPayment.objects.create(
        amount=Decimal('150.00'), payment_type='inbound',
        partner_type='customer', company=company, journal=journal,
    )


@pytest.fixture
def sale_order():
    return SaleOrder.objects.create()


@pytest.fixture
def transaction(sale_order):
    return Payment.objects.create(
        sale_order=sale_order, gateway=Payment.GATEWAY_MERCADOPAGO,
        amount=Decimal('150.00'), status=Payment.STATUS_APPROVED,
    )


class TestPaymentTransactionProperty:
    def test_default_is_none(self, payment):
        assert payment.payment_transaction is None

    def test_set_creates_link_and_persists(self, payment, transaction):
        payment.payment_transaction = transaction
        # Re-leído desde otra instancia — no del atributo en memoria.
        again = AccountPayment.objects.get(pk=payment.pk)
        # `.pk` y no `payment_transaction_id`: aquí `payment_transaction` es
        # una PROPIEDAD sobre la tabla satélite `AccountPaymentTransaction`,
        # no una FK de `AccountPayment`, así que Django no genera el gemelo
        # `_id`. El sufijo `_id` es la convención Many2one de la referencia,
        # que este árbol materializa como propiedad que devuelve el objeto.
        assert again.payment_transaction.pk == transaction.pk

    def test_reassign_updates_same_link_row(self, payment, transaction, sale_order):
        payment.payment_transaction = transaction
        second = Payment.objects.create(
            sale_order=sale_order, gateway=Payment.GATEWAY_PAYPAL,
            amount=Decimal('150.00'), status=Payment.STATUS_PENDING,
        )
        payment.payment_transaction = second
        assert AccountPayment.objects.get(pk=payment.pk).payment_transaction.pk == second.pk
        # Una sola fila de enlace, no dos — get_or_create reusa la existente.
        assert AccountPaymentTransaction.objects.filter(payment=payment).count() == 1


class TestPaymentTokenProperty:
    def test_default_is_none(self, payment):
        assert payment.payment_token is None

    def test_set_and_get(self, payment, company):
        user = ResUsers.objects.create_user(
            login='card@acme.mx', password='TestPass123!', name='Card Holder')
        card = SavedCard.objects.create(
            user=user, mp_card_id='card_1', mp_customer_id='cust_1',
            last_four_digits='4242', expiration_month=12, expiration_year=2030,
        )
        payment.payment_token = card
        assert AccountPayment.objects.get(pk=payment.pk).payment_token.pk == card.pk


class TestSourcePaymentProperty:
    def test_default_is_none(self, payment):
        assert payment.source_payment is None

    def test_set_marks_as_refund(self, payment, company, journal):
        refund_payment = AccountPayment.objects.create(
            amount=Decimal('50.00'), payment_type='outbound',
            partner_type='customer', company=company, journal=journal,
        )
        refund_payment.source_payment = payment
        assert refund_payment.source_payment.pk == payment.pk
        assert payment.refunds_count == 1


class TestAmountAvailableForRefund:
    def test_zero_without_transaction(self, payment):
        assert payment.amount_available_for_refund == Decimal('0.00')

    def test_full_amount_without_refunds(self, payment, transaction):
        payment.payment_transaction = transaction
        assert payment.amount_available_for_refund == transaction.amount

    def test_subtracts_approved_refunds_only(self, payment, transaction):
        payment.payment_transaction = transaction
        Refund.objects.create(
            payment=transaction, amount=Decimal('40.00'),
            status=Refund.STATUS_APPROVED,
        )
        Refund.objects.create(
            payment=transaction, amount=Decimal('1000.00'),
            status=Refund.STATUS_PENDING,  # no cuenta — no aprobado
        )
        assert payment.amount_available_for_refund == Decimal('110.00')


class TestRefundsCount:
    def test_zero_when_no_refund_declares_it_as_source(self, payment):
        assert payment.refunds_count == 0

    def test_counts_only_payments_declaring_this_source(
            self, payment, company, journal):
        AccountPayment.objects.create(
            amount=Decimal('10.00'), payment_type='outbound',
            partner_type='customer', company=company, journal=journal,
        )  # sin source_payment — no cuenta
        refund = AccountPayment.objects.create(
            amount=Decimal('10.00'), payment_type='outbound',
            partner_type='customer', company=company, journal=journal,
        )
        refund.source_payment = payment
        assert payment.refunds_count == 1


class TestGetPaymentRefundWizardValues:
    def test_shape(self, payment, transaction):
        payment.payment_transaction = transaction
        values = payment._get_payment_refund_wizard_values()
        assert values == {
            'transaction_id': transaction.pk,
            'payment_amount': payment.amount,
            'amount_available_for_refund': transaction.amount,
        }
