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
     - portado
     - ``write(self, previous, vals)`` instalado con ``extend_model(...,
       overrides=)``: bloquea si quedan documentos pendientes de un formato
       con web-service y borra los pendientes de los demás
       (``odoo19c: :25-41``)
   * - ``_compute_compatible_edi_ids``
     - portado
     - función de módulo ``compute_compatible_edi_ids(journal)``
   * - ``_compute_edi_format_ids``
     - portado (parcial declarado)
     - la SQL cruda de la referencia (``env.cr.execute`` con
       ``ARRAY_AGG``) se sustituye por un ``.values_list()`` agrupado en
       Python — ver su docstring

``write``, donde lo pone la fuente
==================================

La versión anterior interceptaba la desactivación con un receptor
``m2m_changed`` en ``pre_remove``, porque el M2M se escribía con
``journal.edi_format_ids.set(...)``, fuera de ``save()``. Esa premisa caducó:
``AccountJournal`` es ``BaseModel`` y este mismo módulo escribe el M2M con
``write({'edi_format_ids': [Command.set(...)]})``; ninguna parte del árbol
llama al manager. El receptor, además, sólo bloqueaba: los documentos
pendientes de un formato sin web-service sobrevivían, y la fuente los borra
(``:39-41``). Ver ``designs/account-edi-journal-write.md``.

La escritura y su verificación comparten la transacción del llamador, como en
la fuente: el ``UserError`` la deshace allí.
"""

import fields
import models

from addons.account.models.account_journal import AccountJournal
from addons.account_edi.models.account_edi_document import AccountEdiDocument
from addons.account_edi.models.account_edi_format import AccountEdiFormat
from exceptions import UserError
from orm.model_classes import extend_model
from tools.translate import _


def compute_compatible_edi_ids(journal):
    """≙ ``_compute_compatible_edi_ids`` (``odoo19c: account_edi/models/
    account_journal.py:47-52``).

    Sin ``@api.depends`` reactivo en este ORM (se computa bajo demanda, no
    en cada acceso ni en cada escritura de ``type``/``company``) — mismo
    criterio que el resto de propiedades DEC-SALE-01 de este árbol.
    """
    return [
        edi_format
        for edi_format in AccountEdiFormat.objects.all()
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
        edi_format
        for edi_format in AccountEdiFormat.objects.all()
        if edi_format._is_compatible_with_journal(journal)
        and (
            edi_format._is_enabled_by_default_on_journal(journal)
            or edi_format.id in journal.edi_format_ids.ids
        )
    ]

    protected_ids = set(
        AccountEdiDocument.objects.filter(
            move_id__journal=journal,
            state__in=('to_cancel', 'to_send'),
        ).values_list('edi_format_id', flat=True)
    )
    protected = journal.edi_format_ids.filtered(
        lambda edi_format: edi_format.id in protected_ids)

    ids = {f.pk for f in enabled} | set(protected.ids)
    journal.write({'edi_format_ids': [fields.Command.set(sorted(ids))]})


def write(self, previous, vals):
    """≙ ``write`` (``odoo19c: account_edi/models/account_journal.py:25-41``).

    ``previous`` es el ``write`` de ``account`` (``super().write(vals)`` de la
    fuente). Si ``vals`` no toca ``edi_format_ids`` sólo delega.
    """
    if not vals.get('edi_format_ids'):
        return previous(vals)
    old_edi_format_ids = self.edi_format_ids
    res = previous(vals)
    diff_edi_format_ids = old_edi_format_ids - self.edi_format_ids
    documents = self.env['account.edi.document'].search([
        ('move_id.journal_id', 'in', self.ids),
        ('edi_format_id', 'in', diff_edi_format_ids.ids),
        ('state', 'in', ('to_cancel', 'to_send')),
    ])
    if documents.filtered(lambda d: d.edi_format_id._needs_web_services()):
        raise UserError(
            _(
                'Cannot deactivate (%s) on this journal because not all '
                'documents are synchronized'
            )
            % ', '.join(documents.edi_format_id.mapped('display_name'))
        )
    if documents:
        documents.unlink()
    return res


def apply_account_edi_extensions():
    """≙ ``_inherit = 'account.journal'`` de ``account_edi``.

    ``compatible_edi_ids`` se cuelga como propiedad no-almacenada
    (DEC-SALE-01); ``write`` extiende el de ``account`` por ``overrides=``.
    """
    extend_model('account.journal', overrides={'write': write})
    if not hasattr(AccountJournal, 'compatible_edi_ids'):
        setattr(
            AccountJournal,
            'compatible_edi_ids',
            property(compute_compatible_edi_ids),
        )
