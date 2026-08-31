"""Sonda 2: qué tipo tiene el valor de una propiedad ``many2one`` al leerla.

La primera redacción del porte afirmaba «una instancia, no un recordset de
uno». ``Property.__getitem__`` devuelve ``model.objects.filter(pk__in=pks)``,
que es un ``QuerySet``. Esta sonda lo decide contra una fila real.
"""
import django
django.setup()

from django.test.utils import setup_test_environment
from django.test.runner import DiscoverRunner

setup_test_environment()
runner = DiscoverRunner(verbosity=0, interactive=False, keepdb=True)
old = runner.setup_databases()

from addons.fleet.models.fleet_vehicle import FleetVehicle
from addons.fleet.models.fleet_vehicle_model import FleetVehicleModel
from addons.fleet.models.fleet_vehicle_model_brand import FleetVehicleModelBrand

brand = FleetVehicleModelBrand.objects.create(name='Sonda')
container = FleetVehicleModel.objects.create(
    name='Sonda', brand=brand,
    vehicle_properties_definition=[
        {'name': 'marca', 'type': 'many2one',
         'comodel': 'fleet.FleetVehicleModelBrand', 'string': 'Marca'},
        {'name': 'color', 'type': 'char', 'string': 'Color'}])
row = FleetVehicle.objects.create(
    model=container, vehicle_properties={'marca': brand.pk, 'color': 'azul'})
row.refresh_from_db()

field = FleetVehicle._meta.get_field('vehicle_properties')
getter = field.expression_getter('vehicle_properties.marca')
val = getter(row)
print('almacenado      :', row.vehicle_properties)
print('getter marca    :', type(val).__name__, '->', repr(val))
print('getter color    :', repr(field.expression_getter('vehicle_properties.color')(row)))
print('records()       :', repr(field.expression_getter('vehicle_properties.marca')(FleetVehicle())))

runner.teardown_databases(old)
