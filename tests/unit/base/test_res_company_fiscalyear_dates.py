"""``compute_fiscalyear_dates`` de ``ResCompany`` — el rango del ejercicio
fiscal que contiene una fecha dada.

≙ ``odoo19c: account/models/company.py:1114-1122``, delegado en
``tools.date_utils.get_fiscal_year`` (mismo algoritmo que la fuente porta en
``odoo/tools/date_utils.py``). Sitio divergente declarado en el docstring de
``src/addons/base/models/res_company.py`` (tarea #207): la referencia pone
estos dos campos y este método en la extensión ``account`` de ``res.company``;
aquí van directos en la clase base por el alcance de la tarea.

Cubre también ``_check_fiscalyear_last_day`` (≙ ``odoo19c: :330-343``), el
guard explícito que valida los dos campos que alimentan el método, y
``_ROOT_DELEGATED_FIELDS`` (≙ ``_get_company_root_delegated_field_names``,
``odoo19c: :311-316``), que hace que una sucursal herede el cierre de su
matriz.
"""
import datetime

import pytest

from exceptions import ValidationError
from tools import date_utils

from addons.base.models.res_company import ResCompany


@pytest.fixture
def company(db):
    return ResCompany.objects.create(name='Kaupamex ejercicio fiscal')


class TestComputeFiscalyearDatesCalendarYear:
    """Cierre por omisión de la fuente: 31 de diciembre (≙ ``:74-75``)."""

    def test_a_date_in_the_middle_of_the_year_maps_to_the_calendar_year(
            self, company):
        result = company.compute_fiscalyear_dates(datetime.date(2026, 6, 15))
        assert result == {
            'date_from': datetime.date(2026, 1, 1),
            'date_to': datetime.date(2026, 12, 31),
        }

    def test_the_closing_day_itself_belongs_to_that_year(self, company):
        """Discrimina un corte ``<`` de uno ``<=``: si fuera estricto, el 31
        de diciembre caería al ejercicio SIGUIENTE en vez del que cierra."""
        result = company.compute_fiscalyear_dates(datetime.date(2026, 12, 31))
        assert result == {
            'date_from': datetime.date(2026, 1, 1),
            'date_to': datetime.date(2026, 12, 31),
        }

    def test_the_day_after_closing_belongs_to_the_next_year(self, company):
        result = company.compute_fiscalyear_dates(datetime.date(2027, 1, 1))
        assert result == {
            'date_from': datetime.date(2027, 1, 1),
            'date_to': datetime.date(2027, 12, 31),
        }

    def test_the_return_type_matches_the_source_keys(self, company):
        result = company.compute_fiscalyear_dates(datetime.date(2026, 1, 1))
        assert set(result) == {'date_from', 'date_to'}


class TestComputeFiscalyearDatesStaggeredClose:
    """Cierre desfasado — el ejercicio cruza diciembre y vive en dos años
    calendario, que es el caso que ``get_fiscal_year`` distingue del
    calendario natural."""

    @pytest.fixture
    def staggered_company(self, db):
        company = ResCompany.objects.create(name='Kaupamex cierre junio')
        company.fiscalyear_last_day = 30
        company.fiscalyear_last_month = '6'
        company.save(update_fields=[
            'fiscalyear_last_day', 'fiscalyear_last_month'])
        return company

    def test_before_the_close_the_year_started_the_previous_calendar_year(
            self, staggered_company):
        result = staggered_company.compute_fiscalyear_dates(
            datetime.date(2026, 5, 1))
        assert result == {
            'date_from': datetime.date(2025, 7, 1),
            'date_to': datetime.date(2026, 6, 30),
        }

    def test_after_the_close_the_year_closes_the_next_calendar_year(
            self, staggered_company):
        result = staggered_company.compute_fiscalyear_dates(
            datetime.date(2026, 7, 1))
        assert result == {
            'date_from': datetime.date(2026, 7, 1),
            'date_to': datetime.date(2027, 6, 30),
        }


