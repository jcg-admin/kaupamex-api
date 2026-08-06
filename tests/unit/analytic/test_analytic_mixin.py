"""Contrato de ``AnalyticMixin`` (Python puro, sin las partes SQL de
Postgres que no se portan — ver el docstring de
``src/addons/analytic/models/analytic_mixin.py``).

``_get_analytic_account_ids_from_distributions`` y
``_modifiying_distribution_values``/``_merge_distribution`` que NO
consultan ``AccountAnalyticAccount`` (listas vacías) se ejercen sin BD.
``_sanitize_distribution`` consulta ``DecimalPrecision`` (tabla de ``base``,
ya migrada) — ver el docstring de ``test_analytic_line.py``.
"""
import pytest

from addons.analytic.models import AccountAnalyticDistributionModel, AnalyticMixin


class TestAccountIdsFromDistributions:
    """Fiel a ``_get_analytic_account_ids_from_distributions`` (odoo19c:
    analytic_mixin.py líneas 48-56)."""

    def test_empty_input_returns_empty_set(self):
        assert AnalyticMixin._get_analytic_account_ids_from_distributions(None) == set()
        assert AnalyticMixin._get_analytic_account_ids_from_distributions({}) == set()

    def test_single_distribution_dict(self):
        result = AnalyticMixin._get_analytic_account_ids_from_distributions(
            {'3,5': 60, '7': 40},
        )
        assert result == {3, 5, 7}

    def test_list_of_distributions(self):
        result = AnalyticMixin._get_analytic_account_ids_from_distributions(
            [{'3': 100}, {'5,6': 100}],
        )
        assert result == {3, 5, 6}


class TestMergeDistributionWithoutUpdateKey:
    """``__update__`` ausente -> reemplaza todo (odoo19c: línea 245-246)."""

    def test_returns_new_distribution_verbatim(self):
        new = {'3': 60, '5': 40}
        assert AnalyticMixin._merge_distribution({'1': 100}, new) is new


@pytest.mark.django_db
class TestSanitizeDistribution:
    """``_sanitize_distribution`` (odoo19c: ``_sanitize_values``, líneas
    198-205) — redondea los porcentajes, preserva ``__update__``."""

    def test_rounds_percentages_to_configured_precision(self):
        model = AccountAnalyticDistributionModel()
        model.analytic_distribution = {'3': 33.333333, '5': 66.666667}
        model._sanitize_distribution()
        # Sin fila ``DecimalPrecision`` para "Percentage Analytic" en la QA
        # de este corte, cae al default de 2 dígitos (mismo fallback que
        # ``AccountAnalyticLine.analytic_precision``).
        assert model.analytic_distribution == {'3': 33.33, '5': 66.67}

    def test_preserves_update_marker_unrounded(self):
        model = AccountAnalyticDistributionModel()
        model.analytic_distribution = {'3': 50.005, '__update__': [1, 2]}
        model._sanitize_distribution()
        assert model.analytic_distribution['__update__'] == [1, 2]

    def test_empty_distribution_is_a_noop(self):
        model = AccountAnalyticDistributionModel()
        model.analytic_distribution = {}
        model._sanitize_distribution()  # no debe lanzar
        assert model.analytic_distribution == {}
