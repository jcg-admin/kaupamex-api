"""Catálogo de flota: ``fleet.service.type`` / ``model.category`` / ``model.
brand`` / ``vehicle.tag`` / ``vehicle.state`` (addon ``fleet``, cierre parcial).

Adaptación fiel de Odoo ``fleet`` (odoo-tools@622ddc2a, odoo19c:, LGPL-3).
"""
import pytest

from addons.fleet.models import (
    FleetServiceType,
    FleetVehicleModel,
    FleetVehicleModelBrand,
    FleetVehicleModelCategory,
    FleetVehicleState,
    FleetVehicleTag,
)

pytestmark = pytest.mark.django_db


class TestFleetServiceType:
    def test_create_and_str(self):
        stype = FleetServiceType.objects.create(
            name='Cambio de aceite', category=FleetServiceType.CATEGORY_SERVICE,
        )
        assert str(stype) == 'Cambio de aceite'
        assert stype.category == 'service'

    def test_category_choices_cover_contract_and_service(self):
        assert FleetServiceType.CATEGORY_CONTRACT == 'contract'
        assert FleetServiceType.CATEGORY_SERVICE == 'service'


class TestFleetVehicleModelCategory:
    def test_name_is_unique(self):
        FleetVehicleModelCategory.objects.create(name='Sedán')
        with pytest.raises(Exception):
            FleetVehicleModelCategory.objects.create(name='Sedán')

    def test_ordering_by_sequence(self):
        FleetVehicleModelCategory.objects.create(name='Pickup', sequence=2)
        FleetVehicleModelCategory.objects.create(name='SUV', sequence=1)
        names = list(
            FleetVehicleModelCategory.objects.filter(
                name__in=['Pickup', 'SUV'],
            ).values_list('name', flat=True),
        )
        assert names == ['SUV', 'Pickup']


class TestFleetVehicleModelBrand:
    def test_create_and_str(self):
        brand = FleetVehicleModelBrand.objects.create(name='Toyota')
        assert str(brand) == 'Toyota'
        assert brand.active is True

    def test_model_count_counts_only_active_models(self):
        brand = FleetVehicleModelBrand.objects.create(name='Nissan')
        FleetVehicleModel.objects.create(name='Sentra', brand=brand, active=True)
        FleetVehicleModel.objects.create(name='March', brand=brand, active=False)
        assert brand.model_count == 1


class TestFleetVehicleTag:
    def test_create_and_str_and_uniqueness(self):
        tag = FleetVehicleTag.objects.create(name='Ejecutivo', color=3)
        assert str(tag) == 'Ejecutivo'
        with pytest.raises(Exception):
            FleetVehicleTag.objects.create(name='Ejecutivo')


class TestFleetVehicleState:
    def test_create_and_str(self):
        state = FleetVehicleState.objects.create(name='Nueva solicitud', sequence=1)
        assert str(state) == 'Nueva solicitud'
        assert state.fold is False
