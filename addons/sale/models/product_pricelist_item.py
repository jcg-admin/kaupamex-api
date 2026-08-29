"""Lo que ``sale`` añade a la regla de tarifa — ≙ ``_inherit``.

Origen: ``odoo19c: sale/models/product_pricelist_item.py`` (LGPL-3 según su
``__manifest__.py``: copia + adaptación con atribución).

Dos métodos, y los dos giran alrededor de la misma pregunta: **¿se muestra el
descuento como línea aparte en el presupuesto?** No es una propiedad de la
regla — es una bandera de configuración de la instalación, encendida por el
grupo ``sale.group_discount_per_so_line``.

- ``_is_discount_feature_enabled`` (``:6-8``) — ``@api.model``, así que aquí
  es ``classmethod``: pregunta por la instalación, no por una regla concreta.
- ``_show_discount`` (``:10-15``) — de instancia. Verdadero sólo si la
  funcionalidad está encendida **y** esta regla calcula por porcentaje.
"""

from addons.base.models.res_groups import ResGroups
from addons.product.models.product_pricelist_item import COMPUTE_PERCENTAGE
from orm.model_classes import extend_model

#: ≙ ``'sale.group_discount_per_so_line'`` (``odoo19c: :8``) — el identificador
#: externo del grupo que enciende el descuento por línea de pedido. Se conserva
#: verbatim: es la llave con que la siembra lo registra.
GROUP_DISCOUNT_PER_SO_LINE = 'sale.group_discount_per_so_line'


def _is_discount_feature_enabled(cls):
    """≙ ``_is_discount_feature_enabled`` (``odoo19c: :6-8``).

    ``@api.model`` allá, ``classmethod`` aquí: la pregunta es por la
    instalación, no por una regla. El interruptor lo lee ``ResGroups`` desde
    el superusuario — ver su ``_is_feature_enabled``.
    """
    return ResGroups._is_feature_enabled(GROUP_DISCOUNT_PER_SO_LINE)


def _show_discount(self):
    """≙ ``_show_discount`` (``odoo19c: :10-15``).

    La guarda ``if not self: return False`` de la fuente protege contra el
    recordset vacío, que aquí no existe: ``self`` es siempre una instancia. El
    ``ensure_one()`` que la sigue tampoco tiene destinatario por la misma
    razón. Es divergencia de mecanismo —el recordset frente a la instancia—,
    no símbolo omitido: las dos guardas dejan de poder fallar.
    """
    return (type(self)._is_discount_feature_enabled()
            and self.compute_price == COMPUTE_PERCENTAGE)


def apply_sale_pricelist_item_extensions():
    """Cuelga los dos métodos sobre ``product.pricelist.item``.

    La invoca ``SaleConfig.ready()``.
    """
    extend_model(
        'product', 'ProductPricelistItem',
        metodos={
            '_is_discount_feature_enabled':
                classmethod(_is_discount_feature_enabled),
            '_show_discount': _show_discount,
        },
    )
