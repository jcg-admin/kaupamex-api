"""Lo que ``account`` le cuelga de ``account.analytic.account`` — ≙ ``_inherit``.

Adaptación de Odoo ``addons/account/models/account_analytic_account.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 78 líneas, 4 ``def``: medido
por AST — ``AccountAnalyticAccount``: ``_compute_invoice_count``,
``_compute_vendor_bill_count``, ``action_view_invoice``,
``action_view_vendor_bill``). Extiende ``account.analytic.account`` — ya
portado en ``analytic/models/analytic_account.py`` — con el conteo de
facturas/notas de crédito de cliente y de proveedor imputadas a esta cuenta
analítica.

Porte BLOQUEADO — 4 de 4 símbolos, y ya sólo por UNA pieza
==========================================================

De los dos bloqueadores que este docstring citaba, uno cayó: ``AccountMove``
declara ``get_sale_types``/``get_purchase_types`` desde el pase de los once
predicados de tipo de asiento (``account_move.py``, ≙ ``odoo19c:
account_move.py:6468-6506``). El docstring ya decía que esa mitad "NO es el
bloqueo real"; ahora además es falsa como premisa, y se corrige aquí en vez de
envejecer (Clausula 2 del principio rector).

Queda **uno**, y es el real:

BLOQUEADO por ``AccountMoveLine.analytic_distribution`` — el enlace entre un
apunte contable y una cuenta analítica. La referencia lo declara heredando
``analytic.mixin`` (``odoo19c: account_move_line.py:21``, ``_inherit =
["analytic.mixin"]``); aquí el mixin existe
(``addons/analytic/models/analytic_mixin.py:81``, con su
``analytic_distribution = fields.Json``) y ``AccountMoveLine`` **no lo hereda**
— medido: ``grep -n "AnalyticMixin" addons/account/models/account_move_line.py``
→ 0 hits. No es una carencia del stack: es un ``_inherit`` sin portar, y su
cierre es la tarea **#526**.

``action_view_invoice``/``action_view_vendor_bill`` tienen, además, la segunda
razón independiente ya declarada arriba: devuelven un diccionario
``ir.actions.act_window`` que ningún cliente de esta API consume.

Sucesor: tarea **#526** — heredar ``analytic.mixin`` en ``account.move.line``
con su migración, y entonces portar ``_compute_invoice_count`` y
``_compute_vendor_bill_count``.
"""


def apply_account_extensions():
    """No-op documentado — ninguno de los 4 símbolos de la referencia se porta.

    Se conserva la función (en vez de omitir el archivo) por el precedente de
    ``addons/stock/models/barcode.py``: *"un porte bloqueado se declara donde
    la referencia lo declara... un archivo ausente no se distingue de un
    archivo olvidado"*. Cableada en ``AccountConfig.ready()`` vía
    ``_EXTENSIONES`` (tarea #520 — el nombre de la función se unificó a
    ``apply_account_extensions`` para que el llamador uniforme de ``ready()``
    la encuentre; antes se llamaba ``apply_account_analytic_account_extensions``
    y NO estaba cableada). Invocable a mano; ver
    ``tests/unit/account/test_account_analytic_account.py``.
    """
    return None
