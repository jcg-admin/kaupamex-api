"""``product.tag`` — etiqueta de producto.

Adaptación de ``addons/product/models/product_tag.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 62 líneas).

Dos M2M, no uno — y la razón está en el dominio
===============================================

La referencia declara **dos** relaciones separadas: a fichas
(``product_template_ids``) y a variantes (``product_product_ids``). Podría
parecer redundante —una variante ya cuelga de una ficha— pero el ``domain`` del
segundo lo explica:

    ``[('attribute_line_ids', '!=', False),
      ('product_tmpl_id', 'not in', product_template_ids)]``

Es decir: sólo se etiqueta una **variante suelta** cuando (a) su ficha tiene
atributos —si no, la variante *es* la ficha— y (b) su ficha **no** está ya
etiquetada. Etiquetar la ficha y una de sus variantes a la vez sería declarar
dos veces lo mismo y dejar ambiguo qué se muestra.

``product_ids`` es la **unión** de los dos: las variantes de las fichas
etiquetadas, más las variantes etiquetadas sueltas. Es ``compute`` sin
``store`` → propiedad aquí.

Qué NO se porta, con su medición
================================

- **``_search_product_ids``**: traduce un filtro sobre la unión a un ``OR`` de
  dominios del ORM de Odoo. En Django el equivalente es un ``Q()`` en el
  llamador; portar el traductor no aporta.
- **``copy_data``** (añade *"(copia)"* al duplicar): azúcar del cliente web.
"""
import fields
import models

from addons.base.models.image_mixin import ImageMixin
from addons.base.models.timestamped_mixin import TimeStampedModel
from addons.product.models.product_product import ProductProduct
from addons.product.models.product_template import ProductTemplate

#: Color por defecto de una etiqueta, verbatim de la fuente.
DEFAULT_TAG_COLOR = '#3C3C3C'


class ProductTag(ImageMixin, TimeStampedModel):
    """``product.tag`` — una etiqueta aplicable a fichas o a variantes."""

    name = fields.Char(max_length=255, unique=True, verbose_name='Nombre')
    sequence = fields.Integer(default=10, verbose_name='Secuencia')
    color = fields.Char(
        max_length=16, default=DEFAULT_TAG_COLOR, verbose_name='Color')
    visible_to_customers = fields.Boolean(
        default=True, verbose_name='Visible para el cliente')
    product_templates = fields.Many2many(
        ProductTemplate, blank=True,
        db_table='product_tag_product_template_rel',
        related_name='product_tag_ids', verbose_name='Fichas de producto',
    )
    product_variants = fields.Many2many(
        ProductProduct, blank=True,
        db_table='product_tag_product_product_rel',
        related_name='additional_product_tag_ids',
        verbose_name='Variantes de producto',
        help_text='Sólo variantes sueltas: su ficha debe tener atributos y NO '
                  'estar ya etiquetada. Ver el docstring del módulo.',
    )

    class Meta:
        db_table = 'product_tag'
        ordering = ['sequence', 'id']
        verbose_name = 'Etiqueta de producto'
        verbose_name_plural = 'Etiquetas de producto'
        constraints = [
            # ``_name_uniq`` de la fuente.
            models.UniqueConstraint(fields=['name'], name='product_tag_name_uniq'),
        ]

    def __str__(self):
        return self.name

    @property
    def product_ids(self):
        """``_compute_product_ids`` — la unión de las dos vías.

        Las variantes de las fichas etiquetadas **más** las variantes
        etiquetadas sueltas. Es una unión, no una concatenación: una variante
        alcanzada por las dos vías aparece una sola vez.
        """
        from_templates = ProductProduct.objects.filter(
            product_tmpl__in=self.product_templates.all())
        return (from_templates | self.product_variants.all()).distinct()
