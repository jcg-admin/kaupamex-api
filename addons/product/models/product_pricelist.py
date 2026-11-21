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

``_get_product_price`` y su familia seleccionan la regla aplicable y delegan
el cálculo en el item. Se portan en las etapas 3 y 4 del diseño
``product-pricelist-cluster.md``; hasta entonces el precio de venta es
``lst_price``.
"""

import api
import fields
import models

from addons.base.models.res_company import ResCompany
from addons.base.models.res_country_group import ResCountryGroup
from addons.base.models.res_currency import ResCurrency
from addons.base.models.timestamped_mixin import TimeStampedModel
from addons.mail.models import MailActivityMixin, MailThread
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
