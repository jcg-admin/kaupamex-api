"""``stock.picking`` — el aviso de lote caducado antes de validar.

Adaptación de Odoo ``product_expiry/models/stock_picking.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3) — atribución y aviso de
licencia preservados (DEC-KX-03).

Porte BLOQUEADO — 0 de 3 símbolos
===================================

``odoo19c: addons/product_expiry/models/stock_picking.py`` (48 líneas):
3 métodos.

=========================================  =========================================
Símbolo de la referencia (línea)           Estado
=========================================  =========================================
``_pre_action_done_hook`` (10-19)          bloqueado
``_check_expired_lots`` (21-23)            bloqueado
``_action_generate_expired_wizard`` (25-48) bloqueado
=========================================  =========================================

Dos piezas ausentes, las dos nombradas
----------------------------------------

1. **``move_line_ids``.** Los tres métodos parten de
   ``self.move_line_ids.filtered(lambda ml: ml.lot_id.product_expiry_alert or
   ...)``. El puerto de ``stock.picking``
   (``api: addons/stock/models/stock_picking.py``) declara 5 campos —
   ``name``, ``state``, ``location``, ``location_dest``, ``sale_order`` — y
   ninguna línea de movimiento; ``stock.move.line`` ni siquiera existe como
   modelo (ver ``stock_move_line.py`` de este addon). Sin ese conjunto no hay
   qué filtrar.
2. **``expiry.picking.confirmation``.** ``_action_generate_expired_wizard``
   devuelve un ``ir.actions.act_window`` que abre el asistente de confirmación
   del cliente Odoo. Este árbol no tiene ni el wizard —está en
   ``odoo19c: product_expiry/wizard/confirm_expiry.py``, fuera de ``models/``—
   ni la capa de acciones de ventana.

El **gancho** sí tiene análogo: ``StockPicking.button_validate``
(``api: addons/stock/models/stock_picking.py:90``) es el punto donde la
referencia inserta ``_pre_action_done_hook``. Encadenar ahí es trivial; lo que
falta es el **contenido** del aviso, no el sitio.

Qué desbloquea el porte
-------------------------

``stock.move.line`` con ``lot_id`` y ``removal_date`` — sucesor: tarea
**#274**. El wizard es una decisión aparte: sin capa de vistas, el equivalente
natural es un ``400`` con ``codigo_error`` desde el endpoint de validación, y
esa forma la fija la API REST, no este modelo. Sucesor de esa mitad: tarea
**#279**.
"""


def apply_product_expiry_extensions():
    """No-op declarado — ver el docstring del módulo.

    Mismo criterio que ``stock_move_line.py``: el archivo entra ya en
    ``_EXTENSIONES`` para que el porte futuro sea llenar una función, no
    redescubrir que falta un archivo.
    """
    return None


__all__ = ['apply_product_expiry_extensions']
