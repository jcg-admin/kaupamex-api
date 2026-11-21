"""
Modelo ``ProductTemplateAttributeValue`` — addon ``product`` (base del monolito
modular).

Adaptación fiel de Odoo ``product.template.attribute.value``
(``odoo19c: addons/product/models/product_template_attribute_value.py:10-198``,
LGPL-3): el valor de un atributo **para un producto concreto**, con su
``price_extra``. Diseño: ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/ptav-complete.md``.

Cobertura contra ``odoo19c``
============================

Portados todos los campos y métodos. ``exclude_for`` (``:44-49``) es el
inverso que declara ``product.template.attribute.exclusion``.

``currency_id`` (``odoo19c:
addons/product/models/product_template_attribute_value.py:41``) es
``related`` a ``currency_id`` de la plantilla, como en la fuente.
"""

from decimal import Decimal
from random import randint

import api
import fields
import models
from django.db import transaction

from addons.base.models import TimeStampedModel
from exceptions import UserError, ValidationError
from tools.misc import mute_logger
from tools.translate import _


def _get_default_color():
    """≙ ``_get_default_color`` (``odoo19c: :18-19``). DIVERGENCIA DE
    MECANISMO declarada, la de ``product.attribute.value``: Django serializa
    un ``default`` callable por su ruta de import, así que queda a nivel de
    módulo y sin ``self``."""
    return randint(1, 11)


