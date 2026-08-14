"""``fleet.vehicle.model.brand`` — fabricante/marca (Odoo ``fleet``).

Adaptación fiel de Odoo fleet/models/fleet_vehicle_model_brand.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).

La referencia declara un único ``image_128 = fields.Image("Logo", ...)`` —
**no** hereda ``image.mixin``/``avatar.mixin`` completos (a diferencia de
``fleet.vehicle`` y ``fleet.vehicle.model``, que sí, y que por eso NO heredan
el mixin aquí — ver el docstring de ``fleet_vehicle_model.py``). Se porta tal
cual: un solo campo de imagen, sin las cuatro reducciones ni el avatar SVG.

NO se portan ``action_brand_model``/``action_open_brand_form`` — devuelven
diccionarios de acción de ventana de Odoo (``ir.actions.act_window``), sin
equivalente en DRF; esa navegación la resuelve la capa de vistas/rutas.
"""
import fields

from addons.base.models import TimeStampedModel


class FleetVehicleModelBrand(TimeStampedModel):
    """``fleet.vehicle.model.brand`` — p. ej. "Toyota", "Ford"."""

    name = fields.Char(max_length=150, help_text='Odoo name (required).')
    active = fields.Boolean(default=True, help_text='Odoo active.')
    image_128 = fields.Image(
        upload_to='fleet/brand_logos/', null=True, blank=True,
        help_text='Logo de la marca, 128×128 (Odoo image_128, sin las otras '
                   'reducciones del image.mixin — la referencia no hereda '
                   'el mixin completo aquí, sólo declara este campo).',
    )

    class Meta:
        db_table = 'fleet_vehicle_model_brand'
        ordering = ['name']
        verbose_name = 'Marca de vehículo'
        verbose_name_plural = 'Marcas de vehículo'

    def __str__(self):
        return self.name or ''

    @property
    def model_count(self):
        """Modelos activos de la marca (Odoo ``_compute_model_count``)."""
        return self.models.filter(active=True).count()
