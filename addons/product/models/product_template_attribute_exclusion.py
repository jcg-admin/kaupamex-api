"""
Modelo ``ProductTemplateAttributeExclusion`` — addon ``product``.

Adaptación fiel de Odoo ``product.template.attribute.exclusion``
(``odoo19c: addons/product/models/product_template_attribute_exclusion.py:
6-47``, LGPL-3): un valor de atributo de una plantilla que excluye otros
valores; la generación de variantes descarta las combinaciones que los
reúnen. Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/
designs/product-template-variant-generation.md``.
"""

import api
import fields
import models

from addons.base.models import TimeStampedModel


class ProductTemplateAttributeExclusion(models.BaseModel, TimeStampedModel):
    """``product.template.attribute.exclusion`` — regla de exclusión."""

    _name = 'product.template.attribute.exclusion'
    _description = "Product Template Attribute Exclusion"
    _order = 'product_tmpl_id, id'

    #: ≙ ``product_template_attribute_value_id`` (``:11-15``); su inverso es
    #: ``exclude_for`` de ``product.template.attribute.value``.
    product_template_attribute_value_id = fields.Many2one(
        'product.ProductTemplateAttributeValue',
        string="Attribute Value",
        on_delete=models.CASCADE,
        null=True, blank=True,
        index=True,
        related_name='exclude_for',
        db_column='product_template_attribute_value_id',
    )
    product_tmpl_id = fields.Many2one(
        'product.ProductTemplate',
        string="Product Template",
        on_delete=models.CASCADE,
        null=False,
        index=True,
        related_name='+',
        db_column='product_tmpl_id',
    )
    #: ≙ ``value_ids`` (``:21-25``) con la relación de la fuente.
    value_ids = fields.Many2many(
        'product.ProductTemplateAttributeValue',
        relation='product_attr_exclusion_value_ids_rel',
        column1='product_template_attribute_exclusion_id',
        column2='product_template_attribute_value_id',
        string="Attribute Values",
        related_name='+',
    )

    class Meta:
        db_table = 'product_template_attribute_exclusion'
        ordering = ['product_tmpl_id', 'id']
        verbose_name = 'Exclusión de atributo de producto'
        verbose_name_plural = 'Exclusiones de atributo de producto'

    @api.model_create_multi
    def create(self, vals_list):
        """≙ ``create`` (``:27-31``): regenera las variantes."""
        exclusions = super().create(vals_list)
        exclusions.product_tmpl_id._create_variant_ids()
        return exclusions

    def unlink(self):
        """≙ ``unlink`` (``:33-38``)."""
        # Keep a reference to the related templates before the deletion.
        templates = self.product_tmpl_id
        res = super().unlink()
        templates._create_variant_ids()
        return res

    def write(self, vals):
        """≙ ``write`` (``:40-46``)."""
        templates = self.env['product.template']
        if 'product_tmpl_id' in vals:
            templates = self.product_tmpl_id
        res = super().write(vals)
        (templates | self.product_tmpl_id)._create_variant_ids()
        return res
