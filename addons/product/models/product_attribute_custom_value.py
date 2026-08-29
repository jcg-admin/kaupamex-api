"""Modelo ``ProductAttributeCustomValue`` — addon ``product``.

Adaptación de ``odoo19c: product/models/product_attribute_custom_value.py``
(LGPL-3 según su ``__manifest__.py``: copia + adaptación con atribución).

Qué modela: el texto que el comprador escribe cuando una opción del producto
lo admite. Un atributo con ``is_custom`` no ofrece una lista cerrada de
valores — ofrece un hueco: el grabado de una placa, la leyenda de una
camiseta, la medida exacta de un corte. El valor elegido sigue siendo el de
``product.template.attribute.value``; lo que este modelo guarda es **lo que
el comprador puso en ese hueco**.

*Métrica:* entradas del cuerpo de ``class ProductAttributeCustomValue``,
contadas por AST sobre la fuente — **3** campos, **1** método y **3**
atributos de clase.
*Ciega a:* lo que otros addons le cuelgan por ``_inherit``. ``sale`` le añade
``sale_order_line_id`` y su restricción de unicidad, y eso vive en
``addons/sale/models/product_product.py``, que es donde la referencia lo
declara.

**Se portan 3 de 3 campos y 1 de 1 método.**

Divergencia de mecanismo declarada
===================================

``name`` (``odoo19c: :11``)
    La fuente lo declara ``compute='_compute_name'`` **sin** ``store=True``:
    es un campo sin columna. Aquí se declara con :class:`fields.NonStored`,
    que es el equivalente construido de ese ``store=False``
    (``src/orm/fields_nonstored.py``). El cuerpo del cómputo va verbatim.

``custom_product_template_attribute_value_id`` (``:12``)
    Se porta con el símbolo **verbatim de la fuente** —con su sufijo ``_id``—
    y ``db_column`` fijando la columna al mismo nombre. Es la **forma C** que
    ADR-029 declara gobernante: sin el ``db_column``, Django nombraría la
    columna ``…_id_id``; sin el sufijo en el símbolo, el puerto se apartaría
    del nombre que la referencia declara.

``ondelete='restrict'`` (``:17``)
    Se porta como ``on_delete=models.PROTECT``, que es el mismo contrato: el
    motor rehúsa borrar el valor de atributo mientras alguien lo haya
    personalizado.
"""
import fields
import models

from addons.base.models import TimeStampedModel


def _compute_name(record) -> str:
    """Cuerpo de ``_compute_name`` (``odoo19c: :20-25``).

    Cuerpo fiel: el nombre es el texto que el comprador escribió, y si el
    valor de atributo tiene nombre para mostrar, se antepone separado por dos
    puntos. La fuente lee ``display_name``; aquí el equivalente es el
    ``__str__`` del valor, que es lo que ese ``display_name`` produce.
    """
    name = (record.custom_value or '').strip()
    value = record.custom_product_template_attribute_value_id
    if value is not None and str(value):
        name = f'{value}: {name}'
    return name


class ProductAttributeCustomValue(TimeStampedModel):
    """``product.attribute.custom.value`` — el texto libre de una opción."""

    _name = 'product.attribute.custom.value'
    _description = "Product Attribute Custom Value"
    _order = 'custom_product_template_attribute_value_id, id'

    custom_product_template_attribute_value_id = fields.Many2one(
        'product.ProductTemplateAttributeValue', on_delete=models.PROTECT,
        db_column='custom_product_template_attribute_value_id',
        related_name='custom_values', verbose_name='Valor del atributo',
        help_text='Odoo custom_product_template_attribute_value_id. El valor '
                  'de atributo que admite texto libre (is_custom).',
    )
    custom_value = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Valor personalizado',
        help_text='Odoo custom_value. Lo que el comprador escribió.',
    )
    # ``name`` es el campo SIN columna de la fuente (``compute`` sin ``store``).
    # ``fields.NonStored`` es el equivalente construido de ese ``store=False``.
    name = fields.NonStored(default=_compute_name)

    class Meta:
        db_table = 'product_attribute_custom_value'
        # ≙ ``_order = 'custom_product_template_attribute_value_id, id'``
        # (``odoo19c: :10``). Sin ORDER BY el motor devuelve las filas en el
        # orden que le convenga, y PostgreSQL no promete el de la PK.
        ordering = ['custom_product_template_attribute_value_id', 'id']
        verbose_name = 'Valor personalizado de atributo'
        verbose_name_plural = 'Valores personalizados de atributo'

    def __str__(self) -> str:
        return self.name

