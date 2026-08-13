"""``account.payment.method`` — lo que ``account_check_printing`` le cuelga.

Adaptación de ``odoo19c: addons/account_check_printing/models/
account_payment_method.py`` (``odoo-tools@622ddc2a``, LGPL-3 — atribución y
aviso de licencia preservados, DEC-KX-03):

.. code-block:: python

    @api.model
    def _get_payment_method_information(self):
        res = super()._get_payment_method_information()
        res['check_printing'] = {'mode': 'multi', 'type': ('bank',)}
        return res

Un método, y YA existe en el modelo ajeno — ``chain_method``, nunca ``hasattr``
====================================================================================

``AccountPaymentMethod._get_payment_method_information`` YA está definido
(``account/models/account_payment_method.py:78-88``, sólo el caso
``manual``). La referencia lo extiende con ``super()`` (agrega
``check_printing`` al diccionario que devuelve). El mecanismo sancionado por
H-API-364 para un método que YA existe es ``chain_method`` con ``combine=``
— nunca ``if not hasattr(...)``, que dejaría este addon mudo si algún día
otro addon (la tanda actual ya tiene otro que extiende
``account.payment.method`` — ver el aviso de "NO ESTÁS SOLO") se instala
antes en ``INSTALLED_APPS``.
"""
from orm.method_chain import chain_method
from addons.account.models import AccountPaymentMethod

#: ≙ ``res['check_printing'] = {'mode': 'multi', 'type': ('bank',)}``
#: (``odoo19c: account_payment_method.py:13``).
CHECK_PRINTING_METHOD_INFO = {'check_printing': {'mode': 'multi', 'type': ('bank',)}}


def _get_payment_method_information(self):
    return dict(CHECK_PRINTING_METHOD_INFO)


def _merge_payment_method_information(new, previous):
    """``combine=`` de ``chain_method`` — funde el diccionario nuevo con el
    de la cadena previa (≙ ``res = super()...(); res['check_printing'] =
    {...}; return res``). El orden de fusión no importa: las claves son
    disjuntas por diseño (cada addon declara SU código de método de pago).
    """
    merged = dict(previous or {})
    merged.update(new or {})
    return merged


def apply_account_check_printing_payment_method_extensions():
    """≙ la mitad de ``_inherit = 'account.payment.method'`` que este addon
    necesita. Se llama desde ``AccountCheckPrintingConfig.ready()``.
    """
    chain_method(
        AccountPaymentMethod, '_get_payment_method_information',
        _get_payment_method_information, combine=_merge_payment_method_information,
    )
