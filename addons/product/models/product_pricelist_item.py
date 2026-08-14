"""``product.pricelist.item`` — una regla de precio, y el cálculo entero.

Adaptación de ``addons/product/models/product_pricelist_item.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 684 líneas). Aquí está lo que decide
**qué precio sale**: a qué se aplica una regla, sobre qué base calcula, y en
qué orden se aplican descuento, redondeo, recargo y márgenes.

El orden de las operaciones, que es lo que no se puede reconstruir
=================================================================

``_compute_price`` en modo ``formula`` hace **cinco** pasos, y el orden es el
algoritmo:

1. ``price_limit = base_price`` — se guarda la base **antes** de tocarla;
2. descuento porcentual sobre la base;
3. **redondeo**, si hay ``price_round``;
4. **recargo** ``price_surcharge``, ya redondeado;
5. márgenes mínimo y máximo, medidos **contra ``price_limit``**, no contra el
   precio en curso.

Que los márgenes se midan contra la base y no contra el resultado es el punto
que se pierde al reescribirlo: un margen mínimo de 5 significa "nunca menos de
la base más 5", no "nunca menos del precio calculado más 5" —lo segundo sería
siempre cierto y la regla no haría nada—. Y el redondeo va **antes** del
recargo: al revés, un recargo de 0,99 desaparecería al redondear a la unidad.

Descuento y margen sobre coste son el mismo campo con signo contrario
=====================================================================

.. code-block:: python

   discount = self.price_discount if self.base != 'standard_price' \\
       else -self.price_markup

Cuando la base es el **coste**, no se descuenta: se **marca al alza**, y la
referencia lo expresa negando el margen para reusar la misma fórmula. Portar
sólo ``price_discount`` daría precios por debajo del coste en toda regla
basada en coste.

Los cuatro alcances, ordenados de específico a general
======================================================

``applied_on`` va con prefijo numérico —``0_product_variant``,
``1_product``, ``2_product_category``, ``3_global``— **para que el orden
alfabético sea el orden de precedencia**. No es decoración: el ``_order`` del
modelo empieza por ese campo, de modo que la primera regla que encaja es la
más específica. Se copian los prefijos verbatim; renombrarlos a algo "más
limpio" invertiría la precedencia sin ningún error.

El resto del ``_order`` —``min_quantity desc, categ_id desc, id desc``— sigue
el mismo principio: a igual alcance, gana la regla de cantidad mínima mayor
(la más exigente), y luego la categoría más profunda.

Qué NO se porta, con su medición
================================

- **La conversión de moneda** dentro de ``_compute_base_price``
  (``src_currency._convert(...)``): necesita la tasa vigente en una fecha, que
  vive en ``res.currency.rate``. ``ResCurrencyRate`` **está** portado, pero el
  conversor con fecha y compañía no; el cálculo devuelve el precio en la
  moneda del producto y **declara** cuál es, en vez de convertir mal.
- **La conversión de unidad** (``product_uom._compute_price(p, uom)``):
  ``Uom.compute_price`` sí está portado, así que se **usa** cuando el llamador
  pasa la unidad destino; lo que no se porta es sacarla del contexto de la
  petición, que este archivo no conoce.
- **``base='pricelist'`` recursivo**: una regla puede basarse en **otra
  tarifa**. Se porta el campo y el caso se resuelve delegando en la tarifa
  base a través del llamador; la recursión completa exige el selector de
  reglas de ``product_pricelist.py``, y montarla aquí duplicaría esa lógica.
- **``_compute_price_before_discount`` / ``name`` / ``price``**: los dos
  últimos son etiquetas calculadas para el formulario de Odoo.
"""
import fields
import models
from django.core.exceptions import ValidationError

from addons.base.models.timestamped_mixin import TimeStampedModel
from addons.product.models.product_category import ProductCategory
from addons.product.models.product_pricelist import ProductPricelist
from addons.product.models.product_product import ProductProduct
from addons.product.models.product_template import ProductTemplate
from tools.float_utils import float_round

APPLIED_VARIANT = '0_product_variant'
APPLIED_PRODUCT = '1_product'
APPLIED_CATEGORY = '2_product_category'
APPLIED_GLOBAL = '3_global'
#: ``applied_on`` — los prefijos numéricos son **precedencia**, no adorno:
#: el ``_order`` del modelo empieza por este campo, así que el orden
#: alfabético pone primero lo más específico. Verbatim de la fuente.
APPLIED_ON_CHOICES = [
    (APPLIED_VARIANT, 'Variante de producto'),
    (APPLIED_PRODUCT, 'Producto'),
    (APPLIED_CATEGORY, 'Categoría de producto'),
    (APPLIED_GLOBAL, 'Todos los productos'),
]

