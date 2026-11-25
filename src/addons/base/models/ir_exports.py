"""Modelos ``ir.exports`` e ``ir.exports.line`` — exportaciones guardadas.

Adaptación fiel de Odoo ``odoo/addons/base/models/ir_exports.py``
(``odoo-tools@bf077302``, ``odoo19c:``).

Guarda una selección de campos con nombre para reutilizarla al exportar: el
usuario elige "Pedidos — columnas de contabilidad" en vez de volver a marcar
las mismas doce casillas. ``resource`` es el modelo al que aplica.

Procedencia de los campos:

- ``name`` → ``name``; ``resource`` → ``resource`` (indexado, como allá).
- ``export_fields`` → ``One2many`` declarado en el padre con ``copy=True``
  (``odoo19c: ir_exports.py:14``): duplicar una exportación duplica sus
  líneas. Antes sólo era el ``related_name`` de la FK del hijo, y un reverso
  no declarado no se copia (H-API-1161).
- ``ir.exports.line.name`` → ``name``; ``export_id`` → ``export_id`` con
  ``CASCADE``, que es el ``ondelete`` de la referencia, y su columna de
  siempre (``db_column``).

``resource`` guarda el **label del modelo Django** (``app_label.ModelName``),
que es el análogo del ``_name`` de Odoo: el identificador con el que el
registro se resuelve en el ORM.
"""

from django.db import models

import fields
from addons.base.models.timestamped_mixin import TimeStampedModel
from orm.models import BaseModel


class IrExports(BaseModel, TimeStampedModel):
    """Selección de campos guardada para exportar (``ir.exports``)."""

    _name = 'ir.exports'
    _description = 'Exports'
    _order = 'name, id'

    name = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name='Nombre',
    )
    resource = models.CharField(
        max_length=120,
        blank=True,
        default='',
        db_index=True,
        verbose_name='Modelo',
        help_text="Odoo resource. Label del modelo, p.ej. 'sale.SaleOrder'.",
    )
    export_fields = fields.One2many(
        'ir.exports.line', 'export_id', string='Export ID', copy=True)

    class Meta:
        db_table = 'ir_exports'
        ordering = ['name', 'id']
        verbose_name = 'Exportación'
        verbose_name_plural = 'Exportaciones'

    def __str__(self):
        return self.name or f'{self.resource} #{self.pk}'


class IrExportsLine(BaseModel):
    """Un campo dentro de una exportación (``ir.exports.line``)."""

    _name = 'ir.exports.line'
    _description = 'Exports Line'
    _order = 'id'

    name = models.CharField(
        max_length=120,
        blank=True,
        default='',
        verbose_name='Campo',
    )
    export_id = fields.Many2one(
        IrExports,
        on_delete=models.CASCADE, null=True, blank=True,
        db_index=True,
        related_name='+',
        verbose_name='Exportación',
        db_column='export_id',
    )

    class Meta:
        db_table = 'ir_exports_line'
        ordering = ['id']
        verbose_name = 'Campo de exportación'
        verbose_name_plural = 'Campos de exportación'

    def __str__(self):
        return self.name
