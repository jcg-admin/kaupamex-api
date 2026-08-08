"""Contrato de ``account_payment`` sobre ``account.payment.method.line`` —
la propiedad ``payment_provider`` (DEC-SALE-01, vía
``AccountPaymentMethodLineProvider``), ``payment_provider_state``, el
override captura-y-llama de ``_compute_name``, y el guard de borrado
``_unlink_except_active_provider``.

Portación de ``odoo19c: account_payment/models/
account_payment_method_line.py`` (``odoo-tools@622ddc2aa5563d12295b4ab7d
3eb438a43eb31de``). Ver el docstring de ``src/addons/account_payment/
models/account_payment_method_line.py`` para la divergencia de
``payment_provider_state`` (sin el valor intermedio ``'test'``).
"""
import pytest
from django.db import transaction

from addons.account.models import (
    AccountJournal,
    AccountPaymentMethod,
    AccountPaymentMethodLine,
)
from addons.account_payment.models.account_payment_method_line import (
    apply_account_payment_extensions as apply_account_payment_,
)
from addons.base.models import ResCompany
from addons.payment.models import PaymentGateway
from exceptions import UserError

pytestmark = pytest.mark.django_db

apply_account_payment_()


@pytest.fixture
def company():
    return ResCompany.objects.create(code='acme-apml', name='ACME APML')


@pytest.fixture
def journal(company):
    return AccountJournal.objects.create(
        name='Banco', code='BNKML', type='bank', company=company)


@pytest.fixture
def method():
    return AccountPaymentMethod.objects.create(
        name='MercadoPago', code='mercadopago', payment_type='inbound')


@pytest.fixture
def line(method, journal):
    return AccountPaymentMethodLine.objects.create(
        payment_method=method, journal=journal)


@pytest.fixture
def gateway():
    return PaymentGateway.objects.create(
        gateway='MERCADOPAGO', name='MercadoPago', is_active=True)


class TestPaymentProviderProperty:
    def test_default_is_none(self, line):
        assert line.payment_provider is None

    def test_set_persists(self, line, gateway):
        line.payment_provider = gateway
        again = AccountPaymentMethodLine.objects.get(pk=line.pk)
        # `.pk` y no `payment_provider_id`: `payment_provider` es una
        # PROPIEDAD sobre la tabla satélite `AccountPaymentMethodLineProvider`,
        # no una FK de la línea, así que Django no genera el gemelo `_id`.
        assert again.payment_provider.pk == gateway.pk


class TestPaymentProviderState:
    def test_none_without_provider(self, line):
        assert line.payment_provider_state is None

    def test_enabled_when_active(self, line, gateway):
        line.payment_provider = gateway
        assert line.payment_provider_state == 'enabled'

    def test_disabled_when_inactive(self, line):
        inactive = PaymentGateway.objects.create(
            gateway='PAYPAL', name='PayPal', is_active=False)
        line.payment_provider = inactive
        assert line.payment_provider_state == 'disabled'


class TestComputeNameOverride:
    def test_base_still_fills_from_method_name(self, method, journal):
        # ≙ test_account_payment_methods_and_terms.py::
        #   test_name_defaults_to_method_name — la base sigue corriendo.
        line = AccountPaymentMethodLine.objects.create(
            payment_method=method, journal=journal)
        assert line.name == method.name

    def test_provider_name_used_when_base_leaves_it_empty(self, journal, gateway):
        # payment_method sin name (cadena vacía) — la base no puede llenar
        # ``name``, así que la extensión de este addon sí.
        method_sin_name = AccountPaymentMethod.objects.create(
            name='', code='sin-nombre', payment_type='inbound')
        line = AccountPaymentMethodLine.objects.create(
            payment_method=method_sin_name, journal=journal)
        assert line.name == ''
        line.payment_provider = gateway
        line.save()  # vuelve a correr _compute_name, ya con el enlace creado
        assert line.name == gateway.name

    def test_explicit_name_not_overridden(self, method, journal, gateway):
        line = AccountPaymentMethodLine.objects.create(
            payment_method=method, journal=journal, name='Nombre explícito')
        line.payment_provider = gateway
        line.save()
        assert line.name == 'Nombre explícito'


class TestUnlinkExceptActiveProvider:
    def test_delete_allowed_without_provider(self, line):
        pk = line.pk
        line.delete()
        assert not AccountPaymentMethodLine.objects.filter(pk=pk).exists()

    def test_delete_allowed_with_inactive_provider(self, line):
        inactive = PaymentGateway.objects.create(
            gateway='PAYPAL', name='PayPal', is_active=False)
        line.payment_provider = inactive
        pk = line.pk
        line.delete()
        assert not AccountPaymentMethodLine.objects.filter(pk=pk).exists()

    def test_delete_blocked_with_active_provider(self, line, gateway):
        line.payment_provider = gateway
        # El `atomic()` interno acota el rollback: el guard corre en
        # `pre_delete`, DENTRO del bloque atómico que abre `Collector.delete()`,
        # así que al propagar la excepción Django marca la transacción para
        # rollback. Sin acotarla, el `filter(...).exists()` de abajo aborta con
        # `TransactionManagementError` en vez de comprobar lo que interesa.
        # Es el patrón que la doc de Django exige al esperar una excepción
        # dentro de un bloque atómico — no un parche del guard, que hace justo
        # lo que debe (≙ `@api.ondelete` de la referencia).
        with pytest.raises(UserError):
            with transaction.atomic():
                line.delete()
        assert AccountPaymentMethodLine.objects.filter(pk=line.pk).exists()
