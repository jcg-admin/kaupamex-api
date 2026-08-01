"""``product.combo.item`` — una **opción concreta** dentro de una elección.

Adaptación de ``odoo19c: addons/product/models/product_combo_item.py``
(``odoo-tools@622ddc2aa5``, 33 líneas, licencia ``LGPL-3`` declarada en
``addons/product/__manifest__.py``).

Cierra el par que ``product_combo.py`` dejó abierto
=====================================================

Siguiendo el ejemplo de la hamburguesería del docstring de ``ProductCombo``:
el menú es un ``product.template`` de tipo ``combo``; la **elección** es
"Bebida" (``product.combo``); y una **opción** es "refresco"
(``product.combo.item``). Este archivo es la tercera pieza.

Al aterrizar, el ``related_name='combo_item_ids'`` de abajo hace que
``ProductCombo.combo_item_count`` y ``ProductCombo.base_price`` dejen de
devolver 0 — ambos leen ese nombre y ya estaban escritos esperándolo.

Tres decisiones que no son mecánicas
====================================

**1. ``company`` es una columna real, no una propiedad.** La referencia la
declara ``related='combo_id.company_id'`` **con** ``store=True,
precompute=True``: es una denormalización deliberada, no un atajo de lectura.
Aquí importa el doble: ``ProductCombo.clean()`` compara
``item.company_id`` contra el suyo, y una propiedad ``company`` **no** expone
``company_id`` — el ``getattr(item, 'company_id', None)`` de aquel ``clean()``
devolvería ``None`` y la comprobación de coherencia quedaría desactivada en
silencio, pasando por verde sin haber mirado nada. Se persiste en ``save()``
desde la elección, que es el equivalente Django de ``precompute``.

**2. ``extra_price`` diverge a ``Monetary``.** La referencia usa
``fields.Float``; nuestro ``list_price`` (``product_template.py:156``),
``standard_price`` (``:162``) y ``price_extra``
(``product_template_attribute_value.py:30``) ya divergieron a ``Monetary``
(= ``DecimalField``). Como la referencia **suma** este campo a un precio
—``sale_order_line.py:789``: ``combo_prices[combo_id] + extra_price``—, un
``Float`` aquí daría ``TypeError: unsupported operand type(s) for +:
'decimal.Decimal' and 'float'`` en cuanto alguien lo sumara. La divergencia
no se elige: la fuerza la que ya se tomó aguas arriba.

**3. El ``domain`` es filtro de interfaz; la invariante es el ``clean()``.**
La referencia dice las dos cosas: ``domain=[('type', '!=', 'combo')]`` en el
campo (lo que el selector *ofrece*) y ``_check_product_id_no_combo`` como
``@api.constrains`` (lo que el servidor *acepta*). Django no tiene ``domain``,
así que sobrevive la mitad que importa — la del servidor. La otra es
responsabilidad del serializer que arme el selector.

Qué NO se porta, con su razón
=============================

- **``check_company=True``.** No hay atributo equivalente en Django. Su efecto
  —que la opción y su elección sean de la misma compañía— lo cubren la columna
  ``company`` denormalizada de arriba y el ``clean()`` de ``ProductCombo``.
- **``min_display_digits='Product Price'``.** Es precisión de *presentación*,
  no de almacenamiento. El ``decimal_places`` de la columna es lo que persiste.
- **La conversión de moneda de ``_get_combo_item_display_price``.** Vive en
  ``sale``, no aquí, y necesita ``ResCurrency._convert``, que no está portado
  (misma limitación anotada en ``product_combo.py``).
"""
import decimal

import fields
import models
from django.core.exceptions import ValidationError

from addons.base.models.res_company import ResCompany
from addons.base.models.timestamped_mixin import TimeStampedModel
from addons.product.models.product_combo import ProductCombo
from addons.product.models.product_product import ProductProduct

TYPE_COMBO = 'combo'


class ProductComboItem(TimeStampedModel):
    """``product.combo.item`` — una opción ofrecida dentro de una elección."""

    combo = fields.Many2one(
        ProductCombo, on_delete=models.CASCADE, db_index=True,
        related_name='combo_item_ids', verbose_name='Elección',
        help_text='La elección que ofrece esta opción. Al borrarla se borran '
                  'sus opciones (Odoo ondelete=cascade).',
    )
    product = fields.Many2one(
        ProductProduct, on_delete=models.PROTECT, db_index=True,
        related_name='combo_item_ids', verbose_name='Opción',
        help_text='Odoo string="Options", ondelete=restrict: no se borra un '
                  'producto que alguna elección todavía ofrece.',
    )
    extra_price = fields.Monetary(
        default=decimal.Decimal('0.00'),
        verbose_name='Precio adicional',
        help_text='Sobrecoste de elegir esta opción. En la referencia es '
                  'Float; aquí Monetary porque se suma a list_price, que ya '
                  'divergió a Monetary (ver el docstring del módulo).',
    )
    company = fields.Many2one(
        ResCompany, on_delete=models.CASCADE, null=True, blank=True,
        db_index=True, editable=False, related_name='combo_item_ids',
        verbose_name='Compañía',
        help_text='Denormalizada desde la elección (Odoo related + store=True '
                  '+ precompute=True). Se fija en save(), no se captura.',
    )

    class Meta:
        db_table = 'product_combo_item'
        ordering = ['combo_id', 'id']
        verbose_name = 'Opción de combo'
        verbose_name_plural = 'Opciones de combo'

    def __str__(self):
        return f'{self.combo} / {self.product}'

    def save(self, *args, **kwargs):
        """Propaga la compañía de la elección — el ``precompute`` de la fuente.

        La referencia la calcula antes de escribir la fila (``precompute=True``)
        para que el registro nazca con su compañía ya puesta, no en un segundo
        paso. Aquí ocurre lo mismo: la columna se llena en el ``save()`` que
        crea la fila.
        """
        if self.combo_id:
            self.company_id = self.combo.company_id
        super().save(*args, **kwargs)

    # === DERIVADOS ========================================================

    @property
    def lst_price(self):
        """``related='product_id.lst_price'`` — el precio de catálogo de la opción.

        Es lo que ``ProductCombo.base_price`` mira para tomar el mínimo. No
        incluye ``extra_price``: aquel es el sobrecoste de **elegir** esta
        opción, éste es lo que la opción vale por sí sola.
        """
        return self.product.lst_price

    @property
    def currency(self):
        """``related='product_id.currency_id'`` — la moneda de la opción.

        En la referencia ``product.product`` alcanza los campos de su ficha por
        ``_inherits`` (``product_product.py:19``); aquí la delegación es
        explícita, igual que ``type``, ``uom`` y ``company`` de
        ``ProductProduct``.
        """
        return getattr(self.product, 'currency', None)

    # === INVARIANTES ======================================================

    def clean(self):
        """``_check_product_id_no_combo`` — sin combos dentro de un combo.

        Un menú cuya opción es otro menú abriría una recursión sin fondo al
        prorratear el precio: ``base_price`` del combo exterior tendría que
        resolver el del interior, y así. La referencia lo corta en el primer
        nivel y no necesita más.

        Es la mitad que sobrevive del ``domain`` del campo — ver el docstring
        del módulo.
        """
        super().clean()
        if self.product_id and self.product.type == TYPE_COMBO:
            raise ValidationError(
                'Una elección de combo no puede ofrecer productos de tipo '
                'combo.')
