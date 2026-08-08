"""``account.payment`` — lo que ``account_payment`` le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: account_payment/models/account_payment.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3) —
atribución y aviso de licencia preservados (DEC-KX-03).

18 símbolos en la referencia (7 campos + 11 métodos, ``wc -l`` cuenta 231
líneas). Aquí, 8 portados como propiedades no-almacenadas (DEC-SALE-01, ver
``models/links.py``) que navegan ``AccountPaymentTransaction``, 10 NO
portados con su razón medida.

Portado
========

===================================  ==================================================
Símbolo de la referencia              Aquí
===================================  ==================================================
``payment_transaction_id``            propiedad ``payment_transaction`` (get/set)
``payment_token_id``                  propiedad ``payment_token`` (get/set)
``source_payment_id``                 propiedad ``source_payment`` (get/set)
``_compute_amount_available_for_refund``  propiedad ``amount_available_for_refund``
``_compute_refunds_count``            propiedad ``refunds_count``
``_get_payment_refund_wizard_values``  método homónimo (datos, sin acción de UI)
===================================  ==================================================

Divergencias en lo portado:

1. **``amount_available_for_refund``** no filtra por
   ``tx.provider_id.support_refund``/``payment_method.support_refund``/
   ``tx.operation != 'refund'`` — ``PaymentGateway`` no declara capacidad de
   reembolso por método y ``Payment`` no distingue operación (H-API-97, el
   modelo es más simple que ``payment.transaction``). El cálculo es
   ``monto de la transacción − suma de sus reembolsos APPROBADOS``, sin la
   gating adicional.
2. **``refunds_count``** no filtra por
   ``payment_transaction_id.operation == 'refund'`` (mismo motivo): cuenta
   los ``AccountPaymentTransaction`` cuyo ``source_payment`` es ``self`` —
   cualquier pago que declare a éste como su origen se considera un
   reembolso, que es la única señal de reembolso que este núcleo modela.
3. **Las tres propiedades FK requieren ``self.pk``** (a diferencia de un
   campo Odoo, que puede asignarse en memoria antes de guardar): el enlace
   vive en una fila aparte (``AccountPaymentTransaction``), así que el
   ``account.payment`` debe existir en la base antes de poder enlazarlo.
   Documentado, no oculto — el flujo real (crear el pago, luego enlazar la
   transacción) siempre pasa por un ``account.payment`` ya persistido.

No portado (declarado, no improvisado)
=========================================

- **``suitable_payment_token_ids`` / ``use_electronic_payment_method`` /
  ``_compute_suitable_payment_token_ids`` / ``_compute_use_electronic_
  payment_method`` / ``_onchange_set_payment_token_id``** — dependen de
  ``self.payment_method_line_id`` y de comparar su ``code`` contra
  ``payment.provider._fields['code'].selection``. ``api:
  account/models/account_payment.py`` (9 campos, medido) **no declara**
  ``payment_method_line`` — el pago no navega a una línea de método de pago
  del diario en este núcleo. Condición de cierre: cuando ``account.payment``
  tenga ese enlace (decisión de arquitectura de ``account``, fuera de este
  addon), estas cinco piezas son portables sobre la base de
  ``AccountPaymentMethodLineProvider`` que ya existe (ver
  ``models/account_payment_method_line.py``).
- **``action_post``** — la referencia intercepta el posteo: si hay
  ``payment_token_id`` sin ``payment_transaction_id``, crea la transacción
  primero (``_create_payment_transaction``) y postea condicionalmente según
  su resultado. ``api: account/models/account_payment.py`` no declara
  ``action_post`` en absoluto (el pago no tiene máquina de estados de
  posteo todavía) — no hay método base que envolver.
- **``_create_payment_transaction`` / ``_prepare_payment_transaction_vals``**
  — **bloqueado por diseño, no por pereza**: ``payment.Payment.sale_order``
  es ``NOT NULL PROTECT`` (``api: payment/models/payment.py:61-63``,
  H-API-97). Un ``account.payment`` sin orden de venta asociada —el caso
  típico de pagar una factura ya emitida— no puede crear una fila
  ``Payment``: la construcción exige un ``sale_order`` que no existe en ese
  flujo. Construir un valor sintético violaría la restricción de integridad
  a propósito. Condición de cierre: si ``Payment.sale_order`` se generaliza
  a nulable o a una referencia genérica (decisión de producto sobre
  ``payment``, no de este addon), este método se vuelve portable
  directamente sobre la tabla real en vez de necesitar
  ``AccountPaymentTransaction``.
- **``action_refund_wizard`` / ``action_view_refunds``** — devuelven un
  ``ir.actions.act_window`` (acción de UI del cliente web de Odoo). Sin
  cliente web aquí; los datos que alimentarían un futuro endpoint DRF de
  reembolso ya están expuestos (``refunds_count``, ``amount_available_for_
  refund``, ``_get_payment_refund_wizard_values``) — falta sólo la vista,
  que no es responsabilidad de este addon (``backend-drf``, cuando exista
  el caso de uso).
"""
from decimal import Decimal

