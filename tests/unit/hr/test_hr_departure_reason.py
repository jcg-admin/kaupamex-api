"""``hr.departure.reason`` — motivo de baja de un empleado (addon ``hr``).

Adaptación fiel de Odoo hr/models/hr_departure_reason.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).
"""
import pytest

from addons.base.models import ResCompany, ResCountry
from addons.hr.data.hr_departure_reason_data import (
    seed as departure_reasons_seed,
)
from addons.hr.models import HrDepartureReason
from exceptions import UserError
from orm.environments import set_current_company

pytestmark = pytest.mark.django_db


@pytest.fixture
def mexico():
    return ResCountry.objects.get(code='MX')


@pytest.fixture
def company(mexico):
    company = ResCompany.objects.create(code='hr-departure', name='HR Departure')
    company.partner.country = mexico
    company.partner.save(update_fields=['country'])
    return company


class TestHrDepartureReasonDefaultCountry:
    """≙ ``default=lambda self: self.env.company.country_id``."""

    def test_default_country_is_the_active_company_country(self, company):
        set_current_company(company.pk)
        try:
            reason = HrDepartureReason.objects.create(name='Motivo propio')
        finally:
            set_current_company(None)
        assert reason.country_id == company.partner.country_id

    def test_without_an_active_company_country_stays_empty(self):
        set_current_company(None)
        reason = HrDepartureReason.objects.create(name='Motivo sin compañía')
        assert reason.country_id is None


class TestHrDepartureReasonCountryCode:
    """≙ ``related='country_id.code'``, expuesto como ``@property``."""

    def test_country_code_reads_through_country(self, mexico):
        reason = HrDepartureReason.objects.create(
            name='Con país', country=mexico)
        assert reason.country_code == mexico.code

    def test_country_code_is_empty_without_a_country(self):
        reason = HrDepartureReason.objects.create(name='Sin país')
        assert reason.country_code == ''


class TestHrDepartureReasonDefaultReasonsSeed:
    """``addons/hr/data/hr_departure_reason_data.py`` siembra los tres motivos
    maestros — ≙ los tres ``<record>`` de ``odoo19c: hr/data/hr_data.xml:56-73``.

    La migración ``0003`` los siembra una vez; el catálogo de ``conftest`` los
    repone tras cada flush. Los dos consumen la misma tabla.
    """

    def test_the_three_master_reasons_are_seeded(self):
        motivos = HrDepartureReason._get_default_departure_reasons()
        assert len(motivos) == 3
        assert {m.name for m in motivos} == {
            'Despedido', 'Renunció', 'Jubilado'}

    def test_a_master_reason_cannot_be_deleted(self):
        motivos = HrDepartureReason._get_default_departure_reasons()
        maestro = next(iter(motivos))
        with pytest.raises(UserError):
            maestro.delete()
        assert HrDepartureReason.objects.filter(pk=maestro.pk).exists()

    def test_a_non_master_reason_can_be_deleted(self):
        reason = HrDepartureReason.objects.create(name='Motivo temporal')
        reason.delete()
        assert not HrDepartureReason.objects.filter(pk=reason.pk).exists()

    def test_the_master_sequences_come_from_the_source(self):
        """0, 1, 2 — no el ``default=10`` del campo.

        La fuente los numera por debajo de cualquier motivo que un usuario
        añada después, y eso es lo que los mantiene arriba en el catálogo.
        """
        by_name = {m.name: m.sequence
                   for m in HrDepartureReason._get_default_departure_reasons()}
        assert by_name == {'Despedido': 0, 'Renunció': 1, 'Jubilado': 2}

    def test_the_master_reasons_carry_no_country(self, company):
        """≙ ``<field name="country_id" eval="False"/>`` de la fuente.

        El campo tiene ``default=_default_country``, así que re-sembrar con una
        compañía activa ataría los tres maestros a su país. La fuente lo anula
        a propósito: son universales.
        """
        set_current_company(company.pk)
        try:
            departure_reasons_seed()
        finally:
            set_current_company(None)

        motivos = HrDepartureReason._get_default_departure_reasons()
        assert len(motivos) == 3
        assert all(m.country_id is None for m in motivos)

    def test_seeding_twice_does_not_duplicate(self):
        """Idempotente por ``(module, name)`` de ``ir.model.data``."""
        antes = HrDepartureReason.objects.count()
        departure_reasons_seed()
        assert HrDepartureReason.objects.count() == antes
