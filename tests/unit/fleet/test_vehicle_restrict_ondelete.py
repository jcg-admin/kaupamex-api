"""``fleet.vehicle``: lecturas de odómetro e historial de conductor con
``ondelete='restrict'``.

≙ ``odoo19c: addons/fleet/models/fleet_vehicle_odometer.py:15`` y
``fleet_vehicle_assignation_log.py:12``: ``vehicle_id`` es ``required=True``
sin ``ondelete``, y la regla por defecto de un Many2one requerido es
``restrict`` (``odoo/orm/fields_relational.py:274-282``). ``fleet.vehicle``
no sobreescribe ``unlink``: borrar un vehículo con lecturas o historial falla
y las filas se conservan. Diseño: ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/fleet-restrict-ondelete.md``.
"""
import pytest
from django.db.models import ProtectedError

from addons.base.models import ResPartner
from addons.fleet.models import (FleetVehicle, FleetVehicleAssignationLog,
                                 FleetVehicleModel, FleetVehicleModelBrand,
                                 FleetVehicleOdometer)

pytestmark = pytest.mark.django_db


@pytest.fixture
def vehicle():
    brand = FleetVehicleModelBrand.objects.create(name='Marca')
    model = FleetVehicleModel.objects.create(name='Modelo', brand=brand)
    return FleetVehicle.objects.create(model=model)


def _refuses_and_keeps(vehicle, child):
    with pytest.raises(ProtectedError):
        FleetVehicle.objects.filter(pk=vehicle.pk).delete()
    assert type(child).objects.filter(pk=child.pk).exists()


def test_a_vehicle_with_odometer_readings_is_not_deleted(vehicle):
    reading = FleetVehicleOdometer.objects.create(vehicle=vehicle, value=10)
    _refuses_and_keeps(vehicle, reading)


def test_a_vehicle_with_driver_history_is_not_deleted(vehicle):
    driver = ResPartner.objects.create(name='Conductora')
    log = FleetVehicleAssignationLog.objects.create(vehicle=vehicle,
                                                    driver=driver)
    _refuses_and_keeps(vehicle, log)


def test_a_vehicle_without_children_is_deleted(vehicle):
    FleetVehicle.objects.filter(pk=vehicle.pk).delete()
    assert not FleetVehicle.objects.filter(pk=vehicle.pk).exists()
