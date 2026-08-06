"""``account.journal.group`` — Adaptación de Odoo addons/account/models/account_journal.py
(clase ``AccountJournalGroup``, odoo-tools@622ddc2a, odoo19c:).

Agrupador de diarios (ledger group) para filtros multi-diario en reportes.
Campos núcleo: ``name``, ``company`` (opcional: sin company, visible para
todas), ``excluded_journals`` (M2M — diarios excluidos del grupo),
``sequence``. Único ``(company, name)`` fiel a la referencia
(``_uniq_name``).
"""
import fields
import models


class AccountJournalGroup(models.Model):
    """``account.journal.group`` — agrupador de diarios para reportes."""

    name = fields.Char(
        max_length=255,
        help_text='Nombre del grupo de diarios (Odoo name, requerido, '
                  'traducible).',
    )
    company = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, null=True, blank=True,
        related_name='journal_groups',
        help_text='Empresa que puede seleccionar el grupo en filtros de '
                  'reportes; sin empresa, disponible para todas (Odoo '
                  'company_id).',
    )
    excluded_journals = fields.Many2many(
        'account.AccountJournal', blank=True,
        related_name='excluded_from_groups',
        help_text='Diarios excluidos del grupo (Odoo excluded_journal_ids).',
    )
    sequence = fields.Integer(
        default=10, help_text='Orden de presentación (Odoo sequence).',
    )

    class Meta:
        db_table = 'account_journal_group'
        ordering = ['sequence', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'name'], name='unique_journal_group_name_company',
            ),
        ]
        verbose_name = 'Grupo de diarios'
        verbose_name_plural = 'Grupos de diarios'

    def __str__(self) -> str:
        return self.name
