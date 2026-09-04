"""Sonda: qué forma tienen los tres valores que ``filter_function`` toca.

No es el camino principal —eso son los tests de conducta— sino la pregunta
suelta que hay que responder ANTES de escribirlos: qué devuelve
``expression_getter`` para una propiedad ``many2one``, qué recibe
``filter_function`` como ``records``, y si ``filtered_domain`` acepta esa forma.
"""
import django
django.setup()

from addons.fleet.models.fleet_vehicle import FleetVehicle
from addons.fleet.models.fleet_vehicle_model import FleetVehicleModel
from addons.fleet.models.fleet_vehicle_model_brand import FleetVehicleModelBrand
from orm.fields_properties import _model_of

print('comodel por etiqueta:', _model_of('fleet.FleetVehicleModelBrand'))
print('comodel por _name   :', _model_of('fleet.vehicle.model.brand'))
field = FleetVehicle._meta.get_field('vehicle_properties')
print('campo:', type(field).__name__)
print('records() instancia :', type(FleetVehicle()).__name__)
getter = field.expression_getter('vehicle_properties.marca')
print('getter sobre instancia vacía:', repr(getter(FleetVehicle())))
