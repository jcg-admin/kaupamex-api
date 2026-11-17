"""``account.journal`` — lo que ``account_payment`` le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: addons/account_payment/models/account_journal.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3, 26
líneas) — atribución y aviso de licencia preservados (DEC-KX-03).

2 símbolos portados. ``_get_available_payment_method_lines`` se encadena
sobre el de ``account`` (``designs/journal-payment-method-lines.md``) y,
como la fuente, filtra lo que la base devuelve. El ``@api.ondelete`` sigue
como receptor ``pre_delete``.

- ``_get_available_payment_method_lines``: envuelve el de la base con
  ``wrap_method`` (``previous`` ≙ ``super()``) y excluye las líneas de
  pasarelas deshabilitadas.
- ``_unlink_except_linked_to_payment_provider``: receptor ``pre_delete``.

Otros addons extienden también ``account.journal``; ``wrap_method`` apila
cada extensión sobre la anterior en vez de pisarla (:ref:`h-api-364`).
"""
from addons.account.models.account_journal import AccountJournal
from addons.account_payment.models.links import PaymentGatewayJournal
from exceptions import UserError
from orm.method_chain import wrap_method
from tools.translate import _
from django.db.models.signals import pre_delete
from django.dispatch import receiver


def _get_available_payment_method_lines(self, previous, payment_type):
    """≙ ``odoo19c: addons/account_payment/models/account_journal.py:
    11-14``: las líneas de la base menos las de una pasarela deshabilitada
    (``payment_provider_state != 'disabled'``)."""
    lines = previous(payment_type)
    return lines.filtered(
        lambda line: line.payment_provider_state != 'disabled')


@receiver(
    pre_delete, sender=AccountJournal,
    dispatch_uid='account_payment.unlink_except_linked_to_payment_provider')
def _unlink_except_linked_to_payment_provider(sender, instance, **kwargs):
    """≙ ``odoo19c: addons/account_payment/models/account_journal.py:16-25``
    (``@api.ondelete(at_uninstall=False)``): no se borra un diario con una
    pasarela activa apuntándole."""
    linked = PaymentGatewayJournal.objects.filter(
        journal=instance, gateway__is_active=True,
    ).select_related('gateway')
    if linked.exists():
        names = ', '.join(link.gateway.name for link in linked)
        raise UserError(_(
            'You must first deactivate a payment provider before deleting '
            'its journal.\nLinked providers: %s') % names)


def apply_account_payment_extensions():
    """≙ ``_inherit = 'account.journal'`` de ``account_payment``.

    Se llama desde ``AccountPaymentConfig.ready()``. El receptor
    ``@receiver`` se conecta al importar este módulo.
    """
    wrap_method(
        AccountJournal, '_get_available_payment_method_lines',
        _get_available_payment_method_lines,
    )
