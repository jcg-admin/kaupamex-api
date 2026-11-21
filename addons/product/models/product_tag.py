"""``product.tag`` — etiqueta de producto.

Porte de ``odoo19c: addons/product/models/product_tag.py``: una etiqueta se
aplica a fichas (``product_template_ids``) o a variantes sueltas
(``product_product_ids``), y ``product_ids`` es la unión de las dos vías.
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-tag-basemodel.md``.

La variante suelta sólo se etiqueta cuando su ficha tiene atributos y no
está ya etiquetada: lo dice el ``domain`` de ``product_product_ids``.

Divergencia declarada: ``name`` no lleva ``translate=True``, como el resto
del grupo ``product``; el almacenamiento ``jsonb`` de los campos
traducibles es TASK-GEN-0060.
"""

import api
import fields
import models
from orm.domains import Domain
from orm.environments import env

from addons.base.models.timestamped_mixin import TimeStampedModel
from addons.product.models.product_product import ProductProduct
from addons.product.models.product_template import ProductTemplate


def _get_default_template_id():
    """≙ ``ProductTag._get_default_template_id`` (``odoo19c:
    addons/product/models/product_tag.py:12-13``): la ficha que el contexto
    nombra.

    DIVERGENCIA DE MECANISMO declarada, la de ``_get_default_color``: Django
    serializa un ``default`` callable por su ruta de import y lo resuelve
    sin instancia, así que queda a nivel de módulo, sin ``self``, y lee el
    entorno activo. Registrada en ``scripts/divergencias_declaradas.txt``.
    """
    environment = env()
    return environment['product.template'].browse(
        environment.context.get('product_template_id'))


def _get_default_variant_id():
    """≙ ``ProductTag._get_default_variant_id`` (``:15-16``); misma
    divergencia de mecanismo que ``_get_default_template_id``."""
    environment = env()
    return environment['product.product'].browse(
        environment.context.get('product_variant_id'))


class ProductTag(models.BaseModel, TimeStampedModel):
    """``product.tag`` — una etiqueta aplicable a fichas o a variantes."""

    #: ≙ la cabecera de la fuente (``:8-10``).
    _name = 'product.tag'
    _description = 'Product Tag'
    _order = 'sequence, id'

    name = fields.Char(string="Name", required=True, max_length=255)
    sequence = fields.Integer(default=10)
    color = fields.Char(string="Color", default='#3C3C3C', max_length=16)
    product_template_ids = fields.Many2many(
        ProductTemplate,
        string="Product Templates",
        relation='product_tag_product_template_rel',
        column1='product_tag_id',
        column2='product_template_id',
        related_name='product_tag_ids',
        default=_get_default_template_id,
        blank=True,
    )
    product_product_ids = fields.Many2many(
        ProductProduct,
        string="Product Variants",
        relation='product_tag_product_product_rel',
        column1='product_tag_id',
        column2='product_product_id',
        related_name='additional_product_tag_ids',
        domain="[('attribute_line_ids', '!=', False),"
               " ('product_tmpl_id', 'not in', product_template_ids)]",
        default=_get_default_variant_id,
        blank=True,
    )
    product_ids = fields.Many2many(
        ProductProduct,
        string='All Product Variants using this Tag',
        compute='_compute_product_ids', search='_search_product_ids',
        store=False, related_name='+',
    )
    visible_to_customers = fields.Boolean(
        string="Visible to customers",
        help="Whether the tag is displayed to customers.",
        default=True,
    )
    image = fields.Image(
        string="Image", max_width=200, max_height=200,
        upload_to='product/tags/', null=True, blank=True)

    class Meta:
        db_table = 'product_tag'
        ordering = ['sequence', 'id']
        verbose_name = 'Etiqueta de producto'
        verbose_name_plural = 'Etiquetas de producto'
        constraints = [
            # ≙ ``_name_uniq`` (``:44-47``).
            models.UniqueConstraint(
                fields=['name'], name='product_tag_name_uniq',
                violation_error_message='Tag name already exists!',
            ),
        ]

    def __str__(self):
        return self.name

    @api.depends('product_template_ids', 'product_product_ids')
    def _compute_product_ids(self):
        """≙ ``_compute_product_ids`` (``:49-52``)."""
        for tag in self:
            tag.product_ids = (
                tag.product_template_ids.product_variant_ids
                | tag.product_product_ids)

    def copy_data(self, default=None):
        """≙ ``copy_data`` (``:54-56``): la copia lleva «(copy)»."""
        vals_list = super().copy_data(default=default)
        return [dict(vals, name=self.env._("%s (copy)", tag.name))
                for tag, vals in zip(self, vals_list)]

    def _search_product_ids(self, operator, operand):
        """≙ ``_search_product_ids`` (``:58-62``)."""
        if operator in Domain.NEGATIVE_OPERATORS:
            return NotImplemented
        return ['|',
                ('product_template_ids.product_variant_ids', operator,
                 operand),
                ('product_product_ids', operator, operand)]
