r"""``account.journal`` — lo que ``account_edi`` le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: account_edi/models/account_journal.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3, 83 líneas)
— atribución y aviso de licencia preservados (DEC-KX-03).

Cinco símbolos de la referencia — los 5 con contraparte real
==================================================================

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Símbolo
     - Estado
     - Nota
   * - ``edi_format_ids`` (campo)
     - portado
     - declarado en ``account_edi_format.py`` de este addon (M2M inverso,
       ver su docstring) — **no** aquí; ``account/models/account_journal.py``
       está fuera del write-set de este agente
   * - ``compatible_edi_ids`` (campo)
     - portado
     - propiedad no-almacenada (``compute`` sin ``store=True`` en la
       referencia — DEC-SALE-01, mismo criterio que ``account_payment``)
   * - ``write`` (override)
     - portado (mecanismo distinto)
     - la referencia intercepta ``vals.get('edi_format_ids')`` dentro de
       ``write()``; aquí el M2M se escribe fuera de ``save()``
       (``journal.edi_format_ids.set(...)``/``.remove(...)``), así que el
       punto de intercepción real es la señal ``m2m_changed`` sobre el
       ``through`` del M2M — ver ``_guard_edi_format_removal`` abajo
   * - ``_compute_compatible_edi_ids``
     - portado
     - función de módulo ``compute_compatible_edi_ids(journal)``
   * - ``_compute_edi_format_ids``
     - portado (parcial declarado)
     - la SQL cruda de la referencia (``env.cr.execute`` con
       ``ARRAY_AGG``) se sustituye por un ``.values_list()`` agrupado en
       Python — ver su docstring

``write`` → ``m2m_changed``, no ``save()``
================================================

Django escribe un M2M **fuera** del ciclo ``save()``: ``journal.
edi_format_ids.set([...])`` opera directo sobre la tabla ``through``, sin
pasar por ``AccountJournal.save()``. Colgar un guard en ``save()`` (como
``chain_method`` haría con cualquier otro método) no vería nunca ese cambio.
El punto de intercepción correcto — y el único que Django ofrece para esto —
es la señal ``django.db.models.signals.m2m_changed`` sobre
``AccountEdiFormat.journals.through``, en ``action='pre_remove'``: dispara
**antes** de que la fila del ``through`` se borre, exactamente cuando la
referencia comprueba antes de dejar completar el ``write()``. Mismo patrón
que ``account_payment/models/account_journal.py::_unlink_except_linked_to_
payment_provider`` ya usa para ``pre_delete`` — aquí el evento es de M2M, no
de fila, pero la forma (``@receiver`` + ``raise`` bloquea) es idéntica.

**Divergencia declarada**: la señal cablea sobre CUALQUIER escritura del M2M
—no distingue "el usuario intentó desactivar por la UI" de "un script
administrativo reasigna todo"—, que es exactamente lo que el ``write()`` de
la referencia tampoco distingue (intercepta el diccionario completo de
``vals``, no una intención). Mismo alcance, mecanismo distinto.
"""
import fields
import models
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from addons.account.models.account_journal import AccountJournal
from addons.account_edi.models.account_edi_document import AccountEdiDocument
from addons.account_edi.models.account_edi_format import AccountEdiFormat
from exceptions import UserError
from tools.translate import _


def compute_compatible_edi_ids(journal):
    """≙ ``_compute_compatible_edi_ids`` (``odoo19c: account_edi/models/
    account_journal.py:47-52``).

    Sin ``@api.depends`` reactivo en este ORM (se computa bajo demanda, no
    en cada acceso ni en cada escritura de ``type``/``company``) — mismo
    criterio que el resto de propiedades DEC-SALE-01 de este árbol.
    """
    return [
        edi_format for edi_format in AccountEdiFormat.objects.all()
        if edi_format._is_compatible_with_journal(journal)
    ]


def compute_edi_format_ids(journal):
    """≙ ``_compute_edi_format_ids`` (``odoo19c: :54-79``), parcial declarado.

    La referencia hace UNA consulta SQL cruda con ``ARRAY_AGG`` para los
    ``edi_format_id`` "protegidos" (documentos ``to_send``/``to_cancel`` de
    **todos** los diarios pasados) y luego itera. Aquí se protege sólo este
    ``journal`` (la función recibe una fila, no un recordset — mismo criterio
    que el resto de este puerto, ``self`` de Odoo → parámetro explícito), así
    que la consulta cruda no aporta sobre agregar por lote: un
    ``.values_list('edi_format_id', flat=True)`` filtrado por este diario
    hace el mismo trabajo con el ORM normal.
    """
    enabled = [
        edi_format for edi_format in AccountEdiFormat.objects.all()
        if edi_format._is_compatible_with_journal(journal)
        and (edi_format._is_enabled_by_default_on_journal(journal)
             or journal.edi_format_ids.filter(pk=edi_format.pk).exists())
    ]

    protected_ids = set(
        AccountEdiDocument.objects.filter(
            move_id__journal=journal, state__in=('to_cancel', 'to_send'),
        ).values_list('edi_format_id', flat=True)
    )
    protected = journal.edi_format_ids.filter(pk__in=protected_ids)

    ids = {f.pk for f in enabled} | set(protected.values_list('pk', flat=True))
    journal.edi_format_ids.set(ids)


@receiver(m2m_changed, sender=AccountEdiFormat.journals.through,
          dispatch_uid='account_edi.guard_edi_format_removal')
def _guard_edi_format_removal(sender, instance, action, reverse, pk_set, **kwargs):
    """≙ ``write`` (``odoo19c: account_edi/models/account_journal.py:25-41``).

    No se borra un ``account.edi.format`` de ``journal.edi_format_ids`` si
    quedan documentos ``to_send``/``to_cancel`` de un formato que necesita
    web-service — sin importar de qué lado se disparó el cambio
    (``journal.edi_format_ids.remove(f)`` o ``edi_format.journals.remove(j)``,
    mismo ``through``, mismo receptor, ``reverse`` distingue el lado).
    """
    if action != 'pre_remove':
        return

    if reverse:
        # instance = AccountEdiFormat; pk_set = ids de AccountJournal.
        journal_ids = pk_set
        edi_format_ids = [instance.pk]
    else:
        # instance = AccountJournal; pk_set = ids de AccountEdiFormat.
        journal_ids = [instance.pk]
        edi_format_ids = pk_set

    documents = AccountEdiDocument.objects.filter(
        move_id__journal_id__in=journal_ids,
        edi_format_id__in=edi_format_ids,
        state__in=('to_cancel', 'to_send'),
    ).select_related('edi_format_id')
    blocking = [d for d in documents if d.edi_format_id._needs_web_services()]
    if blocking:
        names = ', '.join(sorted({d.edi_format_id.name or d.edi_format_id.code for d in blocking}))
        raise UserError(_(
            'Cannot deactivate (%s) on this journal because not all '
            'documents are synchronized') % names)


def apply_account_edi_extensions():
    """≙ ``_inherit = 'account.journal'`` de ``account_edi``.

    ``compatible_edi_ids`` se cuelga como propiedad no-almacenada
    (DEC-SALE-01); el guard de ``write`` se conecta al importar este módulo
    (``@receiver``), no aquí — igual que ``account_payment/models/
    account_journal.py``.
    """
    if not hasattr(AccountJournal, 'compatible_edi_ids'):
        setattr(AccountJournal, 'compatible_edi_ids',
                property(compute_compatible_edi_ids))
