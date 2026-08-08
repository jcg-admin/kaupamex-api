"""``fleet.vehicle`` (addon ``fleet``, cierre parcial).

Adaptación fiel de Odoo fleet/models/fleet_vehicle.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3). Ver el docstring del modelo para
las siete divergencias documentadas frente a la referencia.
"""
from datetime import date, timedelta

import pytest

from addons.base.models import ResCompany, ResPartner
from addons.fleet.models import (
    FleetServiceType,
    FleetVehicle,
    FleetVehicleLogContract,
    FleetVehicleLogServices,
    FleetVehicleModel,
    FleetVehicleModelBrand,
)
from tests.factories.user_factory import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def brand():
    return FleetVehicleModelBrand.objects.create(name='Toyota')


@pytest.fixture
def model(brand):
    return FleetVehicleModel.objects.create(
        name='Corolla', brand=brand, color='Rojo', seats=5, doors=4,
        transmission='automatic', default_fuel_type='gasoline',
        default_co2=120.5, power=90.0, vehicle_range=600, range_unit='km',
    )


@pytest.fixture
def driver():
    return ResPartner.objects.create(name='Juan Pérez')


class TestFleetVehicleName:
    def test_name_composes_brand_model_and_plate(self, model):
        vehicle = FleetVehicle.objects.create(model=model, license_plate='ABC-123')
        assert vehicle.name == 'Toyota/Corolla/ABC-123'

    def test_name_falls_back_when_no_plate(self, model):
        vehicle = FleetVehicle.objects.create(model=model)
        assert vehicle.name == 'Toyota/Corolla/Sin placa'

    def test_name_is_a_column_so_the_database_can_filter_by_it(self, model):
        """El motivo por el que la referencia lo declara ``store=True``.

        Con ``@property`` esta consulta lanzaba ``FieldError``: la vieja
        divergencia impedía exactamente lo que el campo existe para permitir.
        """
        FleetVehicle.objects.create(model=model, license_plate='ABC-123')

        encontrado = FleetVehicle.objects.filter(name__icontains='corolla')
        assert encontrado.count() == 1
        assert encontrado.first().name == 'Toyota/Corolla/ABC-123'

    def test_name_is_recomputed_when_the_plate_changes(self, model):
        vehicle = FleetVehicle.objects.create(model=model, license_plate='ABC-123')

        vehicle.license_plate = 'XYZ-789'
        vehicle.save()

        vehicle.refresh_from_db()
        assert vehicle.name == 'Toyota/Corolla/XYZ-789'

    def test_name_survives_a_save_that_narrows_update_fields(self, model):
        """``update_fields`` acotado no debe dejar el nombre viejo en la fila."""
        vehicle = FleetVehicle.objects.create(model=model, license_plate='ABC-123')

        vehicle.license_plate = 'XYZ-789'
        vehicle.save(update_fields=['license_plate'])

        vehicle.refresh_from_db()
        assert vehicle.name == 'Toyota/Corolla/XYZ-789'


class TestFleetVehicleRelatedProperties:
    def test_vehicle_type_delegates_to_model(self, model):
        vehicle = FleetVehicle.objects.create(model=model)
        assert vehicle.vehicle_type == model.vehicle_type

    def test_manager_accepts_a_res_users(self, model):
        manager = UserFactory()
        vehicle = FleetVehicle.objects.create(model=model, manager=manager)
        assert vehicle.manager_id == manager.pk

    def test_currency_and_country_delegate_to_company(self, model):
        company = ResCompany.objects.create(code='acme-fleet', name='Acme')
        vehicle = FleetVehicle.objects.create(model=model, company=company)
        assert vehicle.currency == company.currency
        assert vehicle.country == company.country

    def test_currency_is_none_without_company(self, model):
        vehicle = FleetVehicle.objects.create(model=model)
        assert vehicle.currency is None


class TestFleetVehicleOdometer:
    def test_odometer_defaults_to_zero(self, model):
        vehicle = FleetVehicle.objects.create(model=model)
        assert vehicle.odometer == 0

    def test_setting_odometer_creates_a_log_row(self, model, driver):
        vehicle = FleetVehicle.objects.create(model=model, driver=driver)
        vehicle.odometer = 15000
        assert vehicle.odometer == 15000
        log = vehicle.odometer_logs.get()
        assert log.value == 15000
        assert log.driver_id == driver.pk

    def test_setting_zero_odometer_is_a_no_op(self, model):
        vehicle = FleetVehicle.objects.create(model=model)
        vehicle.odometer = 0
        assert vehicle.odometer_logs.count() == 0


