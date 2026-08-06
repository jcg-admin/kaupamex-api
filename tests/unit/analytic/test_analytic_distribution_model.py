"""Contrato de ``AccountAnalyticDistributionModel`` — construcción de
dominio (Python puro, sin BD). Ver el docstring de ``test_analytic_plan.py``
para por qué no se usa ``pytest.mark.django_db`` aquí: ``_get_applicable_models``
ejecuta un ``QuerySet.filter`` real y necesitaría la tabla del addon
(inexistente en este corte); se cubre sólo la construcción del ``Q``
(``_create_domain``) y el diccionario default, que son puro Python.
"""
from django.db.models import Q

from addons.analytic.models import AccountAnalyticDistributionModel


class TestDefaultSearchDomainVals:
    """Fiel a ``_get_default_search_domain_vals`` (odoo19c: líneas 78-84),
    sin ``partner_category_id`` (ver docstring del módulo: no hay modelo
    ``res.partner.category`` portado)."""

    def test_no_partner_category_key(self):
        vals = AccountAnalyticDistributionModel._get_default_search_domain_vals()
        assert vals == {'company_id': None, 'partner_id': None}
        assert 'partner_category_id' not in vals


class TestCreateDomain:
    """Fiel a ``_create_domain`` (odoo19c: líneas 94-99), adaptado a ``Q``
    de Django — ver el docstring del módulo para por qué NO es una
    traducción literal de ``[(fname, 'in', [value, False])]``."""

    def test_with_a_value_matches_value_or_unset(self):
        q = AccountAnalyticDistributionModel._create_domain('company_id', 7)
        assert q == (Q(company_id=7) | Q(company_id__isnull=True))

    def test_with_none_matches_only_unset(self):
        q = AccountAnalyticDistributionModel._create_domain('partner_id', None)
        assert q == Q(partner_id__isnull=True)
