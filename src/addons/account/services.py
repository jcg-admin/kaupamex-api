"""Servicios de dominio del addon ``account`` — creación de facturas.

Cablea el eje de factura ``account.move`` (H-API-08): emite una factura de
cliente (``out_invoice``) a partir de una orden de venta confirmada, análogo a
Odoo ``sale.order._create_invoices()``. Vive en ``account`` (el paquete dueño de
``AccountMove``) y **lee** la orden por *duck typing* — no importa ``sale``, para
no invertir el acoplamiento (``account`` es la capa contable base).

Rebanada 1 (H-API-08): construir el asiento balanceado de doble entrada. La
resolución automática de ``company`` desde la ``SaleOrder`` (FK que añade #185
SOL-085 S3) y el disparo automático en ``action_confirm`` (etapa 4a/5) son
sub-rebanadas posteriores; aquí la ``company`` emisora se pasa explícita.
"""
from decimal import Decimal

from django.utils import timezone

from exceptions import UserError
from tools.translate import _

from addons.account.models import (
    AccountAccount,
    AccountJournal,
    AccountMove,
    AccountMoveLine,
)

# Odoo SALE_ORDER_STATE: 'sale' = orden confirmada (sale/models/sale_order.py).
_STATE_CONFIRMED = 'sale'


def _require_account(company, account_type: str, label: str) -> AccountAccount:
    account = (AccountAccount.objects
               .filter(company=company, account_type=account_type,
                       deprecated=False)
               .order_by('code').first())
    if account is None:
        raise UserError(_(
            'La empresa no tiene una cuenta contable de tipo "%(label)s".'
        ) % {'label': label})
    return account


def create_invoice_from_sale_order(order, company) -> AccountMove:
    """Crea (sin postear) un ``account.move`` ``out_invoice`` desde ``order``.

    Espeja Odoo ``sale.order._create_invoices``: una factura de cliente con el
    total a débito de la cuenta por cobrar y el desglose (subtotal a ingreso,
    IVA a la cuenta de impuesto trasladado) a crédito, de modo que el asiento
    quede balanceado y ``AccountMove.post()`` lo acepte. Devuelve el asiento en
    ``draft``; el llamador decide cuándo ``post()``.

    :param order: orden de venta confirmada (``state='sale'`` con líneas).
    :param company: empresa emisora (``company.Company``).
    :raises UserError: si la orden no está confirmada o sin líneas, o si a la
        empresa le falta el diario de ventas o las cuentas requeridas.
    """
    if getattr(order, 'state', None) != _STATE_CONFIRMED:
        raise UserError(_('Solo se factura una orden de venta confirmada.'))
    if not order.order_line.exists():
        raise UserError(_('No se puede facturar una orden sin líneas.'))

    journal = (AccountJournal.objects
               .filter(company=company, type='sale', active=True)
               .order_by('code').first())
    if journal is None:
        raise UserError(_('La empresa no tiene un diario de ventas.'))

    receivable = _require_account(company, 'asset_receivable', 'Por cobrar')
    income = _require_account(company, 'income', 'Ingreso')

    untaxed = order.amount_untaxed()
    tax = order.amount_tax()
    total = order.amount_total()

    move = AccountMove.objects.create(
        move_type='out_invoice',
        date=timezone.now().date(),
        journal=journal,
        partner=order.partner,
        company=company,
    )

    # Doble entrada (Odoo _check_balanced): débito por cobrar == crédito ingreso
    # + crédito IVA.
    AccountMoveLine.objects.create(
        move=move, account=receivable, name=order.name or _('Factura'),
        debit=total, credit=Decimal('0.00'),
    )
    AccountMoveLine.objects.create(
        move=move, account=income, name=_('Ingreso por venta'),
        debit=Decimal('0.00'), credit=untaxed, display_type='product',
    )
    if tax > Decimal('0.00'):
        tax_account = _require_account(company, 'liability_current',
                                       'IVA trasladado')
        AccountMoveLine.objects.create(
            move=move, account=tax_account, name=_('IVA trasladado'),
            debit=Decimal('0.00'), credit=tax, display_type='tax',
        )

    return move


def create_refund_from_invoice(invoice) -> AccountMove:
    """Crea (sin postear) un ``out_refund`` que revierte ``invoice``.

    Nota de crédito de cliente: espeja Odoo ``account.move._reverse_moves``.
    Cada apunte de la factura se copia con débito/crédito **intercambiados**
    sobre la misma cuenta, de modo que el asiento queda balanceado por
    construcción (si la factura cuadraba, su reversión cuadra). Devuelve el
    asiento en ``draft``; el llamador decide cuándo ``post()``.

    :param invoice: factura de cliente **publicada** (``out_invoice``/``posted``).
    :raises UserError: si el asiento no es una factura de cliente o no está
        publicado.
    """
    if getattr(invoice, 'move_type', None) != 'out_invoice':
        raise UserError(_('Solo se puede acreditar una factura de cliente.'))
    if invoice.state != 'posted':
        raise UserError(_('Solo se puede acreditar una factura publicada.'))

    refund = AccountMove.objects.create(
        move_type='out_refund',
        date=timezone.now().date(),
        journal=invoice.journal,
        partner=invoice.partner,
        currency=invoice.currency,
        company=invoice.company,
        ref=invoice.name,
    )
    for line in invoice.line_ids.all():
        AccountMoveLine.objects.create(
            move=refund, account=line.account, name=line.name,
            debit=line.credit, credit=line.debit,  # reversión de la factura
            display_type=line.display_type,
        )

    return refund


def create_invoice_from_subscription(sub_invoice, company) -> AccountMove:
    """Crea (sin postear) un ``out_invoice`` del cobro L0 en los libros de
    ``company`` (Kaupamex, el operador de plataforma) desde una
    ``SubscriptionInvoice`` (H-API-05).

    A diferencia de ``create_invoice_from_sale_order`` (desglose por línea), el
    cobro de suscripción es de un solo importe: por cobrar (débito) contra
    ingreso de plataforma (crédito), balanceado por construcción. Sin línea de
    IVA (el tratamiento fiscal del cobro L0 es una decisión aparte). El
    ``company`` emisora la pasa el llamador (``get_system()``) — así ``account``
    no importa ``company`` y *duck-typea* la ``sub_invoice``.

    :param sub_invoice: ``SubscriptionInvoice`` con ``amount`` a cobrar.
    :param company: empresa emisora (la system company / Kaupamex).
    :raises UserError: si el importe no es positivo, o a la empresa le faltan el
        diario de ventas o las cuentas requeridas.
    """
    amount = getattr(sub_invoice, 'amount', None)
    if amount is None or amount <= Decimal('0.00'):
        raise UserError(_('La factura de suscripción no tiene importe a cobrar.'))
    journal = (AccountJournal.objects
               .filter(company=company, type='sale', active=True)
               .order_by('code').first())
    if journal is None:
        raise UserError(_('La empresa no tiene un diario de ventas.'))
    receivable = _require_account(company, 'asset_receivable', 'Por cobrar')
    income = _require_account(company, 'income', 'Ingreso')

    ref = f'SUB/{sub_invoice.subscription_id}/{sub_invoice.period}'
    move = AccountMove.objects.create(
        move_type='out_invoice', date=timezone.now().date(),
        journal=journal, company=company, ref=ref,
    )
    AccountMoveLine.objects.create(
        move=move, account=receivable, name=ref,
        debit=amount, credit=Decimal('0.00'),
    )
    AccountMoveLine.objects.create(
        move=move, account=income, name=_('Ingreso por suscripción'),
        debit=Decimal('0.00'), credit=amount, display_type='product',
    )
    return move
