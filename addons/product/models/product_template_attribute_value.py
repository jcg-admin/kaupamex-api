"""
Modelo ``ProductTemplateAttributeValue`` — addon ``product`` (base del monolito
modular).

Adaptación fiel de Odoo ``product.template.attribute.value``
(``product/models/product_template_attribute_value.py:10-35``, verificado en 18
y 19): el valor de un atributo **para un producto concreto**, con su
``price_extra`` (sobreprecio o18:35 ≡ o19:35). Es la pieza que hace que una
opción (p. ej. talla XL) cueste ``+50`` sobre el precio base — lo que el
``chartsize`` original no modelaba de forma reutilizable.

Cobertura contra ``odoo19c`` (porte parcial declarado)
=======================================================

Portados: ``name`` (``related`` al valor del atributo, ``:24``, TASK-API-0482),
``price_extra`` y los dos enlaces, cuyo nombre aquí es ``line`` y
``attribute_value`` (la fuente dice ``attribute_line_id`` y
``product_attribute_value_id``); los atributos de clase ``_name``,
``_description`` y ``_order``. Pendientes, con sucesor **TASK-API-0493**: doce
métodos (``_check_valid_values``, ``_compute_display_name``,
``_filter_single_value_lines``, ``_get_combination_name``,
``_get_default_color``, ``_ids2str``, ``_is_from_single_value_line``,
``_only_active``, ``_without_no_variant_attributes``, ``create``, ``unlink``,
``write``), once campos (``ptav_active``, ``color``, ``display_type``,
``exclude_for``, ``html_color``, ``image``, ``is_custom``, ``currency_id``,
``product_tmpl_id``, ``attribute_id``, ``ptav_product_variant_ids``) y la
restricción ``_attribute_value_unique``, que aquí se llama
``unique_template_attribute_value``.
"""

from decimal import Decimal

import fields
import models

from addons.base.models import TimeStampedModel


class ProductTemplateAttributeValue(TimeStampedModel):
    """
    ``product.template.attribute.value`` — valor por-producto con price_extra.
    """

    _name = 'product.template.attribute.value'
    _description = "Product Template Attribute Value"
    _order = 'attribute_line_id, product_attribute_value_id, id'

    #: ≙ ``name`` (``odoo19c: :24``): sin columna, leído del valor del
    #: atributo.
    name = fields.Char('Value', related='attribute_value.name')
    line = fields.Many2one(
        'product.ProductTemplateAttributeLine',
        null=False, on_delete=models.CASCADE,
        related_name='template_values',
        help_text='Línea (Odoo attribute_line_id).',
    )
    attribute_value = fields.Many2one(
        'product.ProductAttributeValue',
        null=False, on_delete=models.PROTECT,
        related_name='template_values',
        help_text='Valor del atributo (Odoo product_attribute_value_id).',
    )
    price_extra = fields.Monetary(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Sobreprecio de esta opción (Odoo price_extra).',
    )

    class Meta:
        db_table = 'product_template_attribute_value'
        ordering = ['line', 'attribute_value', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['line', 'attribute_value'],
                name='unique_template_attribute_value',
            ),
        ]
        verbose_name = 'Valor de atributo por producto'
        verbose_name_plural = 'Valores de atributo por producto'

    def __str__(self) -> str:
        extra = f' (+{self.price_extra})' if self.price_extra else ''
        return f'{self.attribute_value.name}{extra}'