class TestFleetVehicleDriverHistory:
    def test_assigning_driver_on_create_logs_history(self, model, driver):
        vehicle = FleetVehicle.objects.create(model=model, driver=driver)
        assert vehicle.assignation_logs.count() == 1
        entry = vehicle.assignation_logs.get()
        assert entry.driver_id == driver.pk
        assert entry.date_start == date.today()

    def test_changing_driver_logs_a_new_entry(self, model, driver):
        vehicle = FleetVehicle.objects.create(model=model)
        assert vehicle.assignation_logs.count() == 0
        vehicle.driver = driver
        vehicle.save()
        assert vehicle.assignation_logs.count() == 1

    def test_resaving_same_driver_does_not_duplicate_history(self, model, driver):
        vehicle = FleetVehicle.objects.create(model=model, driver=driver)
        assert vehicle.assignation_logs.count() == 1
        vehicle.description = 'Actualización sin cambio de conductor'
        vehicle.save()
        assert vehicle.assignation_logs.count() == 1


class TestFleetVehicleDeactivation:
    def test_deactivating_closes_contracts_and_services(self, model):
        vehicle = FleetVehicle.objects.create(model=model)
        stype = FleetServiceType.objects.create(
            name='Afinación', category=FleetServiceType.CATEGORY_SERVICE,
        )
        contract = FleetVehicleLogContract.objects.create(vehicle=vehicle)
        service = FleetVehicleLogServices.objects.create(
            vehicle=vehicle, service_type=stype,
        )
        assert contract.active is True
        assert service.active is True

        vehicle.active = False
        vehicle.save()

        contract.refresh_from_db()
        service.refresh_from_db()
        assert contract.active is False
        assert service.active is False


class TestFleetVehicleSyncFieldsFromModel:
    def test_sync_copies_truthy_fields_from_model(self, model):
        vehicle = FleetVehicle.objects.create(model=model)
        vehicle.sync_fields_from_model()
        assert vehicle.color == 'Rojo'
        assert vehicle.seats == 5
        assert vehicle.doors == 4
        assert vehicle.transmission == 'automatic'
        assert vehicle.fuel_type == 'gasoline'
        assert vehicle.co2 == 120.5
        assert vehicle.brand_id == model.brand_id

    def test_sync_restricted_to_field_names(self, model):
        vehicle = FleetVehicle.objects.create(model=model)
        vehicle.sync_fields_from_model(field_names=['color'])
        assert vehicle.color == 'Rojo'
        assert vehicle.seats is None


class TestFleetVehicleContractCounters:
    def test_contract_count_and_has_open_contract(self, model):
        vehicle = FleetVehicle.objects.create(model=model)
        assert vehicle.contract_count == 0
        assert vehicle.has_open_contract is False

        FleetVehicleLogContract.objects.create(
            vehicle=vehicle, state=FleetVehicleLogContract.STATE_OPEN,
            expiration_date=date.today() + timedelta(days=30),
        )
        assert vehicle.contract_count == 1
        assert vehicle.has_open_contract is True


class TestFleetVehicleAcceptDriverChange:
    def test_accept_driver_change_moves_future_to_current(self, model, driver):
        vehicle = FleetVehicle.objects.create(
            model=model, future_driver=driver, plan_to_change_car=True,
        )
        vehicle.accept_driver_change()
        vehicle.refresh_from_db()
        assert vehicle.driver_id == driver.pk
        assert vehicle.future_driver_id is None
        assert vehicle.plan_to_change_car is False

    def test_accept_driver_change_releases_other_vehicle_of_same_driver(
        self, model, driver,
    ):
        other_vehicle = FleetVehicle.objects.create(model=model, driver=driver)
        vehicle = FleetVehicle.objects.create(model=model, future_driver=driver)

        vehicle.accept_driver_change()

        other_vehicle.refresh_from_db()
        assert other_vehicle.driver_id is None
        assert other_vehicle.plan_to_change_car is False
