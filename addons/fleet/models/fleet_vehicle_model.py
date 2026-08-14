"""``fleet.vehicle.model`` — modelo comercial de un vehículo (Odoo ``fleet``).

Adaptación fiel de Odoo fleet/models/fleet_vehicle_model.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).

Divergencias documentadas
=========================

- **No hereda ``avatar.mixin``.** La referencia declara
  ``_inherit = [..., 'avatar.mixin']`` **y** inmediatamente redeclara
  ``image_128 = fields.Image(related='brand_id.image_128', readonly=True)`` —
  es decir, el propio addon **sustituye** el ``image_128`` propio del mixin
  por un passthrough de sólo lectura hacia la marca. Heredar
  ``AvatarMixin``/``ImageMixin`` en Django habría agregado cinco columnas
  (``image_1920``/``1024``/``512``/``256``/``128``) que la referencia nunca
  usa como propias — se leen siempre por delegación. Aquí ``image_128`` es una
  ``@property`` que delega a ``brand.image_128`` (fiel al ``related``).
- **``model_year`` (Selection dinámico 1970..año-actual → ``IntegerField``).**
  Django resuelve ``choices=`` en tiempo de import de módulo; una lista de
  ~55 años que crece cada 1° de enero no puede vivir ahí. Se guarda el año
  como entero; el rango válido (1970..hoy) se valida en el serializer.
- **``vehicle_properties_definition`` → ``JSONField``** (``fields.Properties*``
  ya son alias de ``JSONField`` en este árbol — ver ``orm/fields_properties.py``).
  Sin el motor de validación dinámica de esquema de Odoo (deferido).
- **NO se porta ``action_model_vehicle``** — devuelve un diccionario de acción
  de ventana; la navegación la resuelve la capa de vistas/rutas.
- **NO se portan ``_search_display_name``/``_search_vehicle_count``** —
  traducen un filtro a dominio del ORM de Odoo; en Django el ``Q()``
  equivalente lo arma el llamador (mismo criterio que ``ProductTag``).
"""
from datetime import date

import fields
import models

from addons.base.models import TimeStampedModel
from addons.mail.models import MailThread

# FUEL_TYPES — compartido con FleetVehicle (Odoo lo importa desde este módulo:
# ``from odoo.addons.fleet.models.fleet_vehicle_model import FUEL_TYPES``).
FUEL_TYPES = [
    ('diesel', 'Diésel'),
    ('gasoline', 'Gasolina'),
    ('full_hybrid', 'Híbrido completo'),
    ('plug_in_hybrid_diesel', 'Híbrido enchufable (diésel)'),
    ('plug_in_hybrid_gasoline', 'Híbrido enchufable (gasolina)'),
    ('cng', 'GNC'),
    ('lpg', 'GLP'),
    ('hydrogen', 'Hidrógeno'),
    ('electric', 'Eléctrico'),
]


