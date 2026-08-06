"""Contrato de ``AnalyticPlanFieldsMixin`` / ``AccountAnalyticLine``.

Ver el docstring de ``test_analytic_plan.py`` para por qué la mayoría de
estos tests NO usan ``pytest.mark.django_db``. La excepción es
``TestAnalyticPrecision``: ``analytic_precision`` consulta
``addons.base.models.DecimalPrecision``, que SÍ tiene tabla migrada (``base``
es un addon instalado desde el arranque del proyecto) — no toca ninguna
tabla de ``analytic``, así que es segura contra la BD real de QA.
"""
import pytest
from django.core.exceptions import ValidationError

from addons.analytic.models import AccountAnalyticAccount, AccountAnalyticLine, AccountAnalyticPlan


def _account(pk=1, name='Cuenta', plan_name='Plan'):
    plan = AccountAnalyticPlan(pk=pk, name=plan_name)
    return AccountAnalyticAccount(pk=pk, name=name, plan=plan)


class TestAccountRequired:
    """Fiel a ``_check_account_id`` (odoo19c: analytic_line.py líneas
    93-98), reducido a un único campo (ver docstring de
    ``models/analytic_line.py``)."""

    def test_clean_rejects_missing_account(self):
        line = AccountAnalyticLine(name='Gasto', amount=100, company_id=1)
        with pytest.raises(ValidationError) as exc:
            line.clean()
        assert exc.value.message_dict['account'] == ['ANALYTIC_LINE_ACCOUNT_REQUIRED']

    def test_clean_passes_with_account_set(self):
        line = AccountAnalyticLine(
            name='Gasto', amount=100, company_id=1, account=_account(),
        )
        line.clean()  # no debe lanzar


class TestDistributionHelpers:
    """``_get_distribution_key``/``_get_analytic_distribution`` (odoo19c:
    líneas 68-73)."""

    def test_distribution_key_is_account_pk_as_string(self):
        line = AccountAnalyticLine(name='Gasto', account=_account(pk=42))
        assert line._get_distribution_key() == '42'

    def test_distribution_key_empty_without_account(self):
        line = AccountAnalyticLine(name='Gasto')
        assert line._get_distribution_key() == ''

    def test_analytic_distribution_maps_account_to_100_percent(self):
        line = AccountAnalyticLine(name='Gasto', account=_account(pk=42))
        assert line._get_analytic_distribution() == {'42': 100}

    def test_analytic_distribution_empty_without_account(self):
        line = AccountAnalyticLine(name='Gasto')
        assert line._get_analytic_distribution() == {}


@pytest.mark.django_db
class TestAnalyticPrecision:
    """``analytic_precision`` — ``store=False`` en la referencia; aquí
    ``@property`` que consulta ``DecimalPrecision`` (mismo patrón que
    ``Uom._precision_digits``)."""

    def test_defaults_to_two_digits_when_no_row_configured(self):
        line = AccountAnalyticLine(name='Gasto', account=_account())
        assert line.analytic_precision == 2
