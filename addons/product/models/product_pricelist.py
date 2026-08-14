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

Qué NO se porta, con su medición
================================

- **``_get_product_price`` y su familia** (``_compute_price_rule``,
  ``_get_products_price``…): seleccionan la regla aplicable y delegan el
  cálculo en el item. La **selección** depende de resolver el producto, su
  categoría y su plantilla contra cada regla; se porta en
  ``product_pricelist_item.py`` como ``matches`` y ``best_rule_for``, que es
  donde están los datos que decide.
- **``_get_partner_pricelist_multi``**: elige la lista de un cliente cruzando
  su país con los grupos de países. Depende de ``res.partner.country``, que
  existe, y del escaparate, que no está en este addon.
"""
import fields
import models

from addons.base.models.res_company import ResCompany
from addons.base.models.res_country_group import ResCountryGroup
from addons.base.models.res_currency import ResCurrency
from addons.base.models.timestamped_mixin import TimeStampedModel


class ProductPricelist(TimeStampedModel):
    """``product.pricelist`` — el contenedor de reglas de precio."""

    name = fields.Char(max_length=255, verbose_name='Nombre de la tarifa')
    active = fields.Boolean(
        default=True, verbose_name='Activa',
        help_text='Desmarcar oculta la tarifa sin borrarla.')
    sequence = fields.Integer(
        default=16, verbose_name='Secuencia',
        help_text='Desempate cuando varias tarifas encajan: gana la menor.')
    currency = fields.Many2one(
        ResCurrency, on_delete=models.PROTECT, null=True, blank=True,
        related_name='pricelist_ids', verbose_name='Moneda',
        help_text='Moneda en que sus reglas expresan los importes.')
    company = fields.Many2one(
        ResCompany, on_delete=models.CASCADE, null=True, blank=True,
        db_index=True, related_name='pricelist_ids', verbose_name='Compañía',
        help_text='Vacío = la tarifa sirve a todas las compañías.')
    country_groups = fields.Many2many(
        ResCountryGroup, blank=True, related_name='pricelist_ids',
        verbose_name='Grupos de países',
        help_text='Decide qué tarifa ve un visitante según de dónde llega. '
                  'No interviene en el cálculo.',
    )

    class Meta:
        db_table = 'product_pricelist'
        ordering = ['sequence', 'id', 'name']
        verbose_name = 'Tarifa'
        verbose_name_plural = 'Tarifas'

    def __str__(self):
        return self.name
