"""``product.pricelist`` — una lista de precios y su alcance.

Adaptación de ``addons/product/models/product_pricelist.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 414 líneas). La lista en sí es poco
más que un contenedor con moneda y alcance; **las reglas** —y con ellas todo
el cálculo— viven en ``product_pricelist_item.py``.

Lo que la lista aporta y sus reglas no
======================================

- **La moneda.** Todas sus reglas expresan importes en ella, y el cálculo
  convierte desde la moneda del producto. Sin este campo, una regla de "10 €
  fijos" no diría si son euros.
- **La compañía.** Vacía = la lista sirve a todas; con valor, sólo a esa.
- **Los grupos de países** (``country_group_ids``): es lo que hace que un
  visitante vea una lista u otra según de dónde llega. La referencia lo usa en
  el escaparate, no en el cálculo.
- **``sequence``.** Cuando varias listas encajan, gana la de secuencia menor.
  Es el desempate, y sin él la elección dependería del orden de inserción.

El orden de las reglas es de las reglas, no de la lista
=======================================================

La lista ordena por ``sequence, id, name``; el **item** ordena por
``applied_on, min_quantity desc, categ_id desc, id desc``. Son dos ordenaciones
distintas y la segunda es la que decide qué precio sale — está documentada en
``product_pricelist_item.py``, que es su sitio.

La selección de la regla y el precio
====================================

``_get_product_price`` y su familia seleccionan la regla aplicable con
``_compute_price_rule`` y delegan el cálculo en el item
(``_compute_price``). Las tarifas por país y por cliente son la etapa 5 del
diseño ``product-pricelist-cluster.md``.
"""

import api
import fields
import models

from addons.base.models.res_company import ResCompany
from addons.base.models.res_country_group import ResCountryGroup
from addons.base.models.res_currency import ResCurrency
from addons.base.models.timestamped_mixin import TimeStampedModel
from addons.mail.models import MailActivityMixin, MailThread
from exceptions import UserError
from orm.environments import env
from tools.translate import _


def _default_currency_id():
    """≙ ``_default_currency_id``
    (``odoo19c: addons/product/models/product_pricelist.py:16-17``): la
    moneda de la empresa activa. Callable de módulo: un ``default`` de
    Django no recibe ``self``."""
    company = env().company
    return company.currency_id if company is not None else None


def _default_company_id():
    """≙ ``default=lambda self: self.env.company`` (``:43-47``)."""
    company = env().company
    return company.pk if company is not None else None


