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
  ``Uom._compute_price`` sí está portado, así que se **usa** cuando el llamador
  pasa la unidad destino; lo que no se porta es sacarla del contexto de la
  petición, que este archivo no conoce.
- **``base='pricelist'`` recursivo**: una regla puede basarse en **otra
  tarifa**. Se porta el campo y el caso se resuelve delegando en la tarifa
  base a través del llamador; la recursión completa exige el selector de
  reglas de ``product_pricelist.py``, y montarla aquí duplicaría esa lógica.
- **``_compute_price_before_discount`` / ``name`` / ``price``**: los dos
  últimos son etiquetas calculadas para el formulario de Odoo.
"""

import api
import fields
import models
from django.core.exceptions import ValidationError

from addons.base.models.res_company import ResCompany
from addons.base.models.res_currency import ResCurrency
from addons.base.models.timestamped_mixin import TimeStampedModel
from addons.product.models.product_category import ProductCategory
from addons.product.models.product_pricelist import ProductPricelist
from addons.product.models.product_product import ProductProduct
from addons.product.models.product_template import ProductTemplate
from orm.environments import env
from tools.float_utils import float_round
from tools.translate import _

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


def _default_pricelist_id():
    """≙ ``_default_pricelist_id`` (``odoo19c: addons/product/models/
    product_pricelist_item.py:14-17``): la primera tarifa sin empresa o de
    la empresa activa. Callable de módulo: un ``default`` de Django no
    recibe ``self``."""
    company = env().company
    pricelist = env()['product.pricelist'].search([
        '|', ('company_id', '=', False),
        ('company_id', '=', company.pk if company is not None else False),
    ], limit=1)
    return pricelist.id or None


class ProductPricelistItem(models.BaseModel, TimeStampedModel):
    """``product.pricelist.item`` — una regla dentro de una tarifa."""

    #: ≙ la cabecera de la fuente
    #: (``odoo19c: addons/product/models/product_pricelist_item.py:9-12``).
    _name = 'product.pricelist.item'
    _description = "Pricelist Rule"
    _order = "applied_on, min_quantity desc, categ_id desc, id desc"
    _check_company_auto = True

    #: ≙ ``pricelist_id`` (``:19-26``). ``required=False`` como la fuente:
    #: los flujos estándar no manejan reglas sin tarifa, algunos módulos sí.
    pricelist_id = fields.Many2one(
        ProductPricelist,
        string="Pricelist",
        db_column='pricelist_id',
        on_delete=models.CASCADE, null=True, blank=True,
        db_index=True,
        default=_default_pricelist_id,
        related_name='+',
    )
    #: ≙ ``is_pricelist_required`` (``:28``).
    is_pricelist_required = fields.Boolean(
        compute='_compute_is_pricelist_required')

    #: ≙ ``company_id`` (``:30``).
    company_id = fields.Many2one(
        ResCompany,
        compute='_compute_company_id', store=True,
        db_column='company_id',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pricelist_item_ids',
    )
    #: ≙ ``currency_id`` (``:31``).
    currency_id = fields.Many2one(
        ResCurrency,
        compute='_compute_currency_id', store=True,
        db_column='currency_id',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pricelist_item_ids',
    )

    date_start = fields.Datetime(
        string="Start Date", null=True, blank=True,
        help="Starting datetime for the pricelist item validation\n"
             "The displayed value depends on the timezone set in your "
             "preferences.")
    date_end = fields.Datetime(
        string="End Date", null=True, blank=True,
        help="Ending datetime for the pricelist item validation\n"
             "The displayed value depends on the timezone set in your "
             "preferences.")

    min_quantity = fields.Float(
        string="Min. Quantity",
        default=0,
        digits='Product Unit',
        help="For the rule to apply, bought/sold quantity must be greater "
             "than or equal to the minimum quantity specified in this "
             "field.\nExpressed in the default unit of measure of the "
             "product.")

    applied_on = fields.Selection(
        selection=APPLIED_ON_CHOICES,
        string="Apply On",
        default=APPLIED_GLOBAL,
        required=True,
        max_length=32,
        help="Pricelist Item applicable on selected option")

    #: ≙ ``display_applied_on`` (``:61-68``).
    display_applied_on = fields.Selection(
        selection=[
            ('1_product', "Product"),
            ('2_product_category', "Category"),
        ],
        default='1_product',
        required=True,
        max_length=32,
        help="Pricelist Item applicable on selected option")

    categ_id = fields.Many2one(
        ProductCategory,
        string="Category",
        on_delete=models.CASCADE, null=True, blank=True,
        db_column='categ_id',
        related_name='pricelist_item_ids',
        help="Specify a product category if this rule only applies to "
             "products belonging to this category or its children "
             "categories. Keep empty otherwise.")
    product_tmpl_id = fields.Many2one(
        ProductTemplate,
        string="Product",
        on_delete=models.CASCADE, null=True, blank=True,
        check_company=True, db_index=True,
        db_column='product_tmpl_id',
        related_name='pricelist_rule_ids',
        help="Specify a template if this rule only applies to one product "
             "template. Keep empty otherwise.")
    product_id = fields.Many2one(
        ProductProduct,
        string="Variant",
        on_delete=models.CASCADE, null=True, blank=True,
        check_company=True, db_index=True,
        domain="[('product_tmpl_id', '=', product_tmpl_id)]",
        db_column='product_id',
        related_name='pricelist_rule_ids',
        help="Specify a product if this rule only applies to one product. "
             "Keep empty otherwise.")
    #: ≙ ``product_uom_name`` (``:87``): ``related='product_tmpl_id.
    #: uom_name'``, y ``uom_name`` es a su vez ``related='uom_id.name'``
    #: (``odoo19c: addons/product/models/product_template.py``); aquí la
    #: plantilla lo expone como propiedad, así que se recorre la cadena.
    product_uom_name = fields.Char(related='product_tmpl_id.uom_id.name')
    #: ≙ ``product_variant_count`` (``:88``).
    product_variant_count = fields.Integer(
        related='product_tmpl_id.product_variant_count')

    base = fields.Selection(
        selection=BASE_CHOICES,
        string="Based on",
        default=BASE_LIST_PRICE,
        required=True,
        max_length=32,
        help="Base price for computation.\n"
             "Sales Price: The base price will be the Sales Price.\n"
             "Cost Price: The base price will be the cost price.\n"
             "Other Pricelist: Computation of the base price based on "
             "another Pricelist.")
    base_pricelist_id = fields.Many2one(
        ProductPricelist,
        string='Other Pricelist',
        check_company=True,
        db_column='base_pricelist_id',
        on_delete=models.PROTECT, null=True, blank=True,
        related_name='derived_item_ids',
    )

    compute_price = fields.Selection(
        selection=COMPUTE_PRICE_CHOICES,
        help="Use the discount rules and activate the discount settings"
             " in order to show discount to customer.",
        db_index=True, default=COMPUTE_FIXED, required=True,
        max_length=16,
    )

    fixed_price = fields.Float(
        string="Fixed Price", min_display_digits='Product Price', default=0)
    percent_price = fields.Float(
        string="Percentage Price", default=0,
        help="You can apply a mark-up by setting a negative discount.")

    price_discount = fields.Float(
        string="Price Discount",
        default=0,
        digits=(16, 2),
        help="You can apply a mark-up by setting a negative discount.")
    price_round = fields.Float(
        string="Price Rounding",
        min_display_digits='Product Price', default=0,
        help="Sets the price so that it is a multiple of this value.\n"
             "Rounding is applied after the discount and before the "
             "surcharge.\nTo have prices that end in 9.99, round off to "
             "10.00 and set an extra at -0.01")
    price_surcharge = fields.Float(
        string="Extra Fee",
        min_display_digits='Product Price', default=0,
        help="Specify the fixed amount to add or subtract (if negative) to "
             "the amount calculated with the discount.")

    #: ≙ ``price_markup`` (``:136-142``): almacenado, calculado desde
    #: ``price_discount`` y con inverso que lo escribe de vuelta.
    price_markup = fields.Float(
        string="Markup",
        digits=(16, 2),
        compute='_compute_price_markup',
        inverse='_inverse_price_markup',
        store=True,
        help="You can apply a mark-up on the cost")

    price_min_margin = fields.Float(
        string="Min. Price Margin",
        min_display_digits='Product Price', default=0,
        help="Specify the minimum amount of margin over the base price.")
    price_max_margin = fields.Float(
        string="Max. Price Margin",
        min_display_digits='Product Price', default=0,
        help="Specify the maximum amount of margin over the base price.")

    #: ≙ ``name`` (``:155-158``), etiqueta calculada no almacenada.
    #: ``price`` y ``rule_tip`` (``:159-163``) son etiquetas de formulario
    #: que dependen de ``formatLang``/``format_amount``: etapa 5 del
    #: diseño ``product-pricelist-cluster``.
    name = fields.Char(
        string="Name",
        compute='_compute_name',
        help="Explicit rule name for this pricelist line.")

    class Meta:
        db_table = 'product_pricelist_item'
        ordering = ['applied_on', '-min_quantity', '-categ_id', '-id']
        verbose_name = 'Regla de tarifa'
        verbose_name_plural = 'Reglas de tarifa'

    # === COMPUTE METHODS ==================================================

    def _compute_is_pricelist_required(self):
        """≙ ``_compute_is_pricelist_required`` (``:167-168``)."""
        self.is_pricelist_required = True

    @api.depends('pricelist_id.company_id', 'product_tmpl_id')
    def _compute_company_id(self):
        """≙ ``_compute_company_id`` (``:170-173``)."""
        for item in self:
            item.company_id = (item.pricelist_id.company_id
                               or item.product_tmpl_id.company_id)

    @api.depends('pricelist_id.currency_id', 'company_id')
    def _compute_currency_id(self):
        """≙ ``_compute_currency_id`` (``:175-182``).

        ``res.company`` guarda su moneda en ``currency`` (su sucesor de
        nombre es ``res-company-currency-id``).
        """
        env_company = self.env.company
        for item in self:
            item_company = item.company_id
            item.currency_id = (
                item.pricelist_id.currency_id
                or (item_company.currency if item_company else None)
                or (env_company.currency if env_company else None)
            )

    @api.depends('applied_on', 'categ_id', 'product_tmpl_id', 'product_id')
    def _compute_name(self):
        """≙ ``_compute_name`` (``:184-196``)."""
        for item in self:
            if item.categ_id and item.applied_on == APPLIED_CATEGORY:
                item.name = _("Category: %s", item.categ_id.display_name)
            elif item.product_tmpl_id and item.applied_on == APPLIED_PRODUCT:
                item.name = item.product_tmpl_id.display_name
            elif item.product_id and item.applied_on == APPLIED_VARIANT:
                item.name = _("Variant: %s", item.product_id.display_name)
            elif item.display_applied_on == '2_product_category':
                item.name = _("All Categories")
            else:
                item.name = _("All Products")

    @api.depends('price_discount')
    def _compute_price_markup(self):
        """≙ ``_compute_price_markup`` (``:265-267``)."""
        for item in self:
            item.price_markup = -item.price_discount

    def _inverse_price_markup(self):
        """≙ ``_inverse_price_markup`` (``:269-271``)."""
        for item in self:
            item.price_discount = -item.price_markup

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
                'Una regla basada en otra tarifa debe indicar cuál.'
            )
        if (
            self.date_start
            and self.date_end
            and self.date_start > self.date_end
        ):
            raise ValidationError(
                'La fecha de inicio no puede ser posterior a la de fin.'
            )

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
            return getattr(product, 'pk', None) == self.product_id_id
        if self.applied_on == APPLIED_PRODUCT:
            tmpl = getattr(product, 'product_tmpl_id_id', None) or getattr(
                product, 'pk', None
            )
            return tmpl == self.product_tmpl_id_id
        if self.applied_on == APPLIED_CATEGORY:
            categ = getattr(product, 'categ_id', None)
            # Una regla de categoría alcanza a toda la rama, no sólo al nodo:
            # la ruta materializada de ``product.category`` lo resuelve sin
            # subir la cadena.
            if not categ or not self.categ_id:
                return False
            return categ.parent_path.startswith(self.categ_id.parent_path)
        return False

    # === CÁLCULO ==========================================================

    def base_price_for(self, product):
        """``_compute_base_price`` — el precio sobre el que calcula la regla.

        Devuelve ``(precio, moneda)``. La conversión de moneda **no** se hace
        aquí: se declara en cuál está para que el llamador convierta con la
        tasa de la fecha que corresponda (ver el docstring del módulo).
        """
        if self.base == BASE_STANDARD_PRICE:
            return float(product.standard_price or 0), product.cost_currency_id
        if self.base == BASE_PRICELIST and self.base_pricelist_id:
            # La recursión completa la resuelve el selector de reglas; aquí se
            # declara el punto de entrada en vez de duplicarlo.
            raise NotImplementedError(
                'Una regla basada en otra tarifa la resuelve el selector de '
                'reglas de product_pricelist, no esta regla.'
            )
        return float(product.lst_price or 0), product.currency_id

    def compute(self, product, quantity=1, to_uom=None):
        """``_compute_price`` — el precio unitario según esta regla.

        Los cinco pasos del modo ``formula``, en el orden de la fuente. Ver el
        docstring del módulo: el orden **es** el algoritmo, y los márgenes se
        miden contra la base, no contra el precio en curso.
        """

        def convert(amount):
            """Los importes de la regla van en la unidad del producto."""
            product_uom = getattr(product, 'uom_id', None)
            if to_uom is None or product_uom is None or product_uom == to_uom:
                return float(amount)
            return product_uom._compute_price(float(amount), to_uom)

        if self.compute_price == COMPUTE_FIXED:
            return convert(self.fixed_price)

        base_price, _currency = self.base_price_for(product)

        if self.compute_price == COMPUTE_PERCENTAGE:
            return (
                base_price - (base_price * (self.percent_price / 100)) or 0.0
            )

        # === formula ===
        price_limit = base_price  # 1. la base, antes de tocarla
        discount = (
            self.price_discount
            if self.base != BASE_STANDARD_PRICE
            else -self.price_markup  # sobre coste se marca al alza
        )
        price = base_price - (base_price * (discount / 100))  # 2. descuento

        if self.price_round:  # 3. redondeo, ANTES del recargo
            price = float_round(price, precision_rounding=self.price_round)

        if self.price_surcharge:  # 4. recargo
            price += convert(self.price_surcharge)

        if self.price_min_margin:  # 5. márgenes contra la BASE
            price = max(price, price_limit + convert(self.price_min_margin))
        if self.price_max_margin:
            price = min(price, price_limit + convert(self.price_max_margin))

        return price
