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

Lo que queda para etapas posteriores
====================================

- La rama ``base='pricelist'`` de ``_compute_base_price`` llama a
  ``base_pricelist_id._get_product_price`` como la fuente; ese método y la
  selección de reglas son la etapa 4 del diseño ``product-pricelist-cluster``,
  junto con ``_compute_price_before_discount``.
- Las etiquetas ``price`` y ``rule_tip`` y los ``onchange`` son la etapa 5.

La conversión de moneda **sí** se porta: ``ResCurrency._convert`` existe, y
``_compute_base_price`` convierte con él como la fuente. La conversión de
unidad usa ``Uom._compute_price`` con la unidad que recibe el método.
"""

import api
import fields
import models

from addons.base.models.res_company import ResCompany
from addons.base.models.res_currency import ResCurrency
from addons.base.models.timestamped_mixin import TimeStampedModel
from addons.product.models.product_category import ProductCategory
from addons.product.models.product_pricelist import ProductPricelist
from addons.product.models.product_product import ProductProduct
from addons.product.models.product_template import ProductTemplate
from exceptions import ValidationError
from orm.environments import env
from tools.float_utils import float_round
from tools.misc import format_amount, format_datetime, formatLang
from tools.translate import _

APPLIED_VARIANT = '0_product_variant'
APPLIED_PRODUCT = '1_product'
APPLIED_CATEGORY = '2_product_category'
APPLIED_GLOBAL = '3_global'
#: ``applied_on`` — los prefijos numéricos son **precedencia**, no adorno:
#: el ``_order`` del modelo empieza por este campo, así que el orden
#: alfabético pone primero lo más específico. Verbatim de la fuente.
APPLIED_ON_CHOICES = [
    (APPLIED_GLOBAL, "All Products"),
    (APPLIED_CATEGORY, "Product Category"),
    (APPLIED_PRODUCT, "Product"),
    (APPLIED_VARIANT, "Product Variant"),
]

BASE_LIST_PRICE = 'list_price'
BASE_STANDARD_PRICE = 'standard_price'
BASE_PRICELIST = 'pricelist'
#: ``base`` — sobre qué se calcula, verbatim.
BASE_CHOICES = [
    (BASE_LIST_PRICE, 'Sales Price'),
    (BASE_STANDARD_PRICE, 'Cost'),
    (BASE_PRICELIST, 'Other Pricelist'),
]

COMPUTE_FIXED = 'fixed'
COMPUTE_PERCENTAGE = 'percentage'
COMPUTE_FORMULA = 'formula'
#: ``compute_price`` — cómo se calcula, verbatim.
COMPUTE_PRICE_CHOICES = [
    (COMPUTE_PERCENTAGE, "Discount"),
    (COMPUTE_FORMULA, "Formula"),
    (COMPUTE_FIXED, "Fixed Price"),
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
        on_delete=models.SET_NULL, null=True, blank=True,
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

    #: ≙ ``name``, ``price`` y ``rule_tip`` (``:155-163``): etiquetas
    #: calculadas, no almacenadas.
    name = fields.Char(
        string="Name",
        compute='_compute_name',
        help="Explicit rule name for this pricelist line.")
    price = fields.Char(
        string="Price",
        compute='_compute_price_label',
        help="Explicit rule name for this pricelist line.")
    rule_tip = fields.Char(compute='_compute_rule_tip')

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

    def _get_price_label_base_str(self):
        """This method allows you to extend it to other modules with other
        options in the base field to return a different text — ≙
        ``_get_price_label_base_str`` (``:198``).
        """
        self.ensure_one()
        base_str = ""
        if self.base == 'pricelist' and self.base_pricelist_id:
            base_str = self.base_pricelist_id.display_name
        elif self.base == 'standard_price':
            base_str = _("product cost")
        else:
            base_str = _("sales price")
        return base_str

    @api.depends(
        'compute_price', 'fixed_price', 'pricelist_id', 'percent_price',
        'price_discount', 'price_markup', 'price_surcharge', 'base',
        'base_pricelist_id',
    )
    def _compute_price_label(self):
        """≙ ``_compute_price_label`` (``:216``)."""
        for item in self:
            if item.compute_price == 'fixed':
                item.price = formatLang(
                    item.env, item.fixed_price, dp="Product Price",
                    currency_obj=item.currency_id)
            elif item.compute_price == 'percentage':
                percentage = self._get_integer(item.percent_price)
                if item.base_pricelist_id:
                    item.price = _(
                        "%(percentage)s %% discount on %(pricelist)s",
                        percentage=percentage,
                        pricelist=item.base_pricelist_id.display_name
                    )
                else:
                    item.price = _(
                        "%(percentage)s %% discount on sales price",
                        percentage=percentage
                    )
            else:
                base_str = item._get_price_label_base_str()

                extra_fee_str = ""
                if item.price_surcharge > 0:
                    extra_fee_str = _(
                        "+ %(amount)s extra fee",
                        amount=format_amount(
                            item.env,
                            abs(item.price_surcharge),
                            currency=item.currency_id,
                        ),
                    )
                elif item.price_surcharge < 0:
                    extra_fee_str = _(
                        "- %(amount)s rebate",
                        amount=format_amount(
                            item.env,
                            abs(item.price_surcharge),
                            currency=item.currency_id,
                        ),
                    )
                discount_type, percentage = self._get_displayed_discount(item)
                item.price = _(
                    "%(percentage)s %% %(discount_type)s on %(base)s "
                    "%(extra)s",
                    percentage=percentage,
                    discount_type=discount_type,
                    base=base_str,
                    extra=extra_fee_str,
                )

    @api.depends('price_discount')
    def _compute_price_markup(self):
        """≙ ``_compute_price_markup`` (``:265-267``)."""
        for item in self:
            item.price_markup = -item.price_discount

    def _inverse_price_markup(self):
        """≙ ``_inverse_price_markup`` (``:269-271``)."""
        for item in self:
            item.price_discount = -item.price_markup

    @api.depends_context('lang')
    @api.depends(
        'base', 'compute_price', 'price_discount', 'price_markup',
        'price_round', 'price_surcharge',
    )
    def _compute_rule_tip(self):
        """≙ ``_compute_rule_tip`` (``:277``)."""
        base_selection_vals = dict(
            self._fields['base']._description_selection(self.env))
        self.rule_tip = False
        for item in self:
            if item.compute_price != 'formula' or not item.base:
                continue
            base_amount = 100
            discount = (item.price_discount if item.base != 'standard_price'
                        else -item.price_markup)
            discount_factor = (100 - discount) / 100
            discounted_price = base_amount * discount_factor
            if item.price_round:
                discounted_price = float_round(
                    discounted_price, precision_rounding=item.price_round)
            surcharge = format_amount(item.env, item.price_surcharge,
                                      item.currency_id)
            discount_type, discount = self._get_displayed_discount(item)

            item.rule_tip = _(
                "%(base)s with a %(discount)s %% %(discount_type)s and "
                "%(surcharge)s extra fee\n"
                "Example: %(amount)s * %(discount_charge)s + "
                "%(price_surcharge)s → %(total_amount)s",
                base=base_selection_vals[item.base],
                discount=discount,
                discount_type=discount_type,
                surcharge=surcharge,
                amount=format_amount(item.env, 100, item.currency_id),
                discount_charge=discount_factor,
                price_surcharge=surcharge,
                total_amount=format_amount(
                    item.env, discounted_price + item.price_surcharge,
                    item.currency_id),
            )

    def _get_integer(self, percentage):
        """≙ ``_get_integer`` (``:306``)."""
        return int(percentage) if percentage == int(percentage) else percentage

    def _get_displayed_discount(self, item):
        """≙ ``_get_displayed_discount`` (``:309``)."""
        if item.base == 'standard_price':
            return _("markup"), self._get_integer(item.price_markup)
        return _("discount"), self._get_integer(item.price_discount)

    # === CONSTRAINT METHODS ===============================================

    @api.constrains('base_pricelist_id', 'base')
    def _check_base_pricelist_id(self):
        """≙ ``_check_base_pricelist_id`` (``:317``)."""
        if any(item.base == 'pricelist' and not item.base_pricelist_id
               for item in self):
            raise ValidationError(_(
                'A pricelist item with "Other Pricelist" as base must have '
                'a base_pricelist_id.'))

    @api.constrains('base_pricelist_id', 'pricelist_id', 'base')
    def _check_pricelist_recursion(self):
        """≙ ``_check_pricelist_recursion`` (``:322``)."""
        def dfs_path(from_pl, to_pl, path, seen):
            if (from_pl, to_pl) in seen:
                # If another pricelist rule from the same pricelist has the
                # same target, there is no need to test that path again.
                return path.browse()

            if to_pl in path:
                return path + to_pl

            seen.add((from_pl, to_pl))
            pricelist_based_items = self.env[
                "product.pricelist.item"]._read_group(
                domain=[("pricelist_id", "=", to_pl.id),
                        ("base", "=", "pricelist")],
                groupby=["base_pricelist_id"],
                aggregates=["id:recordset"],
            )
            new_path = path + to_pl
            for pricelist, _to_items in pricelist_based_items:
                if res := dfs_path(to_pl, pricelist, new_path, seen):
                    return res
            return path.browse()

        seen = set()
        for item in self:
            # Skip validation for rules not based on other pricelists.
            if (item.base != "pricelist" or not item.base_pricelist_id
                    or not item.pricelist_id):
                continue
            if path := dfs_path(item.pricelist_id, item.base_pricelist_id,
                                item.pricelist_id, seen):
                raise ValidationError(_(
                    "Recursive pricelist rules detected: %s",
                    " ⇒ ".join(path.mapped("name"))))

    @api.constrains('date_start', 'date_end')
    def _check_date_range(self):
        """≙ ``_check_date_range`` (``:355``)."""
        for item in self:
            if (item.date_start and item.date_end
                    and item.date_start >= item.date_end):
                raise ValidationError(_(
                    '%(item_name)s: end date (%(end_date)s) should be after '
                    'start date (%(start_date)s)',
                    item_name=item.display_name,
                    end_date=format_datetime(self.env, item.date_end),
                    start_date=format_datetime(self.env, item.date_start),
                ))
        return True

    @api.constrains('price_min_margin', 'price_max_margin')
    def _check_margin(self):
        """≙ ``_check_margin`` (``:367``)."""
        if any(item.price_min_margin > item.price_max_margin
               for item in self):
            raise ValidationError(_(
                'The minimum margin should be lower than the maximum '
                'margin.'))

    @api.constrains('product_id', 'product_tmpl_id', 'categ_id')
    def _check_product_consistency(self):
        """≙ ``_check_product_consistency`` (``:372``)."""
        for item in self:
            if item.applied_on == APPLIED_CATEGORY and not item.categ_id:
                raise ValidationError(_(
                    "Please specify the category for which this rule "
                    "should be applied"))
            if item.applied_on == APPLIED_PRODUCT and not item.product_tmpl_id:
                raise ValidationError(_(
                    "Please specify the product for which this rule should "
                    "be applied"))
            if item.applied_on == APPLIED_VARIANT and not item.product_id:
                raise ValidationError(_(
                    "Please specify the product variant for which this "
                    "rule should be applied"))

    # === ONCHANGE METHODS =================================================

    @api.onchange('base')
    def _onchange_base(self):
        """≙ ``_onchange_base`` (``:384``)."""
        for item in self:
            item.update({
                'price_discount': 0.0,
                'price_markup': 0.0,
            })

    @api.onchange('base_pricelist_id')
    def _onchange_base_pricelist_id(self):
        """≙ ``_onchange_base_pricelist_id`` (``:392``)."""
        for item in self:
            if item.compute_price == 'percentage':
                item.base = ((bool(item.base_pricelist_id) and 'pricelist')
                             or 'list_price')

    @api.onchange('compute_price')
    def _onchange_compute_price(self):
        """≙ ``_onchange_compute_price`` (``:398``)."""
        self.base_pricelist_id = False
        if self.compute_price != 'fixed':
            self.fixed_price = 0.0
        if self.compute_price != 'percentage':
            self.percent_price = 0.0
        if self.compute_price != 'formula':
            self.update({
                'base': 'list_price',
                'price_discount': 0.0,
                'price_surcharge': 0.0,
                'price_markup': 0.0,
                'price_round': 0.0,
                'price_min_margin': 0.0,
                'price_max_margin': 0.0,
            })

    @api.onchange('display_applied_on')
    def _onchange_display_applied_on(self):
        """≙ ``_onchange_display_applied_on`` (``:416``)."""
        for item in self:
            if not (item.product_tmpl_id or item.categ_id):
                item.update({'applied_on': '3_global'})
            elif item.display_applied_on == '1_product':
                item.update({
                    'applied_on': '1_product',
                    'categ_id': None,
                })
            elif item.display_applied_on == '2_product_category':
                item.update({
                    'product_id': None,
                    'product_tmpl_id': None,
                    'applied_on': '2_product_category',
                    'product_uom_name': None,
                })

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """≙ ``_onchange_product_id`` (``:434``)."""
        has_product_id = self.filtered('product_id')
        for item in has_product_id:
            item.product_tmpl_id = item.product_id.product_tmpl_id
        if self.env.context.get('default_applied_on', False) == '1_product':
            # If a product variant is specified, apply on variants instead
            # Reset if product variant is removed
            has_product_id.update({'applied_on': '0_product_variant'})
            (self - has_product_id).update({'applied_on': '1_product'})

    @api.onchange('product_tmpl_id')
    def _onchange_product_tmpl_id(self):
        """≙ ``_onchange_product_tmpl_id`` (``:445``)."""
        has_tmpl_id = self.filtered('product_tmpl_id')
        for item in has_tmpl_id:
            if (item.product_id
                    and item.product_id.product_tmpl_id
                    != item.product_tmpl_id):
                item.product_id = None

    @api.onchange('product_id', 'product_tmpl_id', 'categ_id')
    def _onchange_rule_content(self):
        """≙ ``_onchange_rule_content`` (``:452``)."""
        if not self.env.context.get('default_applied_on', False):
            # If we aren't coming from a specific product template/variant.
            variants_rules = self.filtered(
                lambda r: bool(r.product_id) and bool(r.product_tmpl_id)
            )
            template_rules = (self - variants_rules).filtered(
                'product_tmpl_id')
            category_rules = self.filtered(
                lambda cat: bool(cat.categ_id) and cat.categ_id.name != 'All'
            )
            variants_rules.update({'applied_on': '0_product_variant'})
            template_rules.update({'applied_on': '1_product'})
            category_rules.update({'applied_on': '2_product_category'})
            global_rules = (self - variants_rules - template_rules
                            - category_rules)
            global_rules.update({'applied_on': '3_global'})

    @api.onchange('price_round')
    def _onchange_price_round(self):
        """≙ ``_onchange_price_round`` (``:469``)."""
        if any(item.price_round and item.price_round < 0.0 for item in self):
            raise ValidationError(_(
                "The rounding method must be strictly positive."))

    @api.onchange('date_start', 'date_end')
    def _onchange_validity_period(self):
        """≙ ``_onchange_validity_period`` (``:474``)."""
        self._check_date_range()

    # === CRUD METHODS =====================================================

    @api.model_create_multi
    def create(self, vals_list):
        """≙ ``create`` (``:480``)."""
        for values in vals_list:
            if values.get('product_id') and not values.get('product_tmpl_id'):
                # Deduce product template from product variant if not
                # specified. Ensures that the pricelist rule is properly
                # configured and displayed in the UX even in case of
                # partial/incomplete data (mostly for imports).
                values['product_tmpl_id'] = self.env['product.product'].browse(
                    values.get('product_id')
                ).product_tmpl_id.id

            if not values.get('applied_on'):
                values['applied_on'] = (
                    APPLIED_VARIANT if values.get('product_id') else
                    APPLIED_PRODUCT if values.get('product_tmpl_id') else
                    APPLIED_CATEGORY if values.get('categ_id') else
                    APPLIED_GLOBAL
                )

            # Ensure item consistency for later searches.
            applied_on = values['applied_on']
            if applied_on == APPLIED_GLOBAL:
                values.update({'product_id': None, 'product_tmpl_id': None,
                               'categ_id': None})
            elif applied_on == APPLIED_CATEGORY:
                values.update({'product_id': None, 'product_tmpl_id': None})
            elif applied_on == APPLIED_PRODUCT:
                values.update({'product_id': None, 'categ_id': None})
            elif applied_on == APPLIED_VARIANT:
                values.update({'categ_id': None})
        return super().create(vals_list)

    def write(self, vals):
        """≙ ``write`` (``:510``)."""
        if vals.get('applied_on', False):
            # Ensure item consistency for later searches.
            applied_on = vals['applied_on']
            if applied_on == APPLIED_GLOBAL:
                vals.update({'product_id': None, 'product_tmpl_id': None,
                             'categ_id': None})
            elif applied_on == APPLIED_CATEGORY:
                vals.update({'product_id': None, 'product_tmpl_id': None})
            elif applied_on == APPLIED_PRODUCT:
                vals.update({'product_id': None, 'categ_id': None})
            elif applied_on == APPLIED_VARIANT:
                vals.update({'categ_id': None})
        return super().write(vals)

    # === BUSINESS METHODS =================================================

    def _is_applicable_for(self, product, qty_in_product_uom):
        """Check whether the current rule is valid for the given product &
        qty — ≙ ``_is_applicable_for`` (``:526``).

        Note: self.ensure_one()

        :param product: product record (product.product/product.template)
        :param float qty_in_product_uom: quantity, expressed in product UoM
        :returns: Whether rules is valid or not
        :rtype: bool
        """
        self.ensure_one()
        product.ensure_one()
        res = True

        is_product_template = product._name == 'product.template'
        if self.min_quantity and qty_in_product_uom < self.min_quantity:
            res = False

        elif self.applied_on == "2_product_category":
            if not product.categ_id or (
                product.categ_id != self.categ_id
                and not product.categ_id.parent_path.startswith(
                    self.categ_id.parent_path)
            ):
                res = False
        # Applied on a specific product template/variant
        elif is_product_template:
            if (self.applied_on == "1_product"
                    and product.id != self.product_tmpl_id.id):
                res = False
            elif self.applied_on == "0_product_variant" and not (
                product.product_variant_count == 1
                and product.product_variant_id.id == self.product_id.id
            ):
                # product self acceptable on template if has only one variant
                res = False
        elif (
            self.applied_on == "1_product"
            and product.product_tmpl_id.id != self.product_tmpl_id.id
        ) or (
            self.applied_on == "0_product_variant"
            and product.id != self.product_id.id
        ):
            res = False

        return res

    def _compute_price(self, product, quantity, uom, date, currency=None,
                       **kwargs):
        """Compute the unit price of a product in the context of a pricelist
        application — ≙ ``_compute_price`` (``:570``).

        Note: self and self.ensure_one()

        :param product: recordset of product (product.product/
            product.template)
        :param float quantity: quantity of products requested (in given uom)
        :param uom: unit of measure (uom.uom record)
        :param datetime date: date to use for price computation and currency
            conversions
        :param currency: currency (for the case where self is empty)
        :param dict kwargs: unused parameters available for overrides

        :returns: price according to pricelist rule or the product price,
            expressed in the param currency, the pricelist currency or the
            company currency
        :rtype: float

        ``res.currency`` es todavía un modelo de Django (la app ``base`` está
        pendiente de ``BaseModel``): una instancia es un único registro por
        construcción, así que su ``ensure_one`` no tiene a quién comprobar.
        La moneda de la empresa vive en ``currency`` (sucesor de nombre
        ``res-company-currency-id``).
        """
        self and self.ensure_one()  # self is at most one record
        product.ensure_one()
        uom.ensure_one()

        company = self.env.company
        currency = (currency or self.currency_id
                    or (company.currency if company else None))

        # Pricelist specific values are specified according to product UoM
        # and must be multiplied according to the factor between uoms
        product_uom = product.uom_id
        if product_uom != uom:
            def convert(p):
                return product_uom._compute_price(p, uom)
        else:
            def convert(p):
                return p

        if self.compute_price == 'fixed':
            price = convert(self.fixed_price)
        elif self.compute_price == 'percentage':
            base_price = self._compute_base_price(
                product, quantity, uom, date, currency, **kwargs)
            price = (base_price
                     - (base_price * (self.percent_price / 100))) or 0.0
        elif self.compute_price == 'formula':
            base_price = self._compute_base_price(
                product, quantity, uom, date, currency, **kwargs)
            # complete formula
            price_limit = base_price
            discount = (self.price_discount if self.base != 'standard_price'
                        else -self.price_markup)
            price = base_price - (base_price * (discount / 100))
            if self.price_round:
                price = float_round(price,
                                    precision_rounding=self.price_round)

            if self.price_surcharge:
                price += convert(self.price_surcharge)

            if self.price_min_margin:
                price = max(price,
                            price_limit + convert(self.price_min_margin))

            if self.price_max_margin:
                price = min(price,
                            price_limit + convert(self.price_max_margin))
        else:  # empty self, or extended pricelist price computation logic
            price = self._compute_base_price(
                product, quantity, uom, date, currency, **kwargs)

        return price

    def _compute_base_price(self, product, quantity, uom, date, currency,
                            **kwargs):
        """Compute the base price for a given rule — ≙
        ``_compute_base_price`` (``:628``).

        :param product: recordset of product (product.product/
            product.template)
        :param float quantity: quantity of products requested (in given uom)
        :param uom: unit of measure (uom.uom record)
        :param datetime date: date to use for price computation and currency
            conversions
        :param currency: currency in which the returned price must be
            expressed

        :returns: base price, expressed in provided pricelist currency
        :rtype: float

        ``_convert`` devuelve un ``Decimal``; el precio se mantiene ``float``,
        como el de la fuente.
        """
        rule_base = self.base or 'list_price'
        if rule_base == 'pricelist' and self.base_pricelist_id:
            price = self.base_pricelist_id._get_product_price(
                product, quantity, currency=self.base_pricelist_id.currency_id,
                uom=uom, date=date, **kwargs
            )
            src_currency = self.base_pricelist_id.currency_id
        elif rule_base == "standard_price":
            src_currency = product.cost_currency_id
            price = product._price_compute(
                rule_base, uom=uom, date=date)[product.id]
        else:  # list_price
            src_currency = product.currency_id
            price = product._price_compute(
                rule_base, uom=uom, date=date)[product.id]

        if src_currency != currency:
            price = float(src_currency._convert(
                price, currency, self.env.company, date, round=False))

        return price

    def _compute_price_before_discount(self, *args, **kwargs):
        """Compute the base price of the given rule, considering chained
        pricelists — ≙ ``_compute_price_before_discount`` (``:661``).

        :param product: recordset of product (product.product/
            product.template)
        :param float qty: quantity of products requested (in given uom)
        :param uom: unit of measure (uom.uom record)
        :param datetime date: date to use for price computation and currency
            conversions
        :param currency: currency in which the returned price must be
            expressed

        :returns: base price, expressed in provided pricelist currency
        :rtype: float
        """
        pricelist_item = self
        # Find the lowest pricelist rule whose pricelist is configured to
        # show the discount to the customer.
        while pricelist_item.base == 'pricelist':
            rule_id = pricelist_item.base_pricelist_id._get_product_rule(
                *args, **kwargs)
            rule_pricelist_item = self.env['product.pricelist.item'].browse(
                rule_id)
            if (rule_pricelist_item
                    and rule_pricelist_item.compute_price == 'percentage'):
                pricelist_item = rule_pricelist_item
            else:
                break

        return pricelist_item._compute_base_price(*args, **kwargs)
