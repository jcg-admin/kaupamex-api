"""``account.journal`` extendido por ``account_peppol`` — el diario Peppol.

Adaptación de Odoo ``account_peppol/models/account_journal.py``
(``odoo19c: addons/account_peppol/models/account_journal.py``, 67 líneas,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué es: marcar **un** diario de compras como el que recibe las facturas que
llegan por Peppol, y colgar del tablero del diario los dos botones de
sincronización.

Medido por AST en la fuente: 1 clase (``_inherit``), **2 campos** y
**5 métodos**.

Porte símbolo por símbolo — 7 símbolos: 3 portados, 4 bloqueados
==================================================================

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Símbolo (línea)
     - Desenlace
   * - ``is_peppol_journal`` (``:9``)
     - **portado** verbatim — ``Boolean``, ``default=False``. Es el campo que
       ``ResCompany._inverse_peppol_purchase_journal_id`` mantiene único por
       empresa.
   * - ``_check_type_for_peppol_journal`` (``:11-17``)
     - **portado** como validación de ``clean()`` (divergencia 2), con su
       texto de error.
   * - ``account_peppol_proxy_state`` (``:8``)
     - **portado** como ``property`` — es un ``related='company_id.
       account_peppol_proxy_state'``, y este árbol expresa los ``related`` de
       sólo lectura como propiedad en vez de duplicar la columna.
   * - ``_compute_show_refresh_out_einvoices_status_button`` (``:19-34``) /
       ``_compute_show_fetch_in_einvoices_button`` (``:36-46``)
     - BLOQUEADOS por ``account`` — los dos campos que calculan
       (``show_refresh_out_einvoices_status_button``,
       ``show_fetch_in_einvoices_button``) los declara
       ``odoo19c: account/models/account_journal.py`` y **no están en este
       árbol** (medido: 0 hits de ambos). Bloqueador de segundo orden:
       ``is_self_billing``, también de ``account`` (0 hits).
   * - ``button_fetch_in_einvoices`` (``:48-56``) /
       ``button_refresh_out_einvoices_status`` (``:58-67``)
     - BLOQUEADOS por los métodos base homónimos de ``account`` (0 hits: la
       fuente los extiende con ``super()``) y, en cadena, por
       ``_peppol_get_new_documents`` / ``_peppol_get_message_status``, que
       están bloqueados por ``account_edi_ubl_cii`` (ver
       ``models/account_edi_proxy_user.py``). La **selección** de usuarios de
       proxy que ambos hacen sí está portada, en los crons homónimos de ese
       archivo — es lo mismo que estos botones disparan a mano.

Divergencias declaradas
=========================

1. **``related=`` de sólo lectura → ``property``.** Duplicar la columna
   obligaría a sincronizarla; la propiedad la lee de la empresa, que es la
   dueña del dato.
2. **``@api.constrains('type')`` → ``clean()``**, donde este árbol pone las
   restricciones de modelo.
"""
import fields
from addons.account.models.account_journal import AccountJournal
from exceptions import ValidationError
from orm.method_chain import chain_method
from orm.model_classes import add_field_if_absent
from tools.translate import _


def _campos():
    """El campo que este addon cuelga sobre ``account.AccountJournal``."""
    return {
        'is_peppol_journal': fields.Boolean(
            default=False,
            verbose_name='Diario usado para Peppol',
            help_text='Marca el diario donde aterrizan las facturas recibidas por '
                      'Peppol (Odoo is_peppol_journal).',
        ),
    }


def account_peppol_proxy_state(self):
    """≙ ``account_peppol_proxy_state`` (``odoo19c: :8``), que es un
    ``related='company_id.account_peppol_proxy_state'`` — aquí, propiedad de
    lectura (divergencia 1)."""
    return self.company.account_peppol_proxy_state if self.company_id else None


def _check_type_for_peppol_journal(self, *args, **kwargs):
    """≙ ``_check_type_for_peppol_journal`` (``odoo19c: :11-17``).

    Un diario marcado para Peppol tiene que ser de compras: es donde aterriza
    lo que se recibe. Retorna ``None`` para que ``chain_method`` siga con la
    validación previa.
    """
    if self.is_peppol_journal and self.type != 'purchase':
        raise ValidationError({'type': _(
            'No se puede cambiar el tipo de un diario usado para recibir '
            'facturas por Peppol a uno distinto de «Compras».\n'
            'Cambie antes el diario de recepción Peppol.',
        )})
    return None


def apply_account_peppol_account_journal_extensions():
    """Cuelga sobre ``account.AccountJournal`` la marca de diario Peppol — ≙
    ``_inherit = 'account.journal'``. La llama ``AccountPeppolConfig.ready()``."""
    for name, field in _campos().items():
        add_field_if_absent(AccountJournal, name, field)

    if not hasattr(AccountJournal, 'account_peppol_proxy_state'):
        AccountJournal.account_peppol_proxy_state = property(account_peppol_proxy_state)

    chain_method(AccountJournal, 'clean', _check_type_for_peppol_journal)


__all__ = ['apply_account_peppol_account_journal_extensions']
