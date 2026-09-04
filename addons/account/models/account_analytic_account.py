"""Lo que ``account`` le cuelga de ``account.analytic.account`` — ≙ ``_inherit``.

Adaptación de Odoo ``addons/account/models/account_analytic_account.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 78 líneas, 4 ``def``: medido
por AST — ``AccountAnalyticAccount``: ``_compute_invoice_count``,
``_compute_vendor_bill_count``, ``action_view_invoice``,
``action_view_vendor_bill``). Extiende ``account.analytic.account`` — ya
portado en ``analytic/models/analytic_account.py`` — con el conteo de
facturas/notas de crédito de cliente y de proveedor imputadas a esta cuenta
analítica.

Porte de los 4 símbolos — tarea **#526**
=========================================

Este archivo estuvo bloqueado por dos piezas y las dos cayeron:

1. ``AccountMove.get_sale_types``/``get_purchase_types`` — portados con los
   once predicados de tipo de asiento (``account_move.py``, ≙ ``odoo19c:
   account_move.py:6468-6506``).
2. ``AccountMoveLine.analytic_distribution`` — el apunte hereda
   ``analytic.mixin`` desde este pase, tal como la referencia lo declara
   (``odoo19c: account_move_line.py:21``, ``_inherit = ["analytic.mixin"]``),
   con su columna, su índice GIN y su búsqueda por cuenta analítica.

Los dos conteos se portan enteros. La agregación de la fuente
—``_read_group([...], ['analytic_distribution'], ['__count'])``— no se puede
expresar como ``values().annotate(Count())`` porque agruparía por el objeto
JSON completo, no por la cuenta que sus claves nombran: dos distribuciones que
compartan una cuenta caerían en grupos distintos. El equivalente fiel es
consultar por cuenta con el mismo predicado de solapamiento que la fuente usa
—``_search_analytic_distribution``, portado en el mixin— y contar. Cuesta una
consulta por cuenta en vez de una por lote; ``_compute_*`` de la fuente
tampoco promete lo contrario, porque su ``_read_group`` recorre ``self``.

``action_view_invoice`` / ``action_view_vendor_bill`` — divergencia de
mecanismo declarada: devuelven un diccionario ``ir.actions.act_window``, la
descripción de una ventana del cliente web de Odoo. Este árbol no sirve ese
cliente; su equivalente sería un endpoint DRF, que no es este símbolo. Lo que
sí se porta de ellos es su **consulta**, que es idéntica a la de los conteos y
queda disponible en ``move_lines_for``.
"""
from addons.account.models.account_move import AccountMove
from addons.account.models.account_move_line import AccountMoveLine
from addons.analytic.models.analytic_account import AccountAnalyticAccount


def move_lines_for(account_ids, move_types):
    """Los apuntes contabilizados de esos tipos imputados a esas cuentas.

    La consulta que los cuatro símbolos de la referencia comparten: el
    predicado de ``('analytic_distribution', 'in', ids)`` más el filtro por
    ``parent_state`` y por ``move_type``. ``parent_state`` es el ``related``
    que la fuente declara sobre ``move_id.state``; aquí se recorre la FK.
    """
    if not account_ids:
        return AccountMoveLine.objects.none()
    return AccountMoveLine.objects.filter(
        AccountMoveLine._search_analytic_distribution('in', list(account_ids)),
        move__state='posted',
        move__move_type__in=move_types,
    )


def _count_by_account(account, move_types):
    """El conteo de una cuenta — el cuerpo comun de los dos ``_compute_*``."""
    return move_lines_for([account.pk], move_types).count()


def compute_invoice_count(account):
    """≙ ``_compute_invoice_count`` (``odoo19c: :18-30``)."""
    return _count_by_account(account, AccountMove.get_sale_types(include_receipts=True))


def compute_vendor_bill_count(account):
    """≙ ``_compute_vendor_bill_count`` (``odoo19c: :32-46``)."""
    return _count_by_account(
        account, AccountMove.get_purchase_types(include_receipts=True))


def apply_account_extensions():
    """Cuelga ``invoice_count`` y ``vendor_bill_count`` de la cuenta analítica.

    La fuente los declara ``fields.Integer(compute=...)`` sin ``store``: son
    derivados que se leen, no columnas. El equivalente de un campo calculado no
    persistido es una ``property``, y colgarla desde este addon es lo que
    ``_inherit = 'account.analytic.account'`` hace allá.

    Idempotente: re-invocarla no duplica nada. Cableada en
    ``AccountConfig.ready()`` vía ``_EXTENSIONES``.
    """
    AccountAnalyticAccount.invoice_count = property(compute_invoice_count)
    AccountAnalyticAccount.vendor_bill_count = property(compute_vendor_bill_count)
    return None