class ProductPricelist(models.BaseModel, MailThread, MailActivityMixin,
                       TimeStampedModel):
    """``product.pricelist`` — el contenedor de reglas de precio."""

    #: ≙ la cabecera de ``odoo19c: addons/product/models/
    #: product_pricelist.py:10-14``, verbatim.
    _name = 'product.pricelist'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Pricelist"
    _rec_names_search = ['name', 'currency_id']
    #: ``Meta.ordering`` es su forma en Django; los dos conviven.
    _order = "sequence, id, name"

    def _base_domain_item_ids(self):
        return [
            '|', ('product_tmpl_id', '=', None),
            ('product_tmpl_id.active', '=', True),
            '|', ('product_id', '=', None), ('product_id.active', '=', True),
        ]

    def _domain_item_ids(self):
        return self._base_domain_item_ids()

    name = fields.Char(string="Pricelist Name", required=True,
                       max_length=255)
    active = fields.Boolean(
        default=True,
        verbose_name='Activa',
        help_text='Desmarcar oculta la tarifa sin borrarla.',
    )
    sequence = fields.Integer(
        default=16,
        verbose_name='Secuencia',
        help_text='Desempate cuando varias tarifas encajan: gana la menor.',
    )
    #: ≙ ``currency_id`` (``:36-41``).
    currency_id = fields.Many2one(
        ResCurrency,
        default=_default_currency_id,
        required=True,
        tracking=1,
        db_column='currency_id',
        null=False, on_delete=models.PROTECT,
        related_name='pricelist_ids',
    )
    #: ≙ ``company_id`` (``:43``) en forma C.
    company_id = fields.Many2one(
        ResCompany,
        db_column='company_id',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_index=True,
        default=_default_company_id,
        tracking=5,
        related_name='pricelist_ids',
        verbose_name='Compañía',
        help_text='Vacío = la tarifa sirve a todas las compañías.',
    )
    #: ≙ ``country_group_ids`` (``:49-56``), con la tabla y las columnas
    #: de la fuente.
    country_group_ids = fields.Many2many(
        ResCountryGroup,
        relation='res_country_group_pricelist_rel',
        column1='pricelist_id',
        column2='res_country_group_id',
        blank=True,
        related_name='pricelist_ids',
        verbose_name='Grupos de países',
        help_text=(
            'Decide qué tarifa ve un visitante según de dónde llega. '
            'No interviene en el cálculo.'
        ),
    )

    #: ≙ ``item_ids`` (``odoo19c: addons/product/models/
    #: product_pricelist.py:58-64``); el dominio va como lambda para que
    #: las extensiones de ``_domain_item_ids`` surtan efecto.
    item_ids = fields.One2many(
        comodel_name='product.pricelist.item',
        inverse_name='pricelist_id',
        string="Pricelist Rules",
        domain=lambda self: self._domain_item_ids(),
        copy=True)

    class Meta:
        db_table = 'product_pricelist'
        ordering = ['sequence', 'id', 'name']
        verbose_name = 'Tarifa'
        verbose_name_plural = 'Tarifas'

    def __str__(self):
        return self.name

    @api.depends('currency_id')
    def _compute_display_name(self):
        for pricelist in self:
            pricelist_name = pricelist.name and pricelist.name or _('New')
            pricelist.display_name = (
                f'{pricelist_name} ({pricelist.currency_id.name})')

    def write(self, vals):
        res = super().write(vals)

        # Make sure that there is no multi-company issue in the existing
        # rules after the company change.
        if 'company_id' in vals and len(self) == 1:
            self.item_ids._check_company()

        return res

    def copy_data(self, default=None):
        default = dict(default or {})
        vals_list = super().copy_data(default=default)
        if 'name' not in default:
            for pricelist, vals in zip(self, vals_list):
                vals['name'] = _("%s (copy)", pricelist.name)
        return vals_list

    def _get_products_price(self, products, *args, **kwargs):
        """Compute the pricelist prices for the specified products, quantity
        & uom — ≙ ``_get_products_price`` (``:90``).

        Note: self and self.ensure_one()

        :param products: recordset of products (product.product/
            product.template)
        :param float quantity: quantity of products requested (in given uom)
        :param currency: record of currency (res.currency) (optional)
        :param uom: unit of measure (uom.uom record) (optional)
            If not specified, prices returned are expressed in product uoms
        :param date: date to use for price computation and currency
            conversions (optional)
        :type date: date or datetime

        :returns: {product_id: product price}, considering the current
            pricelist if any
        :rtype: dict(int, float)
        """
        self and self.ensure_one()  # self is at most one record
        return {
            product_id: res_tuple[0]
            for product_id, res_tuple in self._compute_price_rule(
                products, *args, **kwargs).items()
        }

    def _get_product_price(self, product, *args, **kwargs):
        """Compute the pricelist price for the specified product, qty & uom
        — ≙ ``_get_product_price`` (``:112``).

        Note: self and self.ensure_one()

        :returns: unit price of the product, considering pricelist rules if
            any
        :rtype: float
        """
        self and self.ensure_one()  # self is at most one record
        return self._compute_price_rule(
            product, *args, **kwargs)[product.id][0]

    def _get_product_price_rule(self, product, *args, **kwargs):
        """Compute the pricelist price & rule for the specified product, qty
        & uom — ≙ ``_get_product_price_rule`` (``:131``).

        Note: self and self.ensure_one()

        :returns: (product unit price, applied pricelist rule id)
        :rtype: tuple(float, int)
        """
        self and self.ensure_one()  # self is at most one record
        return self._compute_price_rule(product, *args, **kwargs)[product.id]

    def _get_product_rule(self, product, *args, **kwargs):
        """Compute the pricelist price & rule for the specified product, qty
        & uom — ≙ ``_get_product_rule`` (``:150``).

        Note: self and self.ensure_one()

        :returns: applied pricelist rule id
        :rtype: int or False
        """
        self and self.ensure_one()  # self is at most one record
        return self._compute_price_rule(
            product, *args, compute_price=False, **kwargs)[product.id][1]

    def _compute_price_rule(
        self, products, quantity, *, currency=None, uom=None, date=False,
        compute_price=True, **kwargs
    ):
        """ Low-level method - Mono pricelist, multi products — ≙
        ``_compute_price_rule`` (``:169``).
        Returns: dict{product_id: (price, suitable_rule) for the given
        pricelist}

        Note: self and self.ensure_one()

        :param products: recordset of products (product.product/
            product.template)
        :param float quantity: quantity of products requested (in given uom)
        :param currency: record of currency (res.currency)
                         note: currency.ensure_one()
        :param uom: unit of measure (uom.uom record)
            If not specified, prices returned are expressed in product uoms
        :param date: date to use for price computation and currency
            conversions
        :type date: date or datetime
        :param bool compute_price: whether the price should be computed
            (default: True)

        :returns: product_id: (price, pricelist_rule)
        :rtype: dict

        ``res.currency`` es todavía un modelo de Django: una instancia es un
        único registro por construcción y la moneda de la empresa vive en
        ``currency`` (sucesor ``res-company-currency-id``).
        """
        self and self.ensure_one()  # self is at most one record

        company = self.env.company
        currency = (currency or self.currency_id
                    or (company.currency if company else None))

        if not products:
            return {}

        if not date:
            # Used to fetch pricelist rules and currency rates
            date = fields.Datetime.now()

        # Fetch all rules potentially matching specified products/templates/
        # categories and date
        rules = self._get_applicable_rules(products, date, **kwargs)

        results = {}
        for product in products:
            suitable_rule = self.env['product.pricelist.item']

            product_uom = product.uom_id
            # If no uom is specified, fall back on the product uom
            target_uom = uom or product_uom

            # Compute quantity in product uom because pricelist rules are
            # specified w.r.t product default UoM (min_quantity,
            # price_surchage, ...)
            if target_uom != product_uom:
                qty_in_product_uom = target_uom._compute_quantity(
                    quantity, product_uom, raise_if_failure=False
                )
            else:
                qty_in_product_uom = quantity

            for rule in rules:
                if rule._is_applicable_for(product, qty_in_product_uom):
                    suitable_rule = rule
                    break

            if compute_price:
                price = suitable_rule._compute_price(
                    product, quantity, target_uom, date=date,
                    currency=currency, **kwargs)
            else:
                # Skip price computation when only the rule is requested.
                price = 0.0

            results[product.id] = (price, suitable_rule.id)

        return results

    # Split methods to ease (community) overrides
    def _get_applicable_rules(self, products, date, **kwargs):
        """≙ ``_get_applicable_rules`` (``:239``)."""
        self and self.ensure_one()  # self is at most one record
        if not self:
            return self.env['product.pricelist.item']

        return self.env['product.pricelist.item'].search(
            self._get_applicable_rules_domain(
                products=products, date=date, **kwargs)
        )

    def _get_applicable_rules_domain(self, products, date, **kwargs):
        """≙ ``_get_applicable_rules_domain`` (``:248``)."""
        self and self.ensure_one()  # self is at most one record
        if products._name == 'product.template':
            templates_domain = ('product_tmpl_id', 'in', products.ids)
            products_domain = ('product_id.product_tmpl_id', 'in',
                               products.ids)
        else:
            templates_domain = ('product_tmpl_id', 'in',
                                products.product_tmpl_id.ids)
            products_domain = ('product_id', 'in', products.ids)

        return [
            ('pricelist_id', '=', self.id),
            '|', ('categ_id', '=', False),
            ('categ_id', 'parent_of', products.categ_id.ids),
            '|', ('product_tmpl_id', '=', False), templates_domain,
            '|', ('product_id', '=', False), products_domain,
            '|', ('date_start', '=', False), ('date_start', '<=', date),
            '|', ('date_end', '=', False), ('date_end', '>=', date),
        ]

    # Multi pricelists price|rule computation
    def _price_get(self, product, quantity, **kwargs):
        """ Multi pricelist, mono product - returns price per pricelist —
        ≙ ``_price_get`` (``:268``)."""
        return {
            key: price[0]
            for key, price in self._compute_price_rule_multi(
                product, quantity, **kwargs)[product.id].items()}

    def _compute_price_rule_multi(self, products, quantity, uom=None,
                                  date=False, **kwargs):
        """ Low-level method - Multi pricelist, multi products — ≙
        ``_compute_price_rule_multi`` (``:274``).
        Returns: dict{product_id: dict{pricelist_id: (price,
        suitable_rule)} }"""
        if not self.ids:
            pricelists = self.search([])
        else:
            pricelists = self
        results = {}
        for pricelist in pricelists:
            subres = pricelist._compute_price_rule(
                products, quantity, uom=uom, date=date, **kwargs)
            for product_id, price in subres.items():
                results.setdefault(product_id, {})
                results[product_id][pricelist.id] = price
        return results

    @api.ondelete(at_uninstall=False)
    def _unlink_except_used_as_rule_base(self):
        """≙ ``_unlink_except_used_as_rule_base`` (``odoo19c:
        addons/product/models/product_pricelist.py:394``): una tarifa que
        otra usa como base no se borra, salvo que se borren juntas."""
        linked_items = self.env['product.pricelist.item'].sudo().search([
            ('base', '=', 'pricelist'),
            ('base_pricelist_id', 'in', self.ids),
            ('pricelist_id', 'not in', self.ids),
        ])
        if linked_items:
            raise UserError(_(
                'You cannot delete pricelist(s):\n(%(pricelists)s)\nThey are '
                'used within pricelist(s):\n%(other_pricelists)s',
                pricelists='\n'.join(
                    linked_items.base_pricelist_id.mapped('display_name')),
                other_pricelists='\n'.join(
                    linked_items.pricelist_id.mapped('display_name')),
            ))
