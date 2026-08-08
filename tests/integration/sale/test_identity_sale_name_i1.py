"""Tests — I1: retirado, no queda espejo con el que comparar la identidad.

Este módulo verificaba que el espejo ``orders.Order.order_number`` naciera
igual a ``sale.SaleOrder.name`` (decisión I1, H-API-29): dos columnas
UNIQUE, dos modelos, una identidad publicada por conveniencia en ambos.

El retiro del addon espejo ``orders`` (SOL-098, ``api@77bd1f0``, ver
``test_sale_order_v1.py``) le quitó el sujeto al test por los dos lados:

- ``confirm_draft_order`` ya no devuelve un segundo objeto "legacy" — la
  venta **es** la orden, no hay ``order_number`` que comparar contra
  ``sale.name``.
- ``SaleOrder`` no declara columna ``order_number`` (verificado:
  ``src/addons/sale/models/sale_order.py`` sólo tiene ``name``).

La identidad pública sigue siendo ``sale.name`` (formato ``S00001…``,
acuñado por ``action_confirm`` vía ``ir.sequence`` — ver
``sale_order.py:_next_sale_name``); esa cobertura vive en
``test_sale_order_parity_e1.py`` y en el propio ``sale_order.py``. No hay
nada más que este módulo pueda ejercer.
"""
