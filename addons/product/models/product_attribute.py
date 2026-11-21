"""Modelo ``ProductAttribute`` — addon ``product`` (base del monolito
modular).

Porte de ``odoo19c: addons/product/models/product_attribute.py``: atributo
reutilizable entre productos (Color, Talla, Material…), con sus valores,
las líneas que lo usan y los productos que lo llevan. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-attribute-basemodel.md``.

Divergencia declarada: ``name`` no lleva ``translate=True``, como
``product.attribute.value`` en este árbol; el almacenamiento ``jsonb`` de
los campos traducibles es TASK-GEN-0060.
"""

import api
import fields
import models
from django.db.models import Q

from addons.base.models import TimeStampedModel
from exceptions import UserError
from tools.translate import _


class ProductAttribute(models.BaseModel, TimeStampedModel):
    """``product.attribute`` — atributo reutilizable entre productos."""

    #: ≙ la cabecera de la fuente
    #: (``odoo19c: addons/product/models/product_attribute.py:8-12``).
    _name = 'product.attribute'
    _description = "Product Attribute"
    # if you change this _order, keep it in sync with the method
    # `_sort_key_attribute_value` in `product.template`
    _order = 'sequence, id'

    name = fields.Char(string="Attribute", required=True, max_length=100)
    active = fields.Boolean(
        default=True,
        help="If unchecked, it will allow you to hide the attribute without"
             " removing it.",
    )
    create_variant = fields.Selection(
        selection=[
            ('always', 'Instantly'),
            ('dynamic', 'Dynamically'),
            ('no_variant', 'Never'),
        ],
        default='always',
        string="Variant Creation",
        help="- Instantly: All possible variants are created as soon as the"
             " attribute and its values are added to a product.\n"
             "- Dynamically: Each variant is created only when its"
             " corresponding attributes and values are added to a sales"
             " order.\n"
             "- Never: Variants are never created for the attribute.\n"
             "Note: this cannot be changed once the attribute is used on a"
             " product.",
        required=True,
        max_length=16)
    display_type = fields.Selection(
        selection=[
            ('radio', 'Radio'),
            ('pills', 'Pills'),
            ('select', 'Select'),
            ('color', 'Color'),
            ('multi', 'Multi-checkbox'),
            ('image', 'Image'),
        ],
        default='radio',
        required=True,
        help="The display type used in the Product Configurator.",
        max_length=16)
    sequence = fields.Integer(
        string="Sequence", help="Determine the display order", index=True,
        default=20)
    #: ≙ ``value_ids``, ``template_value_ids`` y ``attribute_line_ids``
    #: (``:51-62``): los declara el otro extremo de cada relación
    #: (``product.attribute.value.attribute_id``, el ``related`` de
    #: ``product.template.attribute.value`` y
    #: ``product.template.attribute.line.attribute_id``).
    product_tmpl_ids = fields.Many2many(
        'product.ProductTemplate',
        string="Related Products",
        compute='_compute_products',
        store=True,
        relation='product_attribute_product_template_rel',
        column1='product_attribute_id',
        column2='product_template_id',
        related_name='+',
        blank=True)
    number_related_products = fields.Integer(
        compute='_compute_number_related_products', store=False)

    class Meta:
        db_table = 'product_attribute'
        ordering = ['sequence', 'id']
        verbose_name = 'Atributo de producto'
        verbose_name_plural = 'Atributos de producto'
        constraints = [
            # ≙ ``_check_multi_checkbox_no_variant`` (``:14-17``).
            models.CheckConstraint(
                condition=(~Q(display_type='multi')
                           | Q(create_variant='no_variant')),
                name='product_attribute_check_multi_checkbox_no_variant',
                violation_error_message=(
                    'Multi-checkbox display type is not compatible with the'
                    ' creation of variants'),
            ),
        ]

    def __str__(self) -> str:
        return self.name

    # === COMPUTE METHODS === #

    @api.depends('product_tmpl_ids')
    def _compute_number_related_products(self):
        """≙ ``_compute_number_related_products`` (``:75-86``)."""
        res = {
            attribute.id: count
            for attribute, count in self.env[
                'product.template.attribute.line']._read_group(
                domain=[('attribute_id', 'in', self.ids),
                        ('product_tmpl_id.active', '=', 'True')],
                groupby=['attribute_id'],
                aggregates=['__count'],
            )
        }
        for pa in self:
            pa.number_related_products = res.get(pa.id, 0)

    @api.depends('attribute_line_ids.active',
                 'attribute_line_ids.product_tmpl_id')
    def _compute_products(self):
        """≙ ``_compute_products`` (``:88-99``)."""
        templates_by_attribute = {
            attribute.id: templates
            for attribute, templates in self.env[
                'product.template.attribute.line']._read_group(
                domain=[('attribute_id', 'in', self.ids)],
                groupby=['attribute_id'],
                aggregates=['product_tmpl_id:recordset']
            )
        }
        for pa in self:
            pa.with_context(active_test=False).product_tmpl_ids = (
                templates_by_attribute.get(pa.id, False))

    # === ONCHANGE METHODS === #

    @api.onchange('display_type')
    def _onchange_display_type(self):
        """≙ ``_onchange_display_type`` (``:103-106``)."""
        if (self.display_type == 'multi'
                and self.number_related_products == 0):
            self.create_variant = 'no_variant'

    # === CRUD METHODS === #

    def write(self, vals):
        """≙ ``write`` (``:110-134``): el modo de creación de variantes no
        cambia si el atributo ya está en un producto."""
        if 'create_variant' in vals:
            for pa in self:
                if (vals['create_variant'] != pa.create_variant
                        and pa.number_related_products):
                    raise UserError(_(
                        "You cannot change the Variants Creation Mode of the"
                        " attribute %(attribute)s because it is used on the"
                        " following products:\n%(products)s",
                        attribute=pa.display_name,
                        products=", ".join(
                            pa.product_tmpl_ids.mapped('display_name')),
                    ))
        invalidate = 'sequence' in vals and any(
            record.sequence != vals['sequence'] for record in self)
        res = super().write(vals)
        if invalidate:
            # prefetched o2m have to be resequenced
            # (eg. product.template: attribute_line_ids)
            self.env.flush_all()
            self.env.invalidate_all()
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_except_used_on_product(self):
        """≙ ``_unlink_except_used_on_product`` (``:136-145``)."""
        for pa in self:
            if pa.number_related_products:
                raise UserError(_(
                    "You cannot delete the attribute %(attribute)s because it"
                    " is used on the following products:\n%(products)s",
                    attribute=pa.display_name,
                    products=", ".join(
                        pa.product_tmpl_ids.mapped('display_name')),
                ))

    # === ACTION METHODS === #

    def action_archive(self):
        """≙ ``action_archive`` (``:149-155``)."""
        for attribute in self:
            if attribute.number_related_products:
                raise UserError(_(
                    "You cannot archive this attribute as there are still"
                    " products linked to it",
                ))
        return super().action_archive()

    @api.readonly
    def action_open_product_template_attribute_lines(self):
        """≙ ``action_open_product_template_attribute_lines``
        (``:157-165``)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Products"),
            'res_model': 'product.template.attribute.line',
            'view_mode': 'list,form',
            'domain': [('attribute_id', '=', self.id),
                       ('product_tmpl_id.active', '=', 'True')],
        }

    # === TOOLING === #

    def _without_no_variant_attributes(self):
        """≙ ``_without_no_variant_attributes`` (``:167-168``)."""
        return self.filtered(lambda pa: pa.create_variant != 'no_variant')