BASE_LIST_PRICE = 'list_price'
BASE_STANDARD_PRICE = 'standard_price'
BASE_PRICELIST = 'pricelist'
#: ``base`` — sobre qué se calcula, verbatim.
BASE_CHOICES = [
    (BASE_LIST_PRICE, 'Precio de venta'),
    (BASE_STANDARD_PRICE, 'Coste'),
    (BASE_PRICELIST, 'Otra tarifa'),
]

COMPUTE_FIXED = 'fixed'
COMPUTE_PERCENTAGE = 'percentage'
COMPUTE_FORMULA = 'formula'
#: ``compute_price`` — cómo se calcula, verbatim.
COMPUTE_PRICE_CHOICES = [
    (COMPUTE_PERCENTAGE, 'Descuento'),
    (COMPUTE_FORMULA, 'Fórmula'),
    (COMPUTE_FIXED, 'Precio fijo'),
]


class ProductPricelistItem(TimeStampedModel):
    """``product.pricelist.item`` — una regla dentro de una tarifa."""

    pricelist = fields.Many2one(
        ProductPricelist, on_delete=models.CASCADE, db_index=True,
        related_name='item_ids', verbose_name='Tarifa')
    applied_on = fields.Selection(
        max_length=32, choices=APPLIED_ON_CHOICES, default=APPLIED_GLOBAL,
        verbose_name='Se aplica a',
        help_text='El prefijo numérico ES la precedencia — ver el docstring '
                  'del módulo.',
    )
    categ = fields.Many2one(
        ProductCategory, on_delete=models.CASCADE, null=True, blank=True,
        related_name='pricelist_item_ids', verbose_name='Categoría')
    product_tmpl = fields.Many2one(
        ProductTemplate, on_delete=models.CASCADE, null=True, blank=True,
        related_name='pricelist_rule_ids', verbose_name='Producto')
    product = fields.Many2one(
        ProductProduct, on_delete=models.CASCADE, null=True, blank=True,
        related_name='pricelist_rule_ids', verbose_name='Variante')
    min_quantity = fields.Float(
        default=0, verbose_name='Cantidad mínima',
        help_text='A igual alcance gana la regla de mínimo mayor: la más '
                  'exigente.',
    )
    date_start = fields.Datetime(
        null=True, blank=True, verbose_name='Fecha de inicio')
    date_end = fields.Datetime(
        null=True, blank=True, verbose_name='Fecha de fin')
    base = fields.Selection(
        max_length=32, choices=BASE_CHOICES, default=BASE_LIST_PRICE,
        verbose_name='Basado en')
    base_pricelist = fields.Many2one(
        ProductPricelist, on_delete=models.PROTECT, null=True, blank=True,
        related_name='derived_item_ids', verbose_name='Otra tarifa')
    compute_price = fields.Selection(
        max_length=16, choices=COMPUTE_PRICE_CHOICES, default=COMPUTE_FIXED,
        db_index=True, verbose_name='Cálculo del precio')
    fixed_price = fields.Monetary(
        max_digits=16, decimal_places=2, default=0, verbose_name='Precio fijo')
    percent_price = fields.Float(default=0, verbose_name='Descuento (%)')
    price_discount = fields.Float(default=0, verbose_name='Descuento de fórmula (%)')
    price_markup = fields.Float(
        default=0, verbose_name='Margen sobre coste (%)',
        help_text='Se usa EN LUGAR del descuento cuando la base es el coste; '
                  'la fórmula lo aplica como descuento negativo.',
    )
    price_round = fields.Float(
        default=0, verbose_name='Redondeo',
        help_text='Se aplica ANTES del recargo — ver el docstring del módulo.')
    price_surcharge = fields.Monetary(
        max_digits=16, decimal_places=2, default=0, verbose_name='Recargo')
    price_min_margin = fields.Monetary(
        max_digits=16, decimal_places=2, default=0, verbose_name='Margen mínimo',
        help_text='Se mide contra la BASE, no contra el precio en curso.')
    price_max_margin = fields.Monetary(
        max_digits=16, decimal_places=2, default=0, verbose_name='Margen máximo',
        help_text='Se mide contra la BASE, no contra el precio en curso.')

    class Meta:
        db_table = 'product_pricelist_item'
        ordering = ['applied_on', '-min_quantity', '-categ', '-id']
        verbose_name = 'Regla de tarifa'
        verbose_name_plural = 'Reglas de tarifa'

    def __str__(self):
        return f'{self.pricelist_id}/{self.applied_on}#{self.pk}'

    def clean(self):
        """El alcance declarado y el campo que lo concreta tienen que casar.

        La referencia lo resuelve ocultando campos en el formulario; aquí se
        valida, que es la versión de servidor: una regla ``1_product`` sin
        producto no se aplica a nada y es indistinguible de una global mal
        guardada.
        """
        super().clean()
        required = {
            APPLIED_VARIANT: ('product_id', 'una variante'),
            APPLIED_PRODUCT: ('product_tmpl_id', 'un producto'),
            APPLIED_CATEGORY: ('categ_id', 'una categoría'),
        }.get(self.applied_on)
        if required and not getattr(self, required[0], None):
            raise ValidationError(
                'Una regla con alcance %s debe indicar %s.'
                % (self.applied_on, required[1])
            )
        if self.base == BASE_PRICELIST and not self.base_pricelist_id:
            raise ValidationError(
                'Una regla basada en otra tarifa debe indicar cuál.')
        if (self.date_start and self.date_end
                and self.date_start > self.date_end):
            raise ValidationError(
                'La fecha de inicio no puede ser posterior a la de fin.')

    # === APLICABILIDAD ====================================================

    def matches(self, product, quantity=0, date=None):
        """¿Esta regla aplica a ``product`` en esta cantidad y fecha?

        Comprueba las tres condiciones que la referencia usa al seleccionar:
        alcance, cantidad mínima y ventana de fechas. La **precedencia** entre
        reglas que aplican la da el ``ordering``, no este método.
        """
        if quantity < self.min_quantity:
            return False
        if date is not None:
            if self.date_start and date < self.date_start:
                return False
            if self.date_end and date > self.date_end:
                return False

        if self.applied_on == APPLIED_GLOBAL:
            return True
        if self.applied_on == APPLIED_VARIANT:
            return getattr(product, 'pk', None) == self.product_id
        if self.applied_on == APPLIED_PRODUCT:
            tmpl = getattr(product, 'product_tmpl_id', None) \
                or getattr(product, 'pk', None)
            return tmpl == self.product_tmpl_id
        if self.applied_on == APPLIED_CATEGORY:
            categ = getattr(product, 'categ', None)
            # Una regla de categoría alcanza a toda la rama, no sólo al nodo:
            # la ruta materializada de ``product.category`` lo resuelve sin
            # subir la cadena.
            if categ is None or self.categ is None:
                return False
            return categ.parent_path.startswith(self.categ.parent_path)
        return False

    # === CÁLCULO ==========================================================

    def base_price_for(self, product):
        """``_compute_base_price`` — el precio sobre el que calcula la regla.

        Devuelve ``(precio, moneda)``. La conversión de moneda **no** se hace
        aquí: se declara en cuál está para que el llamador convierta con la
        tasa de la fecha que corresponda (ver el docstring del módulo).
        """
        if self.base == BASE_STANDARD_PRICE:
            return float(product.standard_price or 0), product.cost_currency
        if self.base == BASE_PRICELIST and self.base_pricelist_id:
            # La recursión completa la resuelve el selector de reglas; aquí se
            # declara el punto de entrada en vez de duplicarlo.
            raise NotImplementedError(
                'Una regla basada en otra tarifa la resuelve el selector de '
                'reglas de product_pricelist, no esta regla.'
            )
        return float(product.lst_price or 0), product.currency

    def compute(self, product, quantity=1, to_uom=None):
        """``_compute_price`` — el precio unitario según esta regla.

        Los cinco pasos del modo ``formula``, en el orden de la fuente. Ver el
        docstring del módulo: el orden **es** el algoritmo, y los márgenes se
        miden contra la base, no contra el precio en curso.
        """
        def convert(amount):
            """Los importes de la regla van en la unidad del producto."""
            product_uom = getattr(product, 'uom', None)
            if to_uom is None or product_uom is None or product_uom == to_uom:
                return float(amount)
            return product_uom.compute_price(float(amount), to_uom)

        if self.compute_price == COMPUTE_FIXED:
            return convert(self.fixed_price)

        base_price, _currency = self.base_price_for(product)

        if self.compute_price == COMPUTE_PERCENTAGE:
            return base_price - (base_price * (self.percent_price / 100)) or 0.0

        # === formula ===
        price_limit = base_price          # 1. la base, antes de tocarla
        discount = (
            self.price_discount if self.base != BASE_STANDARD_PRICE
            else -self.price_markup       # sobre coste se marca al alza
        )
        price = base_price - (base_price * (discount / 100))   # 2. descuento

        if self.price_round:              # 3. redondeo, ANTES del recargo
            price = float_round(price, precision_rounding=self.price_round)

        if self.price_surcharge:          # 4. recargo
            price += convert(self.price_surcharge)

        if self.price_min_margin:         # 5. márgenes contra la BASE
            price = max(price, price_limit + convert(self.price_min_margin))
        if self.price_max_margin:
            price = min(price, price_limit + convert(self.price_max_margin))

        return price