class ProductTemplateAttributeValue(models.BaseModel, TimeStampedModel):
    """
    ``product.template.attribute.value`` — valor por-producto con price_extra.
    """

    _name = 'product.template.attribute.value'
    _description = "Product Template Attribute Value"
    _order = 'attribute_line_id, product_attribute_value_id, id'

    #: ≙ ``ptav_active`` (``:21-23``): no ``active``, porque los valores se
    #: muestran siempre salvo en casos concretos.
    ptav_active = fields.Boolean(string="Active", default=True)
    #: ≙ ``name`` (``odoo19c: :24``): sin columna, leído del valor del
    #: atributo.
    name = fields.Char('Value', related='product_attribute_value_id.name')
    #: ≙ ``ondelete='cascade'`` (``:27-30``). La guarda que impide borrar un
    #: valor en uso es ``_unlink_except_used_on_product`` de
    #: ``product.attribute.value``; sin uso, el valor arrastra sus opciones.
    product_attribute_value_id = fields.Many2one(
        'product.ProductAttributeValue',
        db_column='product_attribute_value_id',
        null=False, on_delete=models.CASCADE,
        related_name='template_values',
        help_text='Valor del atributo (Odoo product_attribute_value_id).',
    )
    attribute_line_id = fields.Many2one(
        'product.ProductTemplateAttributeLine',
        db_column='attribute_line_id',
        null=False, on_delete=models.CASCADE,
        related_name='product_template_value_ids',
        help_text='Línea (Odoo attribute_line_id).',
    )
    price_extra = fields.Monetary(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Sobreprecio de esta opción (Odoo price_extra).',
    )
    #: ≙ ``product_tmpl_id`` y ``attribute_id`` (``:51-54``): ``related``
    #: almacenados e indexados, que la búsqueda por plantilla o por atributo
    #: lee sin pasar por la línea.
    #: ≙ ``currency_id`` (``odoo19c: addons/product/models/
    #: product_template_attribute_value.py:41``).
    currency_id = fields.Many2one(
        'base.ResCurrency',
        related='attribute_line_id.product_tmpl_id.currency_id',
        store=False, related_name='+',
    )
    product_tmpl_id = fields.Many2one(
        'product.ProductTemplate',
        related='attribute_line_id.product_tmpl_id',
        store=True, index=True,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='+',
        db_column='product_tmpl_id',
    )
    attribute_id = fields.Many2one(
        'product.ProductAttribute',
        related='attribute_line_id.attribute_id',
        store=True, index=True,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='+',
        db_column='attribute_id',
    )
    #: ≙ los ``related`` de presentación (``:58-62``).
    html_color = fields.Char(string="HTML Color Index",
                             related='product_attribute_value_id.html_color')
    is_custom = fields.Boolean(related='product_attribute_value_id.is_custom')
    display_type = fields.Selection(
        related='product_attribute_value_id.display_type')
    color = fields.Integer(string="Color", default=_get_default_color)
    image = fields.Image(related='product_attribute_value_id.image')

    class Meta:
        db_table = 'product_template_attribute_value'
        ordering = ['attribute_line_id', 'product_attribute_value_id', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['attribute_line_id', 'product_attribute_value_id'],
                # ≙ ``_attribute_value_unique`` (``:64-67``), nombre
                # conservado.
                name='_attribute_value_unique',
                violation_error_message=(
                    'Each value should be defined only once per attribute '
                    'per product.'),
            ),
        ]
        verbose_name = 'Valor de atributo por producto'
        verbose_name_plural = 'Valores de atributo por producto'

    def __str__(self) -> str:
        extra = f' (+{self.price_extra})' if self.price_extra else ''
        return f'{self.product_attribute_value_id.name}{extra}'

    @api.constrains('attribute_line_id', 'product_attribute_value_id')
    def _check_valid_values(self):
        """≙ ``_check_valid_values`` (``:69-79``)."""
        for ptav in self:
            if (ptav.ptav_active and ptav.product_attribute_value_id
                    not in ptav.attribute_line_id.value_ids):
                raise ValidationError(_(
                    "The value %(value)s is not defined for the attribute"
                    " %(attribute)s on the product %(product)s.",
                    value=ptav.product_attribute_value_id.display_name,
                    attribute=ptav.attribute_id.display_name,
                    product=ptav.product_tmpl_id.display_name,
                ))

    @api.model_create_multi
    def create(self, vals_list):
        """≙ ``create`` (``:81-87``)."""
        if any('ptav_product_variant_ids' in v for v in vals_list):
            # Force write on this relation from `product.product` to properly
            # trigger `_compute_combination_indices`.
            raise UserError(_(
                "You cannot update related variants from the values. Please"
                " update related values from the variants."))
        return super().create(vals_list)

    def write(self, vals):
        """≙ ``write`` (``:89-115``)."""
        values = vals
        if 'ptav_product_variant_ids' in values:
            # Force write on this relation from `product.product` to properly
            # trigger `_compute_combination_indices`.
            raise UserError(_(
                "You cannot update related variants from the values. Please"
                " update related values from the variants."))
        pav_in_values = 'product_attribute_value_id' in values
        product_in_values = 'product_tmpl_id' in values
        if pav_in_values or product_in_values:
            for ptav in self:
                if (pav_in_values and ptav.product_attribute_value_id.id
                        != values['product_attribute_value_id']):
                    raise UserError(_(
                        "You cannot change the value of the value %(value)s"
                        " set on product %(product)s.",
                        value=ptav.display_name,
                        product=ptav.product_tmpl_id.display_name,
                    ))
                if (product_in_values and ptav.product_tmpl_id.id
                        != values['product_tmpl_id']):
                    raise UserError(_(
                        "You cannot change the product of the value %(value)s"
                        " set on product %(product)s.",
                        value=ptav.display_name,
                        product=ptav.product_tmpl_id.display_name,
                    ))
        res = super().write(values)
        if 'exclude_for' in values:
            self.product_tmpl_id._create_variant_ids()
        return res

    def unlink(self):
        """≙ ``unlink`` (``:117-148``): quita de las variantes los valores de
        las líneas de un solo valor, borra o archiva las variantes, y borra o
        archiva cada valor en su propio savepoint (``env.cr.savepoint`` de la
        fuente es aquí ``transaction.atomic``)."""
        # Directly remove the values from the variants for lines that had
        # single value (counting also the values that are archived).
        single_values = self.filtered(
            lambda ptav: len(
                ptav.attribute_line_id.product_template_value_ids) == 1)
        for ptav in single_values:
            ptav.ptav_product_variant_ids.write({
                'product_template_attribute_value_ids': [
                    fields.Command.unlink(ptav.id)],
            })
        # Try to remove the variants before deleting to potentially remove
        # some blocking references.
        self.ptav_product_variant_ids._unlink_or_archive()
        # Now delete or archive the values.
        ptav_to_archive = self.env['product.template.attribute.value']
        for ptav in self:
            try:
                with transaction.atomic(), mute_logger('django.db.backends'):
                    super(ProductTemplateAttributeValue, ptav).unlink()
            except Exception:
                # We catch all kind of exceptions to be sure that the
                # operation doesn't fail.
                ptav_to_archive += ptav
        ptav_to_archive.write({'ptav_active': False})
        return True

    @api.depends('attribute_id')
    def _compute_display_name(self):
        """≙ ``_compute_display_name`` (``:150-157``): el nombre del valor
        confunde sin el de su atributo."""
        for value in self:
            value.display_name = f"{value.attribute_id.name}: {value.name}"

    def _only_active(self):
        """≙ ``_only_active`` (``:159-160``)."""
        return self.filtered(lambda ptav: ptav.ptav_active)

    def _without_no_variant_attributes(self):
        """≙ ``_without_no_variant_attributes`` (``:162-163``)."""
        return self.filtered(
            lambda ptav: ptav.attribute_id.create_variant != 'no_variant')

    def _ids2str(self):
        """≙ ``_ids2str`` (``:165-166``)."""
        return ','.join([str(i) for i in sorted(self.ids)])

    def _get_combination_name(self):
        """≙ ``_get_combination_name`` (``:168-172``): «Exclude values from
        single value lines or from no_variant attributes.»"""
        ptavs = self._without_no_variant_attributes().with_prefetch(
            self._prefetch_ids)
        ptavs = ptavs._filter_single_value_lines().with_prefetch(
            self._prefetch_ids)
        return ", ".join([ptav.name for ptav in ptavs])

    def _filter_single_value_lines(self):
        """≙ ``_filter_single_value_lines`` (``:174-187``): sin los valores
        de las líneas de un solo valor, contando los archivados si alguno de
        ``self`` lo está."""
        only_active = all(ptav.ptav_active for ptav in self)
        return self.filtered(
            lambda ptav: not ptav._is_from_single_value_line(only_active))

    def _is_from_single_value_line(self, only_active=True):
        """≙ ``_is_from_single_value_line`` (``:189-198``)."""
        self.ensure_one()
        all_values = self.attribute_line_id.product_template_value_ids
        if only_active:
            all_values = all_values._only_active()
        return len(all_values) == 1
