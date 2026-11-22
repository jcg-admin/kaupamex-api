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
     - ``Many2many`` calculado y almacenado sobre el diario, colgado con
       ``extend_model(campos=)`` y la tabla ``through`` de siempre
       (``odoo19c: :11-16``)
   * - ``compatible_edi_ids`` (campo)
     - portado
     - ``Many2many`` calculado sin almacenar (``odoo19c: :18-20``)
   * - ``write`` (override)
     - portado
     - ``write(self, previous, vals)`` instalado con ``extend_model(...,
       overrides=)``: bloquea si quedan documentos pendientes de un formato
       con web-service y borra los pendientes de los demás
       (``odoo19c: :25-41``)
   * - ``_compute_compatible_edi_ids``
     - portado
     - método del recordset (``odoo19c: :46-52``)
   * - ``_compute_edi_format_ids``
     - portado
     - método del recordset, con la consulta agregada por lote de la fuente
       (``odoo19c: :54-79``)

Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
account-edi-journal-computes.md``.

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

from collections import defaultdict

import api
import fields

from exceptions import UserError
from orm.model_classes import extend_model
from tools.sql import SQL
from tools.translate import _


@api.depends('type', 'company', 'company.account_fiscal_country')
def _compute_compatible_edi_ids(self):
    """≙ ``_compute_compatible_edi_ids``.

    ``odoo19c: addons/account_edi/models/account_journal.py:46-52``
    """
    edi_formats = self.env['account.edi.format'].search([])
    for journal in self:
        journal.compatible_edi_ids = edi_formats.filtered(
            lambda e: e._is_compatible_with_journal(journal))


@api.depends('type', 'company', 'company.account_fiscal_country')
def _compute_edi_format_ids(self):
    """≙ ``_compute_edi_format_ids``
    (``odoo19c: addons/account_edi/models/account_journal.py:54-79``).

    La consulta agregada de la fuente corre por ``env.execute_query``; su
    ``IN %s`` con tupla es ``= ANY(%s)`` con lista porque psycopg 3 no
    expande la tupla.
    """
    edi_formats = self.env['account.edi.format'].search([])
    journal_ids = self.ids
    if journal_ids:
        protected_edi_formats_per_journal = {
            row[0]: set(row[1]) for row in self.env.execute_query(SQL("""
                SELECT
                    move.journal_id,
                    ARRAY_AGG(doc.edi_format_id) AS edi_format_ids
                FROM account_edi_document doc
                JOIN account_move move ON move.id = doc.move_id
                WHERE doc.state IN ('to_cancel', 'to_send')
                AND move.journal_id = ANY(%s)
                GROUP BY move.journal_id
            """, list(journal_ids)))}
    else:
        protected_edi_formats_per_journal = defaultdict(set)

    for journal in self:
        enabled_edi_formats = edi_formats.filtered(
            lambda e: e._is_compatible_with_journal(journal)
            and (e._is_enabled_by_default_on_journal(journal)
                 or e in journal.edi_format_ids))
        # Los formatos ya en uso no se pueden quitar.
        protected_edi_format_ids = protected_edi_formats_per_journal.get(
            journal.id, set())
        protected_edi_formats = journal.edi_format_ids.filtered(
            lambda e: e.id in protected_edi_format_ids)
        journal.edi_format_ids = enabled_edi_formats + protected_edi_formats


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

    Los dos campos se declaran sobre el diario con sus cómputos, y ``write``
    extiende el de ``account`` por ``overrides=``.
    """
    extend_model(
        'account.journal',
        campos={
            'edi_format_ids': fields.Many2many(
                'account_edi.AccountEdiFormat',
                blank=True,
                related_name='+',
                db_table='account_edi_format_journals',
                compute='_compute_edi_format_ids', store=True,
                readonly=False,
                string='Electronic invoicing',
                help_text='Send XML/EDI invoices',
            ),
            'compatible_edi_ids': fields.Many2many(
                'account_edi.AccountEdiFormat',
                related_name='+',
                compute='_compute_compatible_edi_ids',
                help_text='EDI format that support moves in this journal',
            ),
        },
        metodos={
            '_compute_compatible_edi_ids': _compute_compatible_edi_ids,
            '_compute_edi_format_ids': _compute_edi_format_ids,
        },
        overrides={'write': write},
    )
