"""Bitácoras de flota: odómetro / contrato / servicio / historial de conductor
(addon ``fleet``, cierre parcial).

Adaptación fiel de Odoo fleet/models/fleet_vehicle_{odometer,log_contract,
log_services,assignation_log}.py (odoo-tools@622ddc2a, odoo19c:, LGPL-3).
"""
from datetime import date, timedelta

import pytest

from addons.base.models import ResPartner
from addons.fleet.models import (
    FleetServiceType,
    FleetVehicle,
    FleetVehicleAssignationLog,
    FleetVehicleLogContract,
    FleetVehicleLogServices,
    FleetVehicleModel,
    FleetVehicleModelBrand,
    FleetVehicleOdometer,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def vehicle():
    brand = FleetVehicleModelBrand.objects.create(name='Toyota')
    model = FleetVehicleModel.objects.create(name='Corolla', brand=brand)
    return FleetVehicle.objects.create(model=model, license_plate='XYZ-987')


@pytest.fixture
def driver():
    return ResPartner.objects.create(name='María López')


class TestFleetVehicleOdometerLog:
    def test_str_combines_vehicle_name_and_date(self, vehicle):
        log = FleetVehicleOdometer.objects.create(
            vehicle=vehicle, value=1000, date=date(2026, 1, 15),
        )
        assert str(log) == f'{vehicle.name} / 2026-01-15'

    def test_unit_delegates_to_vehicle(self, vehicle):
        log = FleetVehicleOdometer.objects.create(vehicle=vehicle, value=500)
        assert log.unit == vehicle.odometer_unit

    def test_save_inherits_driver_from_vehicle_when_missing(self, vehicle, driver):
        vehicle.driver = driver
        vehicle.save()
        log = FleetVehicleOdometer.objects.create(vehicle=vehicle, value=200)
        assert log.driver_id == driver.pk

    def test_save_does_not_override_explicit_driver(self, vehicle, driver):
        other_driver = ResPartner.objects.create(name='Otro conductor')
        vehicle.driver = driver
        vehicle.save()
        log = FleetVehicleOdometer.objects.create(
            vehicle=vehicle, value=200, driver=other_driver,
        )
        assert log.driver_id == other_driver.pk


class TestFleetVehicleLogContract:
    def test_name_prefixes_cost_subtype(self, vehicle):
        subtype = FleetServiceType.objects.create(
            name='Seguro', category=FleetServiceType.CATEGORY_CONTRACT,
        )
        contract = FleetVehicleLogContract.objects.create(
            vehicle=vehicle, cost_subtype=subtype,
        )
        assert contract.name == f'Seguro {vehicle.name}'

    def test_next_year_date_adds_one_year(self):
        start = date(2026, 3, 10)
        assert FleetVehicleLogContract.next_year_date(start) == date(2027, 3, 10)

    def test_days_left_and_expires_today(self, vehicle):
        contract = FleetVehicleLogContract.objects.create(
            vehicle=vehicle, state=FleetVehicleLogContract.STATE_OPEN,
            expiration_date=date.today(),
        )
        assert contract.days_left == 0
        assert contract.expires_today is True

    def test_days_left_is_minus_one_when_closed(self, vehicle):
        contract = FleetVehicleLogContract.objects.create(
            vehicle=vehicle, state=FleetVehicleLogContract.STATE_CLOSED,
            expiration_date=date.today() + timedelta(days=10),
        )
        assert contract.days_left == -1

    def test_has_open_contract_excludes_itself(self, vehicle):
        contract = FleetVehicleLogContract.objects.create(
            vehicle=vehicle, state=FleetVehicleLogContract.STATE_OPEN,
            expiration_date=date.today() + timedelta(days=5),
        )
        assert contract.has_open_contract is False
        FleetVehicleLogContract.objects.create(
            vehicle=vehicle, state=FleetVehicleLogContract.STATE_OPEN,
            expiration_date=date.today() + timedelta(days=5),
        )
        contract.refresh_from_db()
        assert contract.has_open_contract is True

    def test_action_close_sets_state_closed(self, vehicle):
        contract = FleetVehicleLogContract.objects.create(vehicle=vehicle)
        contract.action_close()
        contract.refresh_from_db()
        assert contract.state == FleetVehicleLogContract.STATE_CLOSED

    def test_sync_state_from_dates_marks_expired(self, vehicle):
        contract = FleetVehicleLogContract.objects.create(
            vehicle=vehicle, state=FleetVehicleLogContract.STATE_OPEN,
            start_date=date.today() - timedelta(days=400),
            expiration_date=date.today() - timedelta(days=30),
        )
        contract.sync_state_from_dates()
        assert contract.state == FleetVehicleLogContract.STATE_EXPIRED


class TestFleetVehicleLogServices:
    def test_odometer_getter_defaults_to_zero(self, vehicle):
        stype = FleetServiceType.objects.create(
            name='Frenos', category=FleetServiceType.CATEGORY_SERVICE,
        )
        service = FleetVehicleLogServices.objects.create(
            vehicle=vehicle, service_type=stype,
        )
        assert service.odometer == 0

    def test_odometer_setter_creates_log_and_links_it(self, vehicle):
        stype = FleetServiceType.objects.create(
            name='Frenos', category=FleetServiceType.CATEGORY_SERVICE,
        )
        service = FleetVehicleLogServices.objects.create(
            vehicle=vehicle, service_type=stype,
        )
        service.odometer = 42000
        assert service.odometer == 42000
        assert service.odometer_log.value == 42000
        assert service.odometer_log.vehicle_id == vehicle.pk

    def test_model_and_brand_delegate_to_vehicle(self, vehicle):
        stype = FleetServiceType.objects.create(
            name='Frenos', category=FleetServiceType.CATEGORY_SERVICE,
        )
        service = FleetVehicleLogServices.objects.create(
            vehicle=vehicle, service_type=stype,
        )
        # El puerto expone las delegaciones como propiedades ``model``/
        # ``brand`` (``related='vehicle_id.model_id'`` de la referencia), no
        # como columnas ``*_id``.
        assert service.model == vehicle.model
        assert service.brand == vehicle.model.brand

    def test_sync_defaults_fills_purchaser_from_vehicle_driver(self, vehicle, driver):
        vehicle.driver = driver
        vehicle.save()
        stype = FleetServiceType.objects.create(
            name='Frenos', category=FleetServiceType.CATEGORY_SERVICE,
        )
        service = FleetVehicleLogServices.objects.create(
            vehicle=vehicle, service_type=stype,
        )
        service.sync_defaults()
        assert service.purchaser_id == driver.pk


class TestFleetVehicleAssignationLog:
    def test_str_combines_vehicle_and_driver_names(self, vehicle, driver):
        entry = FleetVehicleAssignationLog.objects.create(
            vehicle=vehicle, driver=driver, date_start=date.today(),
        )
        assert str(entry) == f'{vehicle.name} - {driver.name}'
