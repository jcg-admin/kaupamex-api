"""El guard de redondeo de divisa que ``account`` cuelga (T-B2a).

``rounding`` no es cosmético: es el factor con el que ya se redondearon
importes asentados. Bajarlo a posteriori haría que la misma fila se leyera
con otro valor que el que se contabilizó — por eso la referencia lo bloquea
(``odoo19c: account/models/res_currency.py:27-32``).

La contraprueba del final es tan importante como el bloqueo: sin ella, un
guard que rechazara **siempre** pasaría este archivo igual.
"""
from decimal import Decimal

import pytest
from django.utils import timezone

from addons.account.models import (
    AccountAccount,
    AccountJournal,
    AccountMove,
    AccountMoveLine,
)
from addons.base.models import ResCompany, ResCurrency
from exceptions import UserError

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def company():
    return ResCompany.objects.create(code='acme', name='ACME')


@pytest.fixture
def divisa():
    return ResCurrency.objects.create(
        name='MXN', full_name='Peso mexicano', symbol='$',
        rounding=Decimal('0.01'), decimal_places=2)


def _apunte_en(divisa, company):
    """Un apunte real que usa esa divisa — el hecho que el guard consulta."""
    journal = AccountJournal.objects.create(
        name='Ventas', code='VEN', type='sale', company=company)
    cuenta = AccountAccount.objects.create(
        code='105', name='Clientes', account_type='asset_receivable',
        company=company)
    move = AccountMove.objects.create(
        move_type='out_invoice', date=timezone.now().date(),
        journal=journal, company=company)
    return AccountMoveLine.objects.create(
        move=move, account=cuenta, debit=Decimal('100.00'), currency=divisa)


class TestGuardDeRedondeo:
    def test_sin_apuntes_el_cambio_pasa(self, divisa):
        """Una divisa recién creada puede cambiar su precisión libremente."""
        divisa.assert_rounding_can_change(Decimal('0.1'))   # no lanza

    def test_con_apuntes_no_se_puede_reducir_la_precision(self, divisa, company):
        _apunte_en(divisa, company)

        with pytest.raises(UserError):
            divisa.assert_rounding_can_change(Decimal('0.1'))

    def test_con_apuntes_tampoco_se_admite_cero(self, divisa, company):
        """La referencia trata el 0 como caso especial, no como "más preciso"."""
        _apunte_en(divisa, company)

        with pytest.raises(UserError):
            divisa.assert_rounding_can_change(Decimal('0'))

    def test_con_apuntes_AUMENTAR_la_precision_sigue_permitido(
            self, divisa, company):
        """La contraprueba: el guard no rechaza todo cambio, sólo el destructivo.

        Pasar de 0.01 a 0.001 añade decimales — ningún importe ya asentado se
        vuelve irrepresentable. Sin este test, un guard que lanzara siempre
        pasaría los tres de arriba.
        """
        _apunte_en(divisa, company)

        divisa.assert_rounding_can_change(Decimal('0.001'))  # no lanza

    def test_el_guard_ve_los_apuntes_de_su_divisa_y_no_los_de_otra(
            self, divisa, company):
        otra = ResCurrency.objects.create(
            name='USD', full_name='Dólar', symbol='$',
            rounding=Decimal('0.01'), decimal_places=2)
        _apunte_en(otra, company)

        assert otra._has_accounting_entries() is True
        assert divisa._has_accounting_entries() is False
