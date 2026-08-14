"""Modelos del addon ``fleet`` (estructura Odoo: un archivo por modelo).

Cierre parcial (11 de 14 ``_name`` de la referencia) — ver
``analisis-porte-addon-fleet`` para el detalle de lo que queda fuera
(wizard de correo, reportes SQL-view, extensiones de ``mail.activity.type``/
``res.config.settings``).
"""
from .fleet_service_type import FleetServiceType
from .fleet_vehicle_model_category import FleetVehicleModelCategory
from .fleet_vehicle_model_brand import FleetVehicleModelBrand
from .fleet_vehicle_tag import FleetVehicleTag
from .fleet_vehicle_state import FleetVehicleState
from .fleet_vehicle_model import FleetVehicleModel, FUEL_TYPES
from .fleet_vehicle_odometer import FleetVehicleOdometer
from .fleet_vehicle_assignation_log import FleetVehicleAssignationLog
from .fleet_vehicle import FleetVehicle
from .fleet_vehicle_log_contract import FleetVehicleLogContract
from .fleet_vehicle_log_services import FleetVehicleLogServices

__all__ = [
    'FleetServiceType',
    'FleetVehicleModelCategory',
    'FleetVehicleModelBrand',
    'FleetVehicleTag',
    'FleetVehicleState',
    'FleetVehicleModel',
    'FUEL_TYPES',
    'FleetVehicleOdometer',
    'FleetVehicleAssignationLog',
    'FleetVehicle',
    'FleetVehicleLogContract',
    'FleetVehicleLogServices',
]