class TestComputeFiscalyearDatesDelegatesToDateUtils:
    """CONTROL que puede fallar: si el método no delegara de verdad en
    ``date_utils.get_fiscal_year`` con el día/mes de LA COMPAÑÍA, cambiar
    esos dos campos no cambiaría el resultado — el mismo defecto que
    ``metrica-decide-la-conclusion.md`` (sub-patrón D) exige poder detectar."""

    def test_changing_the_company_fields_changes_the_result(self, company):
        default = company.compute_fiscalyear_dates(datetime.date(2026, 6, 15))
        company.fiscalyear_last_day = 31
        company.fiscalyear_last_month = '3'
        company.save(update_fields=[
            'fiscalyear_last_day', 'fiscalyear_last_month'])
        changed = company.compute_fiscalyear_dates(datetime.date(2026, 6, 15))
        assert changed != default
        assert changed == {
            'date_from': datetime.date(2026, 4, 1),
            'date_to': datetime.date(2027, 3, 31),
        }

    def test_it_is_the_same_algorithm_as_date_utils_get_fiscal_year(
            self, company):
        expected_from, expected_to = date_utils.get_fiscal_year(
            datetime.date(2026, 6, 15), day=company.fiscalyear_last_day,
            month=int(company.fiscalyear_last_month))
        result = company.compute_fiscalyear_dates(datetime.date(2026, 6, 15))
        assert result == {'date_from': expected_from, 'date_to': expected_to}


class TestCheckFiscalyearLastDay:
    """``_check_fiscalyear_last_day`` — guard explícito, no auto-hooked a
    ``save()`` (mismo patrón que ``validate_hard_lock_date_change``)."""

    def test_a_valid_day_for_the_month_does_not_raise(self, company):
        company.fiscalyear_last_day = 30
        company.fiscalyear_last_month = '4'   # abril tiene 30 días
        company._check_fiscalyear_last_day()

    def test_a_day_that_does_not_exist_in_the_month_raises(self, company):
        company.fiscalyear_last_day = 31
        company.fiscalyear_last_month = '4'   # abril NO tiene 31
        with pytest.raises(ValidationError):
            company._check_fiscalyear_last_day()

    def test_february_29_is_always_accepted(self, company):
        """Verbatim de la fuente: sin ``fiscalyear_last_year`` no se sabe si
        el usuario pensaba en un año bisiesto, así que se acepta siempre."""
        company.fiscalyear_last_day = 29
        company.fiscalyear_last_month = '2'
        company._check_fiscalyear_last_day()

    def test_a_zero_or_negative_day_raises(self, company):
        company.fiscalyear_last_day = 0
        company.fiscalyear_last_month = '5'
        with pytest.raises(ValidationError):
            company._check_fiscalyear_last_day()

    def test_control_without_calling_the_guard_the_bad_value_survives(
            self, company):
        """CONTROL — el guard NO está enganchado a ``save()`` (a propósito):
        sin llamarlo explícitamente, un día imposible (31 de abril) se
        persiste sin lanzar nada. Es lo que discrimina "el guard existe y
        protege cuando se invoca" de "no hay nada que chequear en absoluto".
        """
        company.fiscalyear_last_day = 31
        company.fiscalyear_last_month = '4'
        company.save(update_fields=[
            'fiscalyear_last_day', 'fiscalyear_last_month'])
        reloaded = ResCompany.objects.get(pk=company.pk)
        assert reloaded.fiscalyear_last_day == 31
        with pytest.raises(ValidationError):
            reloaded._check_fiscalyear_last_day()


class TestRootDelegation:
    """``_ROOT_DELEGATED_FIELDS`` — ≙ ``_get_company_root_delegated_field_
    names`` (``odoo19c: :311-316``): una sucursal no fija su propio cierre,
    hereda el de su matriz."""

    def test_the_two_fields_are_in_the_delegated_set(self):
        delegated = ResCompany.get_company_root_delegated_field_names()
        assert 'fiscalyear_last_day' in delegated
        assert 'fiscalyear_last_month' in delegated

    def test_a_branch_copies_the_root_fiscal_year_close(self, db):
        root = ResCompany.objects.create(name='Matriz')
        root.fiscalyear_last_day = 30
        root.fiscalyear_last_month = '9'
        root.save(update_fields=[
            'fiscalyear_last_day', 'fiscalyear_last_month'])
        branch = ResCompany.objects.create(name='Sucursal', parent=root)
        # Antes de la delegación, la sucursal trae el default de la fuente.
        assert branch.fiscalyear_last_day == 31
        branch.apply_root_delegation()
        assert branch.fiscalyear_last_day == 30
        assert branch.fiscalyear_last_month == '9'
