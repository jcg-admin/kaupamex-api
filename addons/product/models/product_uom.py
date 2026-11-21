"""``product.uom`` — el código de barras de un empaquetado.

Adaptación de ``addons/product/models/product_uom.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 32 líneas). Une una variante con una
unidad de medida **adicional** y le da su propio código de barras: la caja de
12 tiene un código distinto de la unidad suelta.

El espacio de códigos es **uno solo**, compartido con las variantes
===================================================================

La referencia lo dice en el comentario de ``_check_barcode_uniqueness`` y es la
razón de ser de esta comprobación: *"con la nomenclatura GS1, productos y
empaquetados usan el mismo patrón"*. Un lector de códigos no sabe si lo que
escanea es una unidad o una caja — sólo ve el número.

Por eso la unicidad **no** basta dentro de esta tabla: hay que comprobar
también que ningún ``product.product`` use ya ese código. Se portan las dos
mitades, y esto **cierra** la que ``product_product.py`` dejó anotada como
pendiente de este archivo.

Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-uom-basemodel.md``.
"""

import api
import fields
import models

from addons.base.models.res_company import ResCompany
from addons.base.models.timestamped_mixin import TimeStampedModel
from addons.product.models.product_product import ProductProduct
from addons.uom.models.uom_uom import Uom
from exceptions import ValidationError
from orm.environments import env
from tools.translate import _


def _default_company():
    """≙ ``default=lambda self: self.env.company``
    (``odoo19c: addons/product/models/product_uom.py:16``): la empresa
    activa, o ninguna si no hay empresa en contexto."""
    return env().company


class ProductUom(models.BaseModel, TimeStampedModel):
    """``product.uom`` — variante + unidad adicional, con su código propio."""

    #: ≙ la cabecera de la fuente
    #: (``odoo19c: addons/product/models/product_uom.py:9-11``).
    _name = 'product.uom'
    _description = 'Link between products and their UoMs'
    _rec_name = 'barcode'

    uom_id = fields.Many2one(
        Uom,
        db_column='uom_id',
        null=False, on_delete=models.CASCADE,
        db_index=True,
        related_name='product_uom_ids',
        verbose_name='Unidad',
    )
    product_id = fields.Many2one(
        ProductProduct,
        db_column='product_id',
        null=False, on_delete=models.CASCADE,
        db_index=True,
        related_name='product_uom_ids',
        verbose_name='Producto',
    )
    barcode = fields.Char(
        index='btree_not_null', required=True, copy=False, max_length=64,
        verbose_name='Código de barras',
    )
    company_id = fields.Many2one(
        ResCompany,
        db_column='company_id',
        default=_default_company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='product_uom_ids',
        verbose_name='Compañía',
    )

    class Meta:
        db_table = 'product_uom'
        verbose_name = 'Empaquetado de producto'
        verbose_name_plural = 'Empaquetados de producto'
        constraints = [
            # ≙ ``_barcode_uniq`` (``odoo19c: :18``): un código sólo puede
            # asignarse a un empaquetado. La otra mitad —que tampoco lo use
            # una variante— es ``_check_barcode_uniqueness``.
            models.UniqueConstraint(
                fields=['barcode'], name='product_uom_barcode_uniq',
                violation_error_message=(
                    'A barcode can only be assigned to one packaging.'),
            ),
        ]

    def __str__(self):
        return self.display_name or self.barcode or ''

    @api.constrains('barcode')
    def _check_barcode_uniqueness(self):
        """≙ ``_check_barcode_uniqueness`` (``odoo19c:
        addons/product/models/product_uom.py:20-26``).

        With GS1 nomenclature, products and packagings use the same pattern.
        Therefore, we need to ensure the uniqueness between products'
        barcodes and packagings' ones."""
        domain = [('barcode', 'in', [
            b for b in self.mapped('barcode') if b])]
        if self.env['product.product'].search_count(domain, limit=1):
            raise ValidationError(_("A product already uses the barcode"))

    def _compute_display_name(self):
        """≙ ``_compute_display_name`` (``:28-32``): con
        ``show_variant_name`` en el contexto, el código y la variante."""
        if not self.env.context.get('show_variant_name'):
            return super()._compute_display_name()
        for record in self:
            record.display_name = (
                f"{record.barcode} for: {record.product_id.display_name}")
