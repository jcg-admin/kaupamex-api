"""
Modelo ``ProductTemplateAttributeLine`` — addon ``product`` (base del monolito
modular).

Adaptación fiel de Odoo ``product.template.attribute.line``
(``product/models/product_template_attribute_line.py:8-39``, verificado en 18 y
19): asocia un **atributo** a un **producto** y declara **qué valores** de ese
atributo aplican a ese producto. Núcleo: ``product_tmpl_id``/``attribute_id``/
``value_ids`` (M2M). Es el eje del que se genera el producto cartesiano de
combinaciones.
"""

import fields
import models

from addons.base.models import TimeStampedModel


class ProductTemplateAttributeLine(TimeStampedModel):
    """
    ``product.template.attribute.line`` — atributo aplicado a un producto.
    """

    #: ≙ la cabecera de la fuente
    #: (``odoo19c: addons/product/models/
    #: product_template_attribute_line.py:12-16``).
    _name = 'product.template.attribute.line'
    _rec_name = 'attribute_id'
    _rec_names_search = ['attribute_id', 'value_ids']
    _description = "Product Template Attribute Line"
    _order = 'sequence, attribute_id, id'

    product_tmpl_id = fields.Many2one(
        'product.ProductTemplate',
        db_column='product_tmpl_id',
        null=False, on_delete=models.CASCADE,
        related_name='attribute_lines',
        help_text='Plantilla de producto (Odoo product_tmpl_id).',
    )
    attribute_id = fields.Many2one(
        'product.ProductAttribute',
        null=False, on_delete=models.PROTECT,
        related_name='attribute_line_ids',
        help_text='Atributo (Odoo attribute_id).',
        db_column='attribute_id',
    )
    #: ≙ ``relation`` de la fuente (``:32-36``); las columnas son las que
    #: Odoo deriva de las dos tablas. El otro extremo,
    #: ``pav_attribute_line_ids`` de ``product.attribute.value``, es el
    #: accesor inverso.
    value_ids = fields.Many2many(
        'product.ProductAttributeValue',
        relation='product_attribute_value_product_template_attribute_line_rel',
        column1='product_template_attribute_line_id',
        column2='product_attribute_value_id',
        related_name='pav_attribute_line_ids',
        ondelete='restrict',
        help_text='Valores aplicables a este producto (Odoo value_ids).',
    )
    sequence = models.PositiveIntegerField(
        default=10,
        help_text='Orden (Odoo sequence).',
    )

    class Meta:
        db_table = 'product_template_attribute_line'
        ordering = ['sequence', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['product_tmpl_id', 'attribute_id'],
                name='unique_template_attribute',
            ),
        ]
        verbose_name = 'Línea de atributo de producto'
        verbose_name_plural = 'Líneas de atributo de producto'

    def __str__(self) -> str:
        return f'{self.product_tmpl_id} / {self.attribute_id}'