from django.db.models import Sum

from addons.account.models.account_payment import AccountPayment
from addons.account_payment.models.links import AccountPaymentTransaction
from addons.payment.models import Refund


def _get_link(payment):
    """El enlace de ``payment``, o ``None`` si nunca se creó uno.

    Un pago sin ``pk`` todavía no está insertado, así que no puede tener
    satélite: se devuelve ``None`` sin consultar. Sin este guard, leer
    ``payment.payment_transaction`` sobre una instancia recién construida
    aborta con ``ValueError: Model instances passed to related filters must
    be saved.`` — mismo defecto de raíz que ``account_payment_method_line
    ._get_link``, donde sí llegó a romper tests de la base.
    """
    if payment.pk is None:
        return None
    return AccountPaymentTransaction.objects.filter(payment=payment).first()


def _get_or_create_link(payment):
    """El enlace de ``payment``, creándolo si hace falta.

    Requiere ``payment.pk`` — ver divergencia 3 del docstring del módulo.
    """
    link, _created = AccountPaymentTransaction.objects.get_or_create(payment=payment)
    return link


# -- payment_transaction (≙ payment_transaction_id) --------------------------

def _get_payment_transaction(self):
    link = _get_link(self)
    return link.transaction if link is not None else None


def _set_payment_transaction(self, value):
    link = _get_or_create_link(self)
    link.transaction = value
    link.save(update_fields=['transaction'])


# -- payment_token (≙ payment_token_id) ---------------------------------------

def _get_payment_token(self):
    link = _get_link(self)
    return link.token if link is not None else None


def _set_payment_token(self, value):
    link = _get_or_create_link(self)
    link.token = value
    link.save(update_fields=['token'])


# -- source_payment (≙ source_payment_id) -------------------------------------

def _get_source_payment(self):
    link = _get_link(self)
    return link.source_payment if link is not None else None


def _set_source_payment(self, value):
    link = _get_or_create_link(self)
    link.source_payment = value
    link.save(update_fields=['source_payment'])


# -- amount_available_for_refund (≙ _compute_amount_available_for_refund) ----

def _get_amount_available_for_refund(self):
    """Monto de la transacción menos sus reembolsos aprobados — ≙
    ``odoo19c: account_payment/models/account_payment.py:49-70``, sin la
    gating por capacidad de reembolso (divergencia 1 del docstring)."""
    link = _get_link(self)
    if link is None or link.transaction_id is None:
        return Decimal('0.00')
    tx = link.transaction
    refunded = Refund.objects.filter(
        payment=tx, status=Refund.STATUS_APPROVED,
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    return tx.amount - refunded


# -- refunds_count (≙ _compute_refunds_count) ---------------------------------

def _get_refunds_count(self):
    """Cuántos ``account.payment`` declaran a éste como origen — ≙
    ``odoo19c: account_payment/models/account_payment.py:93-104``, sin
    filtrar por ``operation == 'refund'`` (divergencia 2)."""
    return AccountPaymentTransaction.objects.filter(source_payment=self).count()


# -- _get_payment_refund_wizard_values (dato, sin acción de UI) --------------

def _get_payment_refund_wizard_values(self):
    """≙ ``odoo19c: account_payment/models/account_payment.py:224-230``.

    Datos crudos para un futuro endpoint de reembolso — el wizard de UI de
    la referencia (``payment.refund.wizard``) no se porta (fuera del
    alcance: ``wizards/``), pero los datos que consumiría sí.
    """
    link = _get_link(self)
    return {
        'transaction_id': link.transaction_id if link is not None else None,
        'payment_amount': self.amount,
        'amount_available_for_refund': _get_amount_available_for_refund(self),
    }


def apply_account_payment_extensions():
    """≙ ``_inherit = 'account.payment'`` de ``account_payment``.

    Se llama desde ``AccountPaymentConfig.ready()``. Idempotente: cada
    propiedad se instala sólo si no existe ya (mismo criterio que
    ``_add_if_absent`` para campos — aquí no hay ``chain_method`` porque
    ninguna de estas propiedades reemplaza comportamiento ajeno, todas son
    aportes nuevos).
    """
    for nombre, getter, setter in (
        ('payment_transaction', _get_payment_transaction, _set_payment_transaction),
        ('payment_token', _get_payment_token, _set_payment_token),
        ('source_payment', _get_source_payment, _set_source_payment),
    ):
        if not hasattr(AccountPayment, nombre):
            setattr(AccountPayment, nombre, property(getter, setter))

    for nombre, getter in (
        ('amount_available_for_refund', _get_amount_available_for_refund),
        ('refunds_count', _get_refunds_count),
    ):
        if not hasattr(AccountPayment, nombre):
            setattr(AccountPayment, nombre, property(getter))

    if not hasattr(AccountPayment, '_get_payment_refund_wizard_values'):
        AccountPayment._get_payment_refund_wizard_values = _get_payment_refund_wizard_values
