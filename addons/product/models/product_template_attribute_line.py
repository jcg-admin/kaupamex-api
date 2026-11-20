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

import api
import fields
import models
from django.db import transaction

from addons.base.models import TimeStampedModel
from exceptions import UserError, ValidationError
from tools.misc import mute_logger
from tools.translate import _


class ProductTemplateAttributeLine(models.BaseModel, TimeStampedModel):
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

    #: ≙ ``active`` (``:18``).
    active = fields.Boolean(default=True)
    product_tmpl_id = fields.Many2one(
        'product.ProductTemplate',
        db_column='product_tmpl_id',
        null=False, on_delete=models.CASCADE,
        related_name='attribute_line_ids',
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
    #: ≙ ``value_count`` (``:38``), calculado almacenado.
    value_count = fields.Integer(compute='_compute_value_count', store=True)

    class Meta:
        db_table = 'product_template_attribute_line'
        ordering = ['sequence', 'attribute_id', 'id']
        verbose_name = 'Línea de atributo de producto'
        verbose_name_plural = 'Líneas de atributo de producto'

    def __str__(self) -> str:
        return f'{self.product_tmpl_id} / {self.attribute_id}'

    def _without_no_variant_attributes(self):
        """≙ ``_without_no_variant_attributes`` (``odoo19c:
        addons/product/models/product_template_attribute_line.py:262-263``).
        """
        return self.filtered(
            lambda ptal: ptal.attribute_id.create_variant != 'no_variant')

    def _is_configurable(self):
        """≙ ``_is_configurable`` (``:265-271``)."""
        self.ensure_one()
        return (
            len(self.value_ids) >= 2
            or self.attribute_id.display_type == 'multi'
            or self.value_ids.is_custom
        )

    @api.depends('value_ids')
    def _compute_value_count(self):
        """≙ ``_compute_value_count`` (``odoo19c:
        addons/product/models/product_template_attribute_line.py:44-47``).
        """
        for record in self:
            record.value_count = len(record.value_ids)

    @api.onchange('attribute_id')
    def _onchange_attribute_id(self):
        """≙ ``_onchange_attribute_id`` (``:49-58``)."""
        if self.attribute_id.create_variant == 'no_variant':
            self.value_ids = self.env['product.attribute.value'].search([
                ('attribute_id', '=', self.attribute_id.id),
            ])
        else:
            self.value_ids = self.value_ids.filtered(
                lambda pav: pav.attribute_id == self.attribute_id
            )

    @api.constrains('active', 'value_ids', 'attribute_id')
    def _check_valid_values(self):
        """≙ ``_check_valid_values`` (``:60-78``)."""
        for ptal in self:
            if ptal.active and not ptal.value_ids:
                raise ValidationError(_(
                    "The attribute %(attribute)s must have at least one value"
                    " for the product %(product)s.",
                    attribute=ptal.attribute_id.display_name,
                    product=ptal.product_tmpl_id.display_name,
                ))
            for pav in ptal.value_ids:
                if pav.attribute_id != ptal.attribute_id:
                    raise ValidationError(_(
                        "On the product %(product)s you cannot associate the"
                        " value %(value)s with the attribute %(attribute)s"
                        " because they do not match.",
                        product=ptal.product_tmpl_id.display_name,
                        value=pav.display_name,
                        attribute=ptal.attribute_id.display_name,
                    ))
        return True

    @api.model_create_multi
    def create(self, vals_list):
        """≙ ``create`` (``:80-115``): reactiva la línea archivada con la
        misma configuración en vez de crear otra, y sincroniza valores y
        variantes."""
        create_values = []
        activated_lines = self.env['product.template.attribute.line']
        for value in vals_list:
            vals = dict(value, active=value.get('active', True))
            # While not ideal for peformance, this search has to be done at
            # each step to exclude the lines that might have been activated
            # at a previous step.
            archived_ptal = self.search([
                ('active', '=', False),
                ('product_tmpl_id', '=', vals.pop('product_tmpl_id', 0)),
                ('attribute_id', '=', vals.pop('attribute_id', 0)),
            ], limit=1)
            if archived_ptal:
                # Write given `vals` in addition of `active` to ensure
                # `value_ids` or other fields passed to `create` are saved
                # too, but avoid updating the values and the variants until
                # all the expected lines are created/updated.
                archived_ptal.with_context(
                    update_product_template_attribute_values=False,
                ).write(vals)
                activated_lines += archived_ptal
            else:
                create_values.append(value)
        res = activated_lines + super().create(create_values)
        if self.env.context.get(
                'update_product_template_attribute_values', True):
            res._update_product_template_attribute_values()
        return res

    def write(self, vals):
        """≙ ``write`` (``:117-158``)."""
        values = vals
        if 'product_tmpl_id' in values:
            for ptal in self:
                if ptal.product_tmpl_id.id != values['product_tmpl_id']:
                    raise UserError(_(
                        "You cannot move the attribute %(attribute)s from the"
                        " product %(product_src)s to the product"
                        " %(product_dest)s.",
                        attribute=ptal.attribute_id.display_name,
                        product_src=ptal.product_tmpl_id.display_name,
                        product_dest=values['product_tmpl_id'],
                    ))

        if 'attribute_id' in values:
            for ptal in self:
                if ptal.attribute_id.id != values['attribute_id']:
                    raise UserError(_(
                        "On the product %(product)s you cannot transform the"
                        " attribute %(attribute_src)s into the attribute"
                        " %(attribute_dest)s.",
                        product=ptal.product_tmpl_id.display_name,
                        attribute_src=ptal.attribute_id.display_name,
                        attribute_dest=values['attribute_id'],
                    ))
        # Remove all values while archiving to make sure the line is clean
        # if it is ever activated again.
        if not values.get('active', True):
            values['value_ids'] = [fields.Command.clear()]
        res = super().write(values)
        if 'active' in values:
            self.env.flush_all()
            self.env['product.template'].invalidate_model(
                ['attribute_line_ids'])
        # If coming from `create`, no need to update the values and the
        # variants before all lines are created.
        if self.env.context.get(
                'update_product_template_attribute_values', True):
            self._update_product_template_attribute_values()
        return res

    def unlink(self):
        """≙ ``unlink`` (``:160-192``): borra o archiva cada línea en su
        propio savepoint (``env.cr.savepoint`` de la fuente es aquí
        ``transaction.atomic``)."""
        # Try to remove the values first to remove some potentially
        # blocking references.
        self.product_template_value_ids._only_active().unlink()
        # Keep a reference to the related templates before the deletion.
        templates = self.product_tmpl_id
        # Now delete or archive the lines.
        ptal_to_archive = self.env['product.template.attribute.line']
        for ptal in self:
            try:
                with transaction.atomic(), mute_logger('django.db.backends'):
                    super(ProductTemplateAttributeLine, ptal).unlink()
            except Exception:
                # We catch all kind of exceptions to be sure that the
                # operation doesn't fail.
                ptal_to_archive += ptal
        ptal_to_archive.action_archive()  # only writes if there are records
        # For archived lines the values are updated by the `write` above,
        # but templates that used unlinked lines need their variants.
        (templates - ptal_to_archive.product_tmpl_id)._create_variant_ids()
        return True

    def _update_product_template_attribute_values(self):
        """≙ ``_update_product_template_attribute_values`` (``:194-255``):
        borra los valores de plantilla que ya no están en ``value_ids``,
        reactiva los archivados que vuelven y crea los que faltan."""
        ProductTemplateAttributeValue = self.env[
            'product.template.attribute.value']
        ptav_to_create = []
        ptav_to_unlink = ProductTemplateAttributeValue
        for ptal in self:
            ptav_to_activate = ProductTemplateAttributeValue
            remaining_pav = set(ptal.value_ids.ids)
            for ptav in ptal.product_template_value_ids:
                if ptav.product_attribute_value_id.id not in remaining_pav:
                    # Remove values that existed but don't exist anymore,
                    # but ignore those that are already archived.
                    if ptav.ptav_active:
                        ptav_to_unlink += ptav
                else:
                    # Activate corresponding values that are archived.
                    remaining_pav.remove(ptav.product_attribute_value_id.id)
                    if not ptav.ptav_active:
                        ptav_to_activate += ptav

            ptav_groups = ProductTemplateAttributeValue._read_group([
                ('ptav_active', '=', False),
                ('product_tmpl_id', '=', ptal.product_tmpl_id.id),
                ('attribute_id', '=', ptal.attribute_id.id),
                ('product_attribute_value_id', 'in', list(remaining_pav)),
            ], groupby=['product_attribute_value_id'],
                aggregates=['id:recordset'])

            for pav, ptav in ptav_groups:
                ptav = ptav[0]
                ptav.write({'ptav_active': True, 'attribute_line_id': ptal.id})
                # If the value was marked for deletion, now keep it.
                ptav_to_unlink -= ptav
                remaining_pav.remove(pav.id)

            remaining_pav = self.env['product.attribute.value'].sudo().browse(
                sorted(remaining_pav))

            for pav in remaining_pav:
                ptav_to_create.append({
                    'product_attribute_value_id': pav.id,
                    'attribute_line_id': ptal.id,
                    'price_extra': pav.default_extra_price,
                })
            # Handle active at each step in case a following line might want
            # to re-use a value that was archived at a previous step.
            ptav_to_activate.write({'ptav_active': True})
            ptav_to_unlink.write({'ptav_active': False})
        if ptav_to_unlink:
            ptav_to_unlink.unlink()
        ProductTemplateAttributeValue.create(ptav_to_create)
        if self.env.context.get('create_product_product', True):
            self.product_tmpl_id._create_variant_ids()
