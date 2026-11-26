"""Modelo ``report.layout`` — plantilla visual de los documentos impresos.

Adaptación fiel de Odoo ``odoo/addons/base/models/report_layout.py``
(``odoo-tools@bf077302``, ``odoo19c:``).

Es el catálogo de diseños entre los que se elige al configurar la papelería
(``base.document.layout`` los ofrece). Cada fila lleva su vista y dos rutas de
previsualización.

Procedencia: ``name`` · ``sequence`` (default 50) · ``image`` · ``pdf``
idénticos. ``view_id`` (Many2one a ``ir.ui.view``, obligatorio) → ``view``,
obligatorio también (``odoo19c: odoo/addons/base/models/report_layout.py:12``).
"""

import models

from addons.base.models.timestamped_mixin import TimeStampedModel


class ReportLayout(models.BaseModel, TimeStampedModel):
    """Diseño de documento seleccionable (``report.layout``)."""

    _name = 'report.layout'
    _description = 'Report Layout'
    _order = 'sequence, id'

    name = models.CharField(
        max_length=120,
        blank=True,
        default='',
        verbose_name='Nombre',
    )
    view = models.ForeignKey(
        'base.IrUiView',
        on_delete=models.PROTECT,
        related_name='report_layouts',
        verbose_name='Plantilla del documento',
        help_text='Odoo view_id (required).',
    )
    image = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name='Imagen de previsualización',
    )
    pdf = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name='PDF de previsualización',
    )
    sequence = models.IntegerField(default=50, verbose_name='Secuencia')

    class Meta:
        db_table = 'report_layout'
        ordering = ['sequence', 'id']
        verbose_name = 'Diseño de documento'
        verbose_name_plural = 'Diseños de documento'

    def __str__(self):
        return self.name
