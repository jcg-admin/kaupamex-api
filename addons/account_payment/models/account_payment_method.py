"""``account.payment.method`` — lo que ``account_payment`` le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: account_payment/models/account_payment_method.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3, 21
líneas) — atribución y aviso de licencia preservados (DEC-KX-03).

**1 símbolo, portado íntegro.** La referencia extiende ``_get_payment_
method_information`` (``api: account/models/account_payment_method.py:78-88``,
ya declara el caso base ``manual``) recorriendo
``self.env['payment.provider']._fields['code'].selection`` — los CÓDIGOS
POSIBLES de proveedor, no filas existentes — y marcando cada uno (salvo
``none``/``custom``) como ``mode='electronic'``.

Divergencia declarada
=======================

El análogo aquí de "los códigos posibles de proveedor" es
``PaymentGateway.GATEWAYS`` (``api: payment/models/payment_provider.py:
27-34``): ``TEST``/``MERCADOPAGO``/``PAYPAL``. A diferencia de Odoo, **ninguno
de los tres** representa un pseudo-código "sin proveedor"/"manual" —
``PaymentGateway`` no tiene ese concepto (el ``MANUAL`` de ``payment.
Payment.GATEWAYS`` es un enum DISTINTO, de la transacción, no de la
configuración de pasarela) — así que no hay nada análogo a excluir: los
tres se marcan ``electronic``, incluido ``TEST`` (el modo sandbox de una
pasarela real sigue siendo un flujo electrónico, no manual).
"""
from addons.account.models.account_payment_method import AccountPaymentMethod
from addons.payment.models import PaymentGateway
from orm.method_chain import chain_method


def _get_payment_method_information(self):
    """Marca cada gateway configurable como método electrónico — ≙
    ``odoo19c: account_payment/models/account_payment_method.py:10-20``."""
    return {
        gateway.lower(): {'mode': 'electronic', 'type': ('bank',)}
        for gateway, _label in PaymentGateway.GATEWAYS
    }


def _merge_payment_method_information(new, previous):
    """``combine`` de ``chain_method`` — ≙ ``res = super()...; res[code] = ...``:
    las entradas nuevas se suman a (y ganan sobre) las de la cadena previa."""
    return {**(previous or {}), **(new or {})}


def apply_account_payment_extensions():
    """≙ ``_inherit = 'account.payment.method'`` de ``account_payment``.

    Se llama desde ``AccountPaymentConfig.ready()``. ``chain_method`` con
    ``combine`` de fusión de diccionarios: el ``_get_payment_method_
    information`` base (``manual``) y el de aquí (los 3 gateways) se
    fusionan, en vez del relevo por ``None`` que usa el resto del árbol —
    porque este hook nunca devuelve ``None``, siempre un diccionario, así
    que el relevo por defecto nunca delegaría en la cadena previa.
    """
    chain_method(
        AccountPaymentMethod, '_get_payment_method_information',
        _get_payment_method_information,
        combine=_merge_payment_method_information,
    )
