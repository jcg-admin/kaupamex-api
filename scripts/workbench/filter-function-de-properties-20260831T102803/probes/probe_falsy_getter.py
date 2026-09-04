"""Sonda 3: ¿por qué camino devuelve ``expression_getter`` un ``False``?

El control de neutralización dejó la guarda ``if not corecords`` en verde: el
caso apuntaba a una fila SIN valor, y ésa devuelve un ``QuerySet`` vacío
—``model.objects.none()``, porque el contenedor SÍ declara la propiedad—, que
``filtered_domain`` procesa sin problema. Esta sonda busca el camino que sí
produce el ``False`` no iterable.
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

marca = FleetVehicleModelBrand.objects.create(name='Sonda3')
contenedor = FleetVehicleModel.objects.create(
    name='Sonda3', brand=marca,
    vehicle_properties_definition=[
        {'name': 'marca', 'type': 'many2one',
         'comodel': 'fleet.FleetVehicleModelBrand'}])
vacia = FleetVehicle.objects.create(model=contenedor)
vacia.refresh_from_db()

field = FleetVehicle._meta.get_field('vehicle_properties')
declarada = field.expression_getter('vehicle_properties.marca')(vacia)
ausente = field.expression_getter('vehicle_properties.inexistente')(vacia)
print('declarada sin valor :', type(declarada).__name__, repr(declarada))
print('no declarada        :', type(ausente).__name__, repr(ausente))

runner.teardown_databases(old)
