"""``account.journal`` — lo que ``account_payment`` le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: account_payment/models/account_journal.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3, 26
líneas) — atribución y aviso de licencia preservados (DEC-KX-03).

2 símbolos, los 2 portados — pero **reconstruidos**, no encadenados:
``api: account/models/account_journal.py`` no declara ningún método propio
más allá de ``__str__`` (medido), así que no hay un ``_get_available_
payment_method_lines`` base que envolver ni un ``@api.ondelete`` que
extender. ``chain_method`` sobre un método ausente simplemente instala la
función tal cual (rama ``previous is None`` de ``orm/method_chain.py``) —
se usa igual, por consistencia con el resto del árbol, aunque aquí no haya
cadena que preservar.

===================================  ==================================================
Símbolo de la referencia              Aquí
===================================  ==================================================
``_get_available_payment_method_lines``  método homónimo — filtra por ``payment_type``
                                       y excluye líneas de pasarelas inactivas (≙
                                       ``payment_provider_state != 'disabled'``)
``_unlink_except_linked_to_payment_provider``  receptor ``pre_delete``
===================================  ==================================================

**No estás solo en este modelo** (nota del orquestador): otro addon de la
misma tanda también extiende ``account.journal``. Por eso ambos métodos
usan ``chain_method`` en vez de ``setattr``+``hasattr`` — aunque hoy no haya
cadena previa, si el otro addon instala primero, esta extensión se ENCADENA
en vez de pisarlo (:ref:`h-api-364`).
"""
from addons.account.models.account_journal import AccountJournal
from addons.account_payment.models.links import PaymentGatewayJournal
from exceptions import UserError
from orm.method_chain import chain_method
from tools.translate import _
from django.db.models.signals import pre_delete
from django.dispatch import receiver


def _get_available_payment_method_lines(self, payment_type):
    """Líneas de método de pago del diario, excluyendo las de pasarelas
    inactivas — ≙ ``odoo19c: account_payment/models/account_journal.py:
    11-14``, sin ``super()`` porque no hay base (ver docstring del módulo)."""
    lines = self.payment_method_lines.filter(payment_method__payment_type=payment_type)
    inactive_provider_ids = PaymentGatewayJournal.objects.filter(
        journal=self, gateway__is_active=False,
    ).values_list('gateway_id', flat=True)
    if not inactive_provider_ids:
        return lines
    return lines.exclude(provider_link__provider_id__in=list(inactive_provider_ids))


@receiver(pre_delete, sender=AccountJournal,
          dispatch_uid='account_payment.unlink_except_linked_to_payment_provider')
def _unlink_except_linked_to_payment_provider(sender, instance, **kwargs):
    """≙ ``odoo19c: account_payment/models/account_journal.py:16-25``
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
    chain_method(
        AccountJournal, '_get_available_payment_method_lines',
        _get_available_payment_method_lines,
    )
