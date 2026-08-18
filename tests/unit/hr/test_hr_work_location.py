"""``hr.work.location`` — sede física de trabajo (addon ``hr``).

Adaptación fiel de Odoo hr/models/hr_work_location.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).
"""
import pytest

from addons.hr.models import HrWorkLocation

pytestmark = pytest.mark.django_db


class TestHrWorkLocationDefaults:

    def test_active_defaults_to_true(self):
        location = HrWorkLocation.objects.create(name='Oficina CDMX')
        assert location.active is True

    def test_location_type_defaults_to_office(self):
        location = HrWorkLocation.objects.create(name='Oficina CDMX')
        assert location.location_type == HrWorkLocation.LocationType.OFFICE

    def test_company_and_address_are_optional(self):
        """≙ D-2: opcional + SET_NULL (misma divergencia que company/job)."""
        location = HrWorkLocation.objects.create(name='Remoto')
        assert location.company_id is None
        assert location.address_id is None


class TestHrWorkLocationChoices:

    def test_location_type_accepts_home(self):
        location = HrWorkLocation.objects.create(
            name='Casa de Ana', location_type=HrWorkLocation.LocationType.HOME)
        assert location.location_type == 'home'


class TestHrWorkLocationStr:

    def test_str_returns_name(self):
        location = HrWorkLocation.objects.create(name='Oficina CDMX')
        assert str(location) == 'Oficina CDMX'
