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

Qué NO se porta, con su medición
================================

- **``_compute_display_name`` con ``show_variant_name``**: cambia el nombre
  visible según una clave de contexto del cliente web de Odoo. El nombre
  compuesto —``código para: variante``— sí se porta como propiedad; lo que no
  se porta es que dependa del contexto de la petición.
"""
import fields
import models
from django.core.exceptions import ValidationError

from addons.base.models.res_company import ResCompany
from addons.base.models.timestamped_mixin import TimeStampedModel
from addons.product.models.product_product import ProductProduct
from addons.uom.models.uom_uom import Uom


class ProductUom(TimeStampedModel):
    """``product.uom`` — variante + unidad adicional, con su código propio."""

    uom = fields.Many2one(
        Uom, on_delete=models.CASCADE, db_index=True,
        related_name='product_uom_ids', verbose_name='Unidad')
    product = fields.Many2one(
        ProductProduct, on_delete=models.CASCADE, db_index=True,
        related_name='product_uom_ids', verbose_name='Producto')
    barcode = fields.Char(
        max_length=64, db_index=True, verbose_name='Código de barras')
    company = fields.Many2one(
        ResCompany, on_delete=models.CASCADE, null=True, blank=True,
        related_name='product_uom_ids', verbose_name='Compañía')

    class Meta:
        db_table = 'product_uom'
        verbose_name = 'Empaquetado de producto'
        verbose_name_plural = 'Empaquetados de producto'
        constraints = [
            # ``_barcode_uniq``: un código sólo puede asignarse a un
            # empaquetado. La otra mitad —que tampoco lo use una variante— no
            # cabe en una constraint de tabla; va en ``clean()``.
            models.UniqueConstraint(
                fields=['barcode'], name='product_uom_barcode_uniq'),
        ]

    def __str__(self):
        return f'{self.barcode} para: {self.product}'

    def clean(self):
        """``_check_barcode_uniqueness`` — el código no lo usa ya una variante.

        Cierra la mitad que ``product_product.py`` dejó pendiente de este
        archivo. Ver el docstring del módulo: con GS1 el espacio de códigos es
        uno solo, así que comprobar sólo esta tabla dejaría pasar una colisión
        que el lector de códigos no puede desambiguar.
        """
        super().clean()
        if not self.barcode:
            return
        if ProductProduct.objects.filter(barcode=self.barcode).exists():
            raise ValidationError(
                'Una variante de producto ya usa ese código de barras.')