class FleetVehicleModel(MailThread, TimeStampedModel):
    """``fleet.vehicle.model`` — p. ej. "Toyota / Corolla"."""

    VEHICLE_TYPE_CAR = 'car'
    VEHICLE_TYPE_BIKE = 'bike'
    VEHICLE_TYPES = [
        (VEHICLE_TYPE_CAR, 'Auto'),
        (VEHICLE_TYPE_BIKE, 'Bicicleta/moto'),
    ]
    TRANSMISSIONS = [('manual', 'Manual'), ('automatic', 'Automática')]
    POWER_UNITS = [('power', 'kW'), ('horsepower', 'Caballos de fuerza (hp)')]
    CO2_EMISSION_UNITS = [('g/km', 'g/km'), ('g/mi', 'g/mi')]
    RANGE_UNITS = [('km', 'km'), ('mi', 'mi')]
    DRIVE_TYPES = [
        ('fwd', 'Tracción delantera (FWD)'),
        ('awd', 'Tracción integral (AWD)'),
        ('rwd', 'Tracción trasera (RWD)'),
        ('4wd', 'Tracción en las 4 ruedas (4WD)'),
    ]

    name = fields.Char(max_length=150, help_text='Odoo name (required).')
    brand = fields.Many2one(
        'fleet.FleetVehicleModelBrand', on_delete=models.PROTECT,
        related_name='models', help_text='Fabricante (Odoo brand_id, required).',
    )
    category = fields.Many2one(
        'fleet.FleetVehicleModelCategory', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='models',
        help_text='Categoría (Odoo category_id).',
    )
    vendors = fields.Many2many(
        'base.ResPartner', blank=True,
        db_table='fleet_vehicle_model_vendors', related_name='fleet_vehicle_models',
        help_text='Proveedores del modelo (Odoo vendor_ids).',
    )
    active = fields.Boolean(default=True, help_text='Odoo active.')
    vehicle_type = fields.Selection(
        max_length=4, choices=VEHICLE_TYPES, default=VEHICLE_TYPE_CAR,
        help_text='Odoo vehicle_type.',
    )
    transmission = fields.Selection(
        max_length=9, choices=TRANSMISSIONS, null=True, blank=True,
        help_text='Odoo transmission.',
    )
    model_year = fields.Integer(
        null=True, blank=True,
        help_text='Año del modelo (Odoo model_year, Selection dinámico '
                   '1970..hoy → entero; ver docstring del módulo).',
    )
    color = fields.Char(max_length=50, blank=True, default='', help_text='Odoo color.')
    seats = fields.Integer(null=True, blank=True, help_text='Odoo seats.')
    doors = fields.Integer(
        null=True, blank=True,
        help_text='Número de puertas, incluidas cajuela y portón trasero '
                   'si aplica (Odoo doors).',
    )
    trailer_hook = fields.Boolean(
        default=False,
        help_text='Enganche de remolque (Odoo trailer_hook).',
    )
    default_co2 = fields.Float(
        null=True, blank=True, help_text='Emisiones CO₂ por defecto (Odoo default_co2).',
    )
    co2_standard = fields.Char(
        max_length=150, blank=True, default='',
        help_text='Norma de emisiones bajo la que se mide (Odoo co2_standard).',
    )
    default_fuel_type = fields.Selection(
        max_length=23, choices=FUEL_TYPES, default='electric',
        help_text='Odoo default_fuel_type.',
    )
    power = fields.Float(null=True, blank=True, help_text='Potencia en kW (Odoo power).')
    horsepower = fields.Float(null=True, blank=True, help_text='Odoo horsepower.')
    horsepower_tax = fields.Float(null=True, blank=True, help_text='Odoo horsepower_tax.')
    electric_assistance = fields.Boolean(default=False, help_text='Odoo electric_assistance.')
    power_unit = fields.Selection(
        max_length=10, choices=POWER_UNITS, default='power',
        help_text='Odoo power_unit.',
    )
    vehicle_properties_definition = fields.PropertiesDefinition(
        null=True, blank=True,
        help_text='Esquema de propiedades dinámicas del modelo (Odoo '
                   'vehicle_properties_definition). Sin motor de validación '
                   'de esquema (deferido).',
    )
    vehicle_range = fields.Integer(null=True, blank=True, help_text='Odoo vehicle_range.')
    range_unit = fields.Selection(
        max_length=2, choices=RANGE_UNITS, default='km',
        help_text='Odoo range_unit.',
    )
    drive_type = fields.Selection(
        max_length=4, choices=DRIVE_TYPES, null=True, blank=True,
        help_text='Odoo drive_type.',
    )

    class Meta:
        db_table = 'fleet_vehicle_model'
        ordering = ['name']
        verbose_name = 'Modelo de vehículo'
        verbose_name_plural = 'Modelos de vehículo'

    def __str__(self):
        """``_compute_display_name`` — "Marca/Modelo" cuando hay marca."""
        if self.brand_id and self.brand.name:
            return f'{self.brand.name}/{self.name}'
        return self.name or ''

    @property
    def image_128(self):
        """``related='brand_id.image_128', readonly=True``."""
        return self.brand.image_128 if self.brand_id else None

    @property
    def vehicle_count(self):
        """``_compute_vehicle_count`` — vehículos que usan este modelo."""
        return self.vehicles.count()

    @property
    def co2_emission_unit(self):
        """``_compute_co2_emission_unit`` — depende de ``range_unit``."""
        return 'g/km' if self.range_unit == 'km' else 'g/mi'

    @staticmethod
    def year_choices():
        """Rango válido de ``model_year`` — reemplaza el ``_get_year_selection``
        dinámico de la referencia; lo consume el serializer, no el modelo."""
        current_year = date.today().year
        return list(range(1970, current_year + 1))
