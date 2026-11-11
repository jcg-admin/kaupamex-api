"""Las 93 políticas de borrado de Django que destruyen lo que la fuente
conserva o protege.

Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
delete-policy-contract-tests.md``. Población: ``outputs/
fk_reference_ondelete.tsv`` del mismo banco (odoo-tools ``abe4040ec1``),
filas donde la fuente declara ``set null`` o ``restrict`` y Django
``CASCADE`` (o declaraba, para las ya corregidas de ``CORRECTED``).

Tres planos: el atributo de cada fila (``xfail`` estricto mientras difiera),
el borrado por el ORM en dos representantes (lo observado hoy y el contrato
de la fuente) y el borrado en SQL, que no cascada.
"""
import csv
import pathlib

import pytest
from django.apps import apps
from django.db import IntegrityError, connection, models, transaction

from addons.base.models.ir_actions import IrActionsActions, IrActionsTodo
from addons.base.models.res_device import ResDeviceLog
from addons.fleet.models import (FleetVehicle, FleetVehicleModel,
                                 FleetVehicleModelBrand,
                                 FleetVehicleOdometer)

_MATRIX = (pathlib.Path(__file__).resolve().parents[3] / 'scripts'
           / 'workbench' / 'orm-continuation-plan-20261103T095630'
           / 'outputs' / 'fk_reference_ondelete.tsv')

#: Filas ya corregidas: su caso corre sin ``xfail`` y tiene que pasar. Cada
#: entrada cita la unidad que la corrigió.
CORRECTED = {
    # designs/stock-quant-restrict-ondelete.md
    'stock.StockQuant.product', 'stock.StockQuant.location',
    'stock.StockQuant.lot',
    # designs/country-and-todo-restrict-ondelete.md
    'base.ResCountryState.country', 'base_address_extended.ResCity.country_id',
    'base.IrActionsTodo.action',
}

#: Política de Django que corresponde al ``ondelete`` de la fuente.
_EXPECTED = {
    'set null': (models.SET_NULL,),
    'restrict': (models.PROTECT, models.RESTRICT),
}


def _destructive_rows():
    with _MATRIX.open(newline='') as handle:
        for row in csv.DictReader(handle, delimiter='\t'):
            kind = row['reference_ondelete'].split(' (')[0]
            ident = f"{row['django_field']}.{row['field']}"
            if kind in _EXPECTED and (row['django_policy'] == 'CASCADE'
                                      or ident in CORRECTED):
                marks = () if ident in CORRECTED else pytest.mark.xfail(
                    strict=True, reason=(
                        f"{kind} -> CASCADE "
                        f"(odoo19c: {row['reference_field']})"))
                yield pytest.param(row, kind, id=ident, marks=marks)


_ROWS = list(_destructive_rows())


def test_the_population_is_the_measured_one():
    """93 filas: 48 ``set null`` y 45 ``restrict`` (42 por defecto y 3
    explícitas). Eran 96 hasta aplicar la regla de los transitorios
    (``odoo19c: odoo/orm/fields_relational.py:274-282``): tres Many2one
    obligatorios de transitorios son ``cascade`` en la fuente. Si la matriz
    cambia, este conteo lo dice antes que nadie."""
    kinds = [param.values[1] for param in _ROWS]
    assert (len(kinds), kinds.count('set null'),
            kinds.count('restrict')) == (93, 48, 45)


@pytest.mark.parametrize('row, kind', _ROWS)
def test_the_django_policy_matches_the_source_ondelete(row, kind):
    model = apps.get_model(row['django_field'])
    field = model._meta.get_field(row['field'])
    assert field.remote_field.on_delete in _EXPECTED[kind]


# --- ORM: dos representantes, uno por familia ------------------------------

@pytest.mark.django_db
@pytest.mark.xfail(strict=True, reason=(
    'set null -> CASCADE: la fuente vacía user_id '
    '(odoo19c: odoo/addons/base/models/res_device.py:28); aquí se borra'))
def test_deleting_a_user_keeps_its_device_logs(user):
    log = ResDeviceLog.objects.create(session_identifier='probe-session',
                                      user=user)
    type(user).objects.filter(pk=user.pk).delete()
    log.refresh_from_db()
    assert log.user_id is None


@pytest.mark.django_db
def test_today_deleting_a_user_deletes_its_device_logs(user):
    """Lo observado hoy, para que el ``xfail`` no oculte otra causa."""
    log = ResDeviceLog.objects.create(session_identifier='probe-session',
                                      user=user)
    type(user).objects.filter(pk=user.pk).delete()
    assert not ResDeviceLog.objects.filter(pk=log.pk).exists()


@pytest.fixture
def vehicle():
    brand = FleetVehicleModelBrand.objects.create(name='Marca')
    model = FleetVehicleModel.objects.create(name='Modelo', brand=brand)
    return FleetVehicle.objects.create(model=model)


@pytest.mark.django_db
@pytest.mark.xfail(strict=True, reason=(
    'restrict -> CASCADE: la fuente rehúsa borrar un vehículo con lecturas '
    'de odómetro (odoo19c: addons/fleet/models/'
    'fleet_vehicle_odometer.py:15); aquí se borran'))
def test_deleting_a_vehicle_with_odometer_readings_is_refused(vehicle):
    reading = FleetVehicleOdometer.objects.create(vehicle=vehicle,
                                                  value=10)
    with pytest.raises(models.ProtectedError):
        FleetVehicle.objects.filter(pk=vehicle.pk).delete()
    assert FleetVehicleOdometer.objects.filter(pk=reading.pk).exists()


@pytest.mark.django_db
def test_today_deleting_a_vehicle_deletes_its_odometer_readings(vehicle):
    """Lo observado hoy, para que el ``xfail`` no oculte otra causa. El
    representante anterior de la familia, ``ir.actions.todo``, ya está
    corregido (``designs/country-and-todo-restrict-ondelete.md``)."""
    reading = FleetVehicleOdometer.objects.create(vehicle=vehicle,
                                                  value=10)
    FleetVehicle.objects.filter(pk=vehicle.pk).delete()
    assert not FleetVehicleOdometer.objects.filter(pk=reading.pk).exists()


# --- PostgreSQL: el DELETE crudo no cascada ---------------------------------

@pytest.mark.django_db
def test_a_raw_delete_of_the_parent_does_not_cascade():
    """La FK física es NO ACTION y diferible (``confdeltype = 'a'``): un
    DELETE en SQL del padre con hijo presente falla al comprobar la
    restricción y el hijo sigue. La pérdida de las 96 es sólo del camino
    ORM."""
    action = IrActionsActions.objects.create(
        name='probe', type='ir.actions.actions')
    wizard_step = IrActionsTodo.objects.create(action=action)
    table = IrActionsActions._meta.db_table
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            with connection.cursor() as cr:
                cr.execute('SET CONSTRAINTS ALL IMMEDIATE')
                cr.execute(f'DELETE FROM {table} WHERE id = %s',
                           [action.pk])
    assert IrActionsTodo.objects.filter(pk=wizard_step.pk).exists()
