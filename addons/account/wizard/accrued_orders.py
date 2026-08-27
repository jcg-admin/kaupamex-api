"""``account.accrued.orders.wizard`` — asiento de devengo desde órdenes.

Adaptación de Odoo ``addons/account/wizard/accrued_orders.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3 —
atribución y aviso de licencia preservados, DEC-KX-03).

``TransientModel`` → clase con classmethods, no tabla — mismo patrón que
``AccountDebitNoteWizard``.

Veinte símbolos de la referencia (10 campos + 10 defs) — el desglose
=====================================================================

=========================================  ================================
Símbolo de la referencia                    Qué pasa aquí
=========================================  ================================
``company_id`` (campo)                      PORTADO — ``_get_default_company``
``journal_id`` (campo)                      PORTADO — ``_compute_journal_id``
``date`` (campo)                            PORTADO — ``_get_default_date``
``reversal_date`` (campo)                   PORTADO — ``_compute_reversal_date``
``amount`` (campo)                          PORTADO — parámetro ``amount``
``currency_id`` (related)                   NO — utilería de widget
                                             monetario del formulario
                                             (``related='company_id.
                                             currency_id'``); el llamador
                                             ya tiene la empresa.
``account_id`` (campo)                      PORTADO — parámetro ``account``
``preview_data`` (compute)                  NO — bloqueado por
                                             ``account.move.
                                             _move_dict_to_preview_vals``
                                             (el previsualizador del
                                             cliente web, no portado).
``display_amount`` (compute)                PORTADO —
                                             ``_compute_display_amount``
                                             (recibe ``lines`` en vez de
                                             releer ``preview_data``)
``_get_default_company``                    PORTADO
``_get_default_date``                       PORTADO
``_compute_display_amount``                 PORTADO
``_compute_reversal_date``                  PORTADO
``_compute_journal_id``                     PORTADO
``_compute_preview_data``                   NO — ver ``preview_data``.
``_get_computed_account``                   PORTADO
``_compute_move_vals``                      PORTADO (parcial declarado —
                                             ver su docstring)
``_get_accrual_message_body``               NO — compone HTML de chatter
                                             con ``move._get_html_link``;
                                             el chatter de ``mail`` sobre
                                             ``account.move`` no está
                                             portado.
``create_entries``                          PORTADO (sin el
                                             ``message_post`` final ni el
                                             ``ir.actions.act_window`` —
                                             misma exclusión que
                                             ``AccountDebitNoteWizard``)
``_get_product_expense_and_stock_var_accounts``  PORTADO — verbatim
                                             (``(False, False)``; es el
                                             hook que ``stock_account``
                                             sobreescribe).
=========================================  ================================

``_compute_move_vals`` — qué mitad se porta y por qué
======================================================

La referencia tiene dos ramas:

1. **Monto manual** (una sola orden + ``amount``): una línea por el monto a
   la cuenta del producto y la contrapartida global a ``account``. Esta
   rama se porta entera.
2. **Devengo por línea de orden**: calcula cantidad facturada/entregada *a
   la fecha* (``qty_invoiced_at_date`` / ``qty_received_at_date`` /
   ``qty_delivered_at_date`` / ``amount_to_invoice_at_date``), impuestos
   incluidos en precio, diferencias de precio y valuación perpetua.
   **Bloqueada por esos campos at-date de las líneas de orden**: el puerto
   de ``sale_order_line.py`` (medido) declara ``product`` / ``price_unit``
   / ``discount`` / totales, sin las cantidades a fecha ni
   ``analytic_distribution`` / ``display_type`` / ``is_downpayment``.
   Cuando el porte de ``sale``/``purchase`` incorpore la facturación por
   cantidades, esta rama se completa aquí — la estructura (``_get_aml_vals``
   y el ensamblado del asiento) ya queda escrita.

Otras divergencias declaradas: ``analytic_distribution`` y
``amount_currency``/multi-moneda no existen en el puerto de
``account.move.line`` (mismas exclusiones que ``account_partial_reconcile``);
``formatLang``/``format_date`` (formato por locale) → f-string/isoformat.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction

from addons.account.models.account_journal import AccountJournal
from addons.account.models.account_move import AccountMove
from addons.account.models.account_move_line import AccountMoveLine
from addons.account.models.product import get_product_accounts
from addons.account.wizard.account_move_reversal import AccountMoveReversal
from exceptions import UserError
from orm.models_transient import TransientModel
from tools.translate import _


def _ellipsis(string, size):
    """≙ el helper interno ``_ellipsis`` de ``_compute_move_vals``."""
    if len(string) > size:
        return string[0:size - 3] + '...'
    return string


class AccountAccruedOrdersWizard(TransientModel):
    """≙ ``account.accrued.orders.wizard`` — genera el asiento de devengo de
    las órdenes seleccionadas y su reverso al día siguiente."""

    _name = 'account.accrued.orders.wizard'
    _description = 'Accrued Orders Wizard'
    _check_company_auto = True

    class Meta:
        abstract = True
        managed = False

    @classmethod
    def _get_default_company(cls, orders):
        """≙ ``_get_default_company`` — la empresa de la primera orden."""
        orders = list(orders)
        return orders[0].company if orders else None

    @classmethod
    def _get_default_date(cls, today=None):
        """≙ ``_get_default_date`` — el último día del mes anterior
        (``date_utils.get_month(today)[0] - 1 día`` de la referencia,
        con el primer día del mes calculado aquí)."""
        today = today or date.today()
        return today.replace(day=1) - timedelta(days=1)

    @classmethod
    def _compute_display_amount(cls, amount, single_order, lines):
        """≙ ``_compute_display_amount`` — mostrar el monto manual cuando ya
        hay uno, o cuando es una sola orden sin líneas devengables."""
        return bool(amount) or (single_order and not lines)

    @classmethod
    def _compute_reversal_date(cls, accrual_date, reversal_date=None):
        """≙ ``_compute_reversal_date`` — el día siguiente al devengo, salvo
        que el llamador ya haya fijado una posterior."""
        if accrual_date and (not reversal_date or reversal_date <= accrual_date):
            return accrual_date + timedelta(days=1)
        return reversal_date

    @classmethod
    def _compute_journal_id(cls, company):
        """≙ ``_compute_journal_id`` — el primer diario general de la
        empresa."""
        return AccountJournal.objects.filter(
            company=company, type='general').first()

    @classmethod
    def _get_computed_account(cls, order, product, is_purchase):
        """≙ ``_get_computed_account`` — la cuenta de gasto o ingreso del
        producto. La posición fiscal de la orden no está portada
        (divergencia declarada): resolución cruda de
        ``get_product_accounts``."""
        accounts = get_product_accounts(product)
        if is_purchase:
            return accounts['expense']
        return accounts['income']

    @classmethod
    def _compute_move_vals(cls, orders, company, journal, accrual_date,
                            account, amount=None, is_purchase=False):
        """≙ ``_compute_move_vals`` (parcial declarado — sólo la rama de
        monto manual; ver el docstring del módulo).

        Devuelve ``(move_vals, orders_with_entries)`` con la misma forma que
        la referencia: ``move_vals`` trae ``line_ids`` como lista de dicts.
        """
        def _get_aml_vals(balance, account_id, label=""):
            """≙ el helper interno ``_get_aml_vals`` — sin
            ``amount_currency``/``analytic_distribution`` (divergencias
            declaradas en el módulo)."""
            if not is_purchase:
                balance = -balance
            return {
                'name': label,
                'debit': balance if balance > 0 else Decimal('0.00'),
                'credit': -balance if balance < 0 else Decimal('0.00'),
                'account_id': account_id,
            }

        orders = list(orders)
        if any(order.company_id != company.pk for order in orders):
            raise UserError(_(
                'Entries can only be created for a single company at a '
                'time.'))

        move_lines = []
        orders_with_entries = []
        total_balance = Decimal('0.00')

        if len(orders) == 1 and amount:
            order = orders[0]
            order_line = order.order_line.filter(product__isnull=False).first()
            if order_line is None:
                raise UserError(_(
                    'La orden no tiene líneas con producto para devengar.'))
            total_balance = Decimal(amount)
            accrual_account = cls._get_computed_account(
                order, order_line.product, is_purchase)
            move_lines.append(_get_aml_vals(
                Decimal(amount), accrual_account.pk, label=_('Manual entry')))
        else:
            # Rama de devengo por línea — bloqueada por los campos at-date
            # de las líneas de orden (ver el docstring del módulo).
            raise UserError(_(
                'El devengo por línea de orden requiere las cantidades '
                'facturadas/entregadas a fecha, aún no portadas en '
                'sale/purchase — usa el monto manual sobre una sola orden.'))

        if total_balance != Decimal('0.00'):
            # Contrapartida global — ≙ la línea "Accrued total".
            move_lines.append(_get_aml_vals(
                -total_balance, account.pk, label=_('Accrued total')))

        move_type = _('Expense') if is_purchase else _('Revenue')
        move_vals = {
            'ref': _('Accrued %(entry_type)s entry as of %(date)s') % {
                'entry_type': move_type,
                'date': accrual_date.isoformat(),
            },
            'name': '/',
            'journal': journal,
            'date': accrual_date,
            'line_ids': move_lines,
        }
        return move_vals, orders_with_entries

    @classmethod
    @transaction.atomic
    def create_entries(cls, orders, company, journal, accrual_date,
                        reversal_date, account, amount=None,
                        is_purchase=False):
        """≙ ``create_entries`` — crea y publica el devengo y su reverso.

        Sin el ``message_post`` a las órdenes (chatter no portado) y
        devolviendo ``(move, reverse_move)`` en vez del
        ``ir.actions.act_window`` (ver la tabla del módulo).
        """
        if reversal_date <= accrual_date:
            raise UserError(_('Reversal date must be posterior to date.'))
        move_vals, orders_with_entries = cls._compute_move_vals(
            orders, company, journal, accrual_date, account,
            amount=amount, is_purchase=is_purchase)

        line_vals = move_vals.pop('line_ids')
        move = AccountMove.objects.create(
            move_type='entry', company=company, **move_vals)
        for values in line_vals:
            AccountMoveLine.objects.create(
                move=move,
                account_id=values['account_id'],
                name=values['name'],
                debit=values['debit'],
                credit=values['credit'],
            )
        move.post()

        reverse_move = AccountMoveReversal._reverse_single_move(move, {
            'ref': _('Reversal of: %s') % move.ref,
            'date': reversal_date,
            'journal': journal,
        })
        reverse_move.post()
        # ``orders_with_entries`` queda vacío mientras la rama por línea
        # esté bloqueada — el message_post de la referencia tampoco aplica.
        return move, reverse_move

    @classmethod
    def _get_product_expense_and_stock_var_accounts(cls, product):
        """≙ ``_get_product_expense_and_stock_var_accounts`` — verbatim: el
        hook que ``stock_account`` sobreescribe con la valuación perpetua."""
        return (False, False)
