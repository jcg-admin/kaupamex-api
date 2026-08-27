r"""``account.resequence.wizard`` — lo que ``account_edi`` le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: account_edi/wizard/account_resequence.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3, 23 líneas)
— atribución y aviso de licencia preservados (DEC-KX-03).

Dos símbolos, los 2 portados
================================

.. list-table::
   :header-rows: 1
   :widths: 35 15 50

   * - Símbolo
     - Estado
     - Nota
   * - ``_frozen_edi_documents``
     - portado
     - nuevo — sin colisión
   * - ``resequence`` (override)
     - portado
     - guard: si hay documentos EDI ya enviados, se rehúsa ANTES de llamar
       a la implementación base — ``chain_method`` con relevo por ``None``
       (mi función retorna ``None`` cuando no hay bloqueo, y la cadena
       llama a la implementación previa)

``AccountResequenceWizard`` es una clase Python de ``classmethod``s (ver el
docstring de ``account/wizard/account_resequence.py``), no un modelo Django
— ``resequence(cls, moves, first_name, ordering='keep')`` recibe el iterable
de asientos como parámetro explícito (``self.move_ids`` de la referencia →
``moves``).
"""
from addons.account.wizard.account_resequence import AccountResequenceWizard
from addons.account_edi.models.account_edi_document import AccountEdiDocument
from exceptions import UserError
from orm.method_chain import chain_method
from tools.translate import _


def _frozen_edi_documents(moves):
    """≙ ``_frozen_edi_documents`` (``odoo19c: :7-14``).

    Documentos EDI que no pueden cambiar: sus asientos no admiten
    renumeración. Función de módulo (recibe ``moves`` explícito, mismo
    criterio del resto de este puerto — ``self.move_ids`` de la referencia
    ya llega como parámetro en ``resequence``).
    """
    docs = AccountEdiDocument.objects.filter(
        move__in=list(moves), state='sent',
    ).select_related('edi_format', 'move')
    return [d for d in docs if d.edi_format._needs_web_services()]


def _resequence_edi_guard(cls, moves, first_name, ordering='keep'):
    """≙ ``resequence`` (``odoo19c: :16-22``).

    Retorna ``None`` cuando no hay bloqueo — ``chain_method`` (relevo por
    ``None``) llama entonces a la implementación base, que hace el trabajo
    real (``account/wizard/account_resequence.py::resequence``).
    """
    moves = list(moves)
    frozen = _frozen_edi_documents(moves)
    if frozen:
        names = sorted({d.move.name for d in frozen})
        raise UserError(_(
            'The following documents have already been sent and cannot be '
            'resequenced: %s') % ', '.join(names))
    return None


def apply_account_edi_extensions():
    """≙ ``_inherit = 'account.resequence.wizard'`` de ``account_edi``."""
    chain_method(AccountResequenceWizard, 'resequence', _resequence_edi_guard)
