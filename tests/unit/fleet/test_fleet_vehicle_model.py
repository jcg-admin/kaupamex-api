"""``fleet.vehicle.model`` (addon ``fleet``, cierre parcial).

Adaptación fiel de Odoo fleet/models/fleet_vehicle_model.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).
"""
import pytest

from addons.fleet.models import (
    FleetVehicle,
    FleetVehicleModel,
    FleetVehicleModelBrand,
    FleetVehicleModelCategory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def brand():
    return FleetVehicleModelBrand.objects.create(name='Toyota')


class TestFleetVehicleModelStr:
    def test_str_prefixes_brand_when_present(self, brand):
        model = FleetVehicleModel.objects.create(name='Corolla', brand=brand)
        assert str(model) == 'Toyota/Corolla'

    def test_str_falls_back_to_name_without_brand_name(self, brand):
        brand.name = ''
        brand.save(update_fields=['name'])
        model = FleetVehicleModel.objects.create(name='Corolla', brand=brand)
        assert str(model) == 'Corolla'


class TestFleetVehicleModelDefaults:
    def test_vehicle_type_defaults_to_car(self, brand):
        model = FleetVehicleModel.objects.create(name='Corolla', brand=brand)
        assert model.vehicle_type == FleetVehicleModel.VEHICLE_TYPE_CAR

    def test_default_fuel_type_defaults_to_electric(self, brand):
        model = FleetVehicleModel.objects.create(name='Corolla', brand=brand)
        assert model.default_fuel_type == 'electric'


class TestFleetVehicleModelComputedProperties:
    def test_image_128_delegates_to_brand(self, brand):
        model = FleetVehicleModel.objects.create(name='Corolla', brand=brand)
        # Sin logo cargado en ninguno de los dos → ambos falsy.
        assert not model.image_128
        assert not brand.image_128

    def test_co2_emission_unit_follows_range_unit(self, brand):
        km_model = FleetVehicleModel.objects.create(
            name='Corolla', brand=brand, range_unit='km',
        )
        mi_model = FleetVehicleModel.objects.create(
            name='Camry', brand=brand, range_unit='mi',
        )
        assert km_model.co2_emission_unit == 'g/km'
        assert mi_model.co2_emission_unit == 'g/mi'

    def test_vehicle_count_reflects_related_vehicles(self, brand):
        model = FleetVehicleModel.objects.create(name='Corolla', brand=brand)
        assert model.vehicle_count == 0
        FleetVehicle.objects.create(model=model, license_plate='ABC-123')
        assert model.vehicle_count == 1


class TestFleetVehicleModelCategoryLink:
    def test_category_is_optional(self, brand):
        model = FleetVehicleModel.objects.create(name='Corolla', brand=brand)
        assert model.category is None

    def test_category_reverse_relation(self, brand):
        category = FleetVehicleModelCategory.objects.create(name='Sedán')
        model = FleetVehicleModel.objects.create(
            name='Corolla', brand=brand, category=category,
        )
        assert category.models.get(pk=model.pk) == model
