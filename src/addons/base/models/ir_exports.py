"""Modelos ``ir.exports`` e ``ir.exports.line`` — exportaciones guardadas.

Adaptación fiel de Odoo ``odoo/addons/base/models/ir_exports.py``
(``odoo-tools@bf077302``, ``odoo19c:``).

Guarda una selección de campos con nombre para reutilizarla al exportar: el
usuario elige "Pedidos — columnas de contabilidad" en vez de volver a marcar
las mismas doce casillas. ``resource`` es el modelo al que aplica.

Procedencia de los campos:

- ``name`` → ``name``; ``resource`` → ``resource`` (indexado, como allá).
- ``export_fields`` (One2many) → ``related_name='export_fields'`` en la línea.
- ``ir.exports.line.name`` → ``name``; ``export_id`` → ``export`` con
  ``CASCADE``, que es el ``ondelete`` de la referencia.

``resource`` guarda el **label del modelo Django** (``app_label.ModelName``),
que es el análogo del ``_name`` de Odoo: el identificador con el que el
registro se resuelve en el ORM.
"""
from django.db import models

from addons.base.models.timestamped_mixin import TimeStampedModel


class IrExports(TimeStampedModel):
    """Selección de campos guardada para exportar (``ir.exports``)."""

    name = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Nombre',
    )
    resource = models.CharField(
        max_length=120, blank=True, default='', db_index=True,
        verbose_name='Modelo',
        help_text="Odoo resource. Label del modelo, p.ej. 'sale.SaleOrder'.",
    )

    class Meta:
        db_table = 'ir_exports'
        ordering = ['name', 'id']
        verbose_name = 'Exportación'
        verbose_name_plural = 'Exportaciones'

    def __str__(self):
        return self.name or f'{self.resource} #{self.pk}'


class IrExportsLine(models.Model):
    """Un campo dentro de una exportación (``ir.exports.line``)."""

    name = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Campo',
    )
    export = models.ForeignKey(
        IrExports, on_delete=models.CASCADE, db_index=True,
        related_name='export_fields', verbose_name='Exportación',
    )

    class Meta:
        db_table = 'ir_exports_line'
        ordering = ['id']
        verbose_name = 'Campo de exportación'
        verbose_name_plural = 'Campos de exportación'

    def __str__(self):
        return self.name
