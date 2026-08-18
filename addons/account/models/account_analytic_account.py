"""Lo que ``account`` le cuelga de ``account.analytic.account`` — ≙ ``_inherit``.

Adaptación de Odoo ``addons/account/models/account_analytic_account.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 78 líneas, 4 ``def``: medido
por AST — ``AccountAnalyticAccount``: ``_compute_invoice_count``,
``_compute_vendor_bill_count``, ``action_view_invoice``,
``action_view_vendor_bill``). Extiende ``account.analytic.account`` — ya
portado en ``analytic/models/analytic_account.py`` — con el conteo de
facturas/notas de crédito de cliente y de proveedor imputadas a esta cuenta
analítica.

Los cuatro símbolos — BLOQUEADO, ninguno se porta
==================================================

Los cuatro dependen de la misma pieza ausente: **el enlace entre un apunte
contable y una cuenta analítica**. En la referencia ese enlace es
``account.move.line.analytic_distribution`` (columna ``jsonb``,
``odoo19c: account_move_line.py``); en este árbol ``account.move.line``
(``account_move_line.py:43-98``) **no declara ese campo** — medido:
``grep -n "analytic" addons/account/models/account_move_line.py`` → 0 hits.

``account_move_line.py`` **no está en la lista de archivos escribibles de este
pase** (tramo 2 de la tarea #398), así que el campo no se puede añadir aquí. Y
aunque se pudiera —vía ``add_to_class`` desde una extensión, sin tocar el
archivo—, el destino real es peor: ``account.move.line`` vive en el app
**``account``**, así que una columna nueva ahí generaría su migración en
``addons/account/migrations/`` (sí escribible) — **eso sí sería viable en un
pase que declarara ese archivo en su alcance**. La condición de cierre de este
bloqueo es, por tanto, un alcance más amplio, no una imposibilidad del stack.

Además, aun con ``analytic_distribution`` resuelto, los dos métodos de conteo
llaman ``self.env['account.move'].get_sale_types(include_receipts=True)`` /
``get_purchase_types(include_receipts=True)`` (``odoo19c:`` líneas 20, 36).
``account.move`` en este árbol (``account_move.py:22-385``) no declara ninguno
de los dos — medido: ``grep -n "def get_sale_types\\|def get_purchase_types"
addons/account/models/account_move.py`` → 0 hits. Son clasificadores estáticos
de ``AccountMove.MOVE_TYPES`` (ya declarado aquí,
``account_move.py:62-70``: ``out_invoice``/``out_refund``/``out_receipt`` de
venta, ``in_invoice``/``in_refund``/``in_receipt`` de compra) — trivialmente
reconstruibles sin tocar ``account_move.py``, así que esa mitad NO es el
bloqueo real.

``action_view_invoice``/``action_view_vendor_bill`` tienen, además, una
segunda razón —independiente de la anterior—: devuelven un diccionario
``ir.actions.act_window`` (``odoo19c:`` líneas 56-63, 71-77), el formato que
el cliente web de Odoo interpreta para abrir una vista. Esta API es DRF, sin
cliente web propio: no hay consumidor de ese diccionario. Ver el mismo
criterio ya aplicado a ``on_change_unit_amount``/``view_header_get`` en
``account_analytic_line.py`` de este mismo tramo.

Sucesor: tarea PENDIENTE DE ASIGNAR — declarar ``account_move_line.py`` en el
alcance de un pase, añadir ``analytic_distribution`` (o el enlace explícito
vía ``account.analytic.line.move_line`` que ``account_analytic_line.py``
también deja bloqueado por la misma familia de causas), con su migración en
``addons/account/migrations/``, y entonces recuperar este archivo.
"""


def apply_account_analytic_account_extensions():
    """No-op documentado — ninguno de los 4 símbolos de la referencia se porta.

    Se conserva la función (en vez de omitir el archivo) por el precedente de
    ``addons/stock/models/barcode.py``: *"un porte bloqueado se declara donde
    la referencia lo declara... un archivo ausente no se distingue de un
    archivo olvidado"*. Cableada por la MISMA vía que las demás extensiones de
    ``account`` (``AccountConfig._EXTENSIONES`` + ``ready()``) — pero
    ``addons/account/apps.py`` **no está en la lista de archivos escribibles
    de este tramo**, así que el cableado real es también parte del sucesor
    de arriba. Hasta entonces, invocable a mano (y así se prueba: ver
    ``tests/unit/account/test_account_analytic_account.py``).
    """
    return None
