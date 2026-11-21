"""Lo que ``sale`` añade a la regla de tarifa — ≙ ``_inherit``.

Origen: ``odoo19c: sale/models/product_pricelist_item.py`` (LGPL-3 según su
``__manifest__.py``: copia + adaptación con atribución).

Dos métodos, y los dos giran alrededor de la misma pregunta: **¿se muestra el
descuento como línea aparte en el presupuesto?** No es una propiedad de la
regla — es una bandera de configuración de la instalación, encendida por el
grupo ``sale.group_discount_per_so_line``.

- ``_is_discount_feature_enabled`` (``:6-8``) — ``@api.model``: pregunta por
  la instalación, no por una regla concreta.
- ``_show_discount`` (``:10-15``) — de instancia. Verdadero sólo si la
  funcionalidad está encendida **y** esta regla calcula por porcentaje.
"""

import api

from addons.base.models.res_groups import ResGroups
from addons.product.models.product_pricelist_item import COMPUTE_PERCENTAGE
from orm.model_classes import extend_model

#: ≙ la cabecera que la fuente declara en su clase (``odoo19c: :5``; la
#: extensión aquí no es clase).
_inherit = 'product.pricelist.item'

#: ≙ ``'sale.group_discount_per_so_line'`` (``odoo19c: :8``) — el identificador
#: externo del grupo que enciende el descuento por línea de pedido. Se conserva
#: verbatim: es la llave con que la siembra lo registra.
GROUP_DISCOUNT_PER_SO_LINE = 'sale.group_discount_per_so_line'


@api.model
def _is_discount_feature_enabled(self):
    """≙ ``_is_discount_feature_enabled`` (``odoo19c: :6-8``).

    La pregunta es por la instalación, no por una regla. El interruptor lo
    lee ``ResGroups`` desde el superusuario — ver su
    ``_is_feature_enabled``.
    """
    return ResGroups._is_feature_enabled(GROUP_DISCOUNT_PER_SO_LINE)


def _show_discount(self):
    """≙ ``_show_discount`` (``odoo19c: :10-15``), con sus dos guardas:
    el recordset vacío no muestra descuento y más de uno es un error."""
    if not self:
        return False

    self.ensure_one()

    return (
        self._is_discount_feature_enabled()
        and self.compute_price == COMPUTE_PERCENTAGE
    )


def apply_sale_pricelist_item_extensions():
    """Cuelga los dos métodos sobre ``product.pricelist.item``.

    La invoca ``SaleConfig.ready()``.
    """
    extend_model(
        'product',
        'ProductPricelistItem',
        metodos={
            '_is_discount_feature_enabled': _is_discount_feature_enabled,
            '_show_discount': _show_discount,
        },
    )
