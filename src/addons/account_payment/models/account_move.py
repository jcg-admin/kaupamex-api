"""``account.move`` — lo que ``account_payment`` le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: account_payment/models/account_move.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3, 183
líneas) — atribución y aviso de licencia preservados (DEC-KX-03).

16 símbolos en la referencia (4 campos + 12 métodos). Portados 5 (como
propiedades no-almacenadas, DEC-SALE-01), 11 no portados con su razón
medida.

Portado
========

===================================  ==================================================
Símbolo de la referencia              Aquí
===================================  ==================================================
``transaction_ids``                   propiedad ``transaction_ids`` (queryset de
                                       ``payment.Payment`` vía ``AccountMoveTransaction
                                       Link``)
``transaction_count``                 propiedad ``transaction_count``
``amount_paid``                       propiedad ``amount_paid``
``_compute_transaction_count``        lógica de la propiedad ``transaction_count``
``_compute_amount_paid``              lógica de la propiedad ``amount_paid``
===================================  ==================================================

No portado (declarado, no improvisado)
=========================================

- **``authorized_transaction_ids`` / ``_compute_authorized_transaction_ids``
  / ``payment_action_capture`` / ``payment_action_void``** —
  ``payment.Payment.STATUSES`` (``api: payment/models/payment.py:37-50``,
  medido) es ``PENDING``/``APPROVED``/``FAILED``/``REFUNDED``/
  ``PARTIALLY_REFUNDED``/``CANCELLED`` — **0 estado ``authorized``**. El
  flujo de dos pasos autorizar→capturar/anular que estos cuatro símbolos
  implementan no existe en este núcleo: ``Payment`` sólo modela el
  resultado final de un intento (aprobado/fallido/etc.), no un estado
  intermedio retenido. Condición de cierre: si ``payment.Payment`` agrega
  un estado de autorización (decisión de producto sobre ``payment``, fuera
  de este addon), estos cuatro son portables directamente.
- **``amount_paid``** SÍ se porta, pero sumando sólo transacciones
  ``STATUS_APPROVED`` (el análogo más cercano a "authorized o done" cuando
  no existe el estado intermedio) — divergencia declarada, no un olvido de
  ``authorized``.
- **``_has_to_be_paid`` / ``_get_online_payment_error``** — necesitan
  ``amount_residual``, ``payment_state``, ``currency_id.is_zero()`` y el
  parámetro ``account_payment.enable_portal_payment`` (éste SÍ se porta,
  ver ``data/config_parameters.py``). ``api: account/models/account_move.py``
  (medido: ``name``/``ref``/``date``/``state``/``move_type``/``journal``/
  ``partner``/``currency``/``company``/``amount_total`` — 10 campos) **no
  declara** ``amount_residual`` ni ``payment_state``: no hay motor de
  reconciliación que los compute. Construirlos exige diseñar ese motor —
  fuera del alcance de este addon (tocaría ``account/``, prohibido para
  este agente).
- **``get_portal_last_transaction``** — contexto de sesión portal
  (``with_context(active_test=False)``). Sin portal aquí.
- **``action_view_payment_transactions``** — devuelve ``ir.actions.act_
  window`` (UI). ``transaction_ids``/``transaction_count`` ya están
  expuestos para un futuro serializer.
- **``_get_default_payment_link_values`` / ``_generate_portal_payment_qr``
  / ``_get_portal_payment_link``** — generan el enlace/QR de pago portal
  (``payment.link.wizard``, ``ir.actions.report``). ``wizards/`` está
  fuera del alcance explícito de esta tarea, y no hay generador de barcode
  ni acceso portal por token en este stack.
"""
from decimal import Decimal

from django.db.models import Sum

from addons.account.models.account_move import AccountMove
from addons.account_payment.models.links import AccountMoveTransactionLink
from addons.payment.models import Payment

#: Único estado de ``payment.Payment`` que cuenta como "cobrado" cuando no
#: existe el intermedio ``authorized`` de la referencia — ver "No portado".
_PAID_STATUSES = (Payment.STATUS_APPROVED,)


def _get_transaction_ids(self):
    """Los pagos vinculados a esta factura — ≙ ``transaction_ids``."""
    return Payment.objects.filter(invoice_links__move=self)


def _get_transaction_count(self):
    """≙ ``_compute_transaction_count`` (``odoo19c: account_payment/models/
    account_move.py:39-42``)."""
    return AccountMoveTransactionLink.objects.filter(move=self).count()


def _get_amount_paid(self):
    """Suma de los pagos ``APPROVED`` vinculados — ≙ ``_compute_amount_paid``
    (``odoo19c: account_payment/models/account_move.py:44-53``), con
    ``_PAID_STATUSES`` en vez de ``('authorized', 'done')`` (divergencia del
    docstring del módulo — ``Payment`` no tiene estado ``authorized``)."""
    total = Payment.objects.filter(
        invoice_links__move=self, status__in=_PAID_STATUSES,
    ).aggregate(total=Sum('amount'))['total']
    return total or Decimal('0.00')


def apply_account_payment_extensions():
    """≙ ``_inherit = 'account.move'`` de ``account_payment``.

    Se llama desde ``AccountPaymentConfig.ready()``.
    """
    for nombre, getter in (
        ('transaction_ids', _get_transaction_ids),
        ('transaction_count', _get_transaction_count),
        ('amount_paid', _get_amount_paid),
    ):
        if not hasattr(AccountMove, nombre):
            setattr(AccountMove, nombre, property(getter))
