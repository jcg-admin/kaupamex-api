"""``fiscal_year_search`` de ``AccountAnalyticLine`` — el atajo de filtro por
ejercicio fiscal vigente, sin columna propia.

≙ ``odoo19c: analytic/models/analytic_line.py:222-226`` (el campo) y
``:272-274`` (``_search_fiscal_date``). Desbloqueado por
``ResCompany.compute_fiscalyear_dates`` (tarea #207) — ver el docstring del
módulo ``analytic_line.py`` para el detalle de los dos mecanismos que este
campo necesitaba.
"""
import datetime
import inspect

import pytest
from dateutil.relativedelta import relativedelta

from orm.domains import Domain, to_q
from orm.environments import set_current_company
from orm.fields_nonstored import NonStored

from addons.analytic.models.analytic_line import AccountAnalyticLine
from addons.base.models.res_company import ResCompany


@pytest.fixture
def company(db):
    company_record = ResCompany.objects.create(
        name='Kaupamex analítica fiscal')
    company_record.fiscalyear_last_day = 31
    company_record.fiscalyear_last_month = '12'
    company_record.save(update_fields=[
        'fiscalyear_last_day', 'fiscalyear_last_month'])
    return company_record


class TestTheFieldIsANonStoredSearchOnly:
    """No es "campo virtual sólo de filtro de vista" — verificación de la
    forma exacta que ``porte-completo-no-parcial.md`` exige."""

    def test_it_is_a_non_stored_descriptor(self):
        descriptor = AccountAnalyticLine.__dict__.get('fiscal_year_search')
        # Puede colgar de un mixin/ancestro si el MRO cambia; se resuelve
        # igual que ``_field()`` de ``orm/domains.py``: por atributo estático.
        if descriptor is None:
            descriptor = inspect.getattr_static(
                AccountAnalyticLine, 'fiscal_year_search')
        assert isinstance(descriptor, NonStored)

    def test_it_declares_the_search_method_of_the_source(self):
        descriptor = inspect.getattr_static(
            AccountAnalyticLine, 'fiscal_year_search')
        assert descriptor.search == '_search_fiscal_date'

    def test_it_has_no_column(self):
        names = {f.name for f in AccountAnalyticLine._meta.get_fields()}
        assert 'fiscal_year_search' not in names


class TestSearchFiscalDateReturnsTheDomainOfTheSource:
    """≙ ``:272-274`` — verbatim: ni ``operator`` ni ``value`` cambian el
    resultado; el filtro es siempre desde un año antes del inicio del
    ejercicio vigente."""

    def test_with_no_active_company_it_does_not_restrict(self, db):
        """CONTROL de la divergencia de mecanismo (sesión, no registro): sin
        compañía activada no hay de dónde sacar el ejercicio, y el resultado
        es "verdadero" — no restringe — en vez de fallar."""
        set_current_company(None)
        assert AccountAnalyticLine._search_fiscal_date('=', True) == []

    def test_with_an_active_company_it_uses_its_fiscal_year(self, company):
        set_current_company(company.pk)
        try:
            domain = AccountAnalyticLine._search_fiscal_date('=', True)
        finally:
            set_current_company(None)
        fiscal_from = company.compute_fiscalyear_dates(
            datetime.date.today())['date_from']
        assert domain == [
            ('date', '>=', fiscal_from - relativedelta(years=1)),
        ]

    def test_the_operator_and_value_are_ignored_like_the_source(self, company):
        """El quirk verbatim de la fuente: cualquier operador da el mismo
        dominio — no es un recorte de este puerto."""
        set_current_company(company.pk)
        try:
            with_eq = AccountAnalyticLine._search_fiscal_date('=', True)
            with_neq = AccountAnalyticLine._search_fiscal_date('!=', False)
        finally:
            set_current_company(None)
        assert with_eq == with_neq


class TestSearchFiscalDateReachesTheDatabase:
    """El consumidor real: la condición se sustituye y compila a SQL."""

    def test_a_line_inside_the_window_is_found(self, company):
        set_current_company(company.pk)
        try:
            inside = AccountAnalyticLine.objects.create(
                name='dentro', company=company,
                date=datetime.date.today())
            found = AccountAnalyticLine.objects.filter(
                to_q(Domain('fiscal_year_search', '=', True),
                    AccountAnalyticLine))
            assert inside.pk in [line.pk for line in found]
        finally:
            set_current_company(None)

    def test_a_line_older_than_the_window_is_excluded(self, company):
        set_current_company(company.pk)
        try:
            fiscal_from = company.compute_fiscalyear_dates(
                datetime.date.today())['date_from']
            too_old = fiscal_from.replace(year=fiscal_from.year - 2)
            old_line = AccountAnalyticLine.objects.create(
                name='vieja', company=company, date=too_old)
            found = AccountAnalyticLine.objects.filter(
                to_q(Domain('fiscal_year_search', '=', True),
                    AccountAnalyticLine))
            assert old_line.pk not in [line.pk for line in found]
        finally:
            set_current_company(None)
