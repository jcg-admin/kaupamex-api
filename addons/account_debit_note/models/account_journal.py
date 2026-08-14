"""``account.journal`` — lo que ``account_debit_note`` le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: addons/account_debit_note/models/account_journal.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3 — atribución
y aviso de licencia preservados, DEC-KX-03).

Un campo, un método — ambos se portan
=======================================

La referencia reabre ``account.journal`` (ya en ``account.AccountJournal``,
sin declarar este campo) y agrega::

    debit_sequence = fields.Boolean(
        compute="_compute_debit_sequence", readonly=False, store=True, ...)

    @api.depends("type")
    def _compute_debit_sequence(self):
        for journal in self:
            journal.debit_sequence = journal.type in ("sale", "purchase")

Cross-app ``_inherit`` → RELATED OneToOne (DEC-SALE-01, mismo criterio que
``account_add_gln.PartnerGln``): Django no inyecta una columna en la tabla de
OTRO addon sin migrar la app dueña (``account.journal`` vive en ``account``
en este árbol), así que ``JournalDebitSequence`` cuelga de
``account.AccountJournal`` con su propia tabla — sin tocar ``account`` ni su
migración.

Divergencia declarada — recompute explícito, no automático
=============================================================

La referencia es ``compute=..., store=True, readonly=False``: Odoo
**recomputa** el valor cada vez que ``type`` cambia (``@api.depends``),
incluso si el usuario ya lo había editado a mano. Aquí el equivalente es
``JournalDebitSequence.sync_from_type()``, invocado explícitamente por el
llamador — mismo criterio que ``fleet.FleetVehicle`` ya fija para la misma
familia de campo ("compute, store=True, readonly=False" → método explícito,
NO disparado en ``save()``, "para no pisar en silencio un valor que el
usuario ya editó"; ver el docstring de ``fleet/models/fleet_vehicle.py``,
divergencia 2). No hay ``AccountJournal.save()`` que interceptar sin tocar
``account`` de todos modos — sería el mismo problema que
``models/account_move_sequence.py`` resuelve para ``AccountMove``, pero para
un campo sin lectores adicionales no lo justifica: **DESCONOCIDO declarado**,
se decide si algún día un flujo de creación de diarios necesita el
recompute automático.

``wants_debit_sequence()`` es el lector que sí importa: da el valor
**efectivo** del flag exista o no la fila override — es lo que
``models/account_move_sequence.py`` consulta para decidir la numeración.
"""
from addons.base.models import TimeStampedModel
import fields
import models


class JournalDebitSequence(TimeStampedModel):
    """Flag "secuencia dedicada de nota de débito" de un ``account.journal``.

    ≙ ``account.journal.debit_sequence``. Si está activo, las notas de
    débito de este diario numeran en una serie separada de la de facturas
    (ver ``models/account_move_sequence.py``).
    """

    #: Tipos de diario cuyo default es ``True`` — ≙ el cuerpo de
    #: ``_compute_debit_sequence`` (``odoo19c: account_journal.py:15``).
    DEFAULT_TYPES = ('sale', 'purchase')

    journal = models.OneToOneField(
        'account.AccountJournal', on_delete=models.CASCADE,
        related_name='debit_sequence_setting',
        help_text='Diario al que pertenece (Odoo _inherit account.journal).',
    )
    debit_sequence = fields.Boolean(
        default=False,
        verbose_name='Secuencia dedicada de nota de débito',
        help_text='No compartir la secuencia de facturas y notas de débito '
                  'de este diario (Odoo debit_sequence).',
    )

    class Meta:
        db_table = 'account_debit_note_journal_debit_sequence'
        verbose_name = 'Secuencia de nota de débito del diario'
        verbose_name_plural = 'Secuencias de nota de débito de diarios'

    def __str__(self) -> str:
        label = 'con' if self.debit_sequence else 'sin'
        return f'{self.journal} — {label} secuencia dedicada de nota de débito'

    @classmethod
    def default_for_type(cls, journal_type) -> bool:
        """El default por tipo de diario — ≙ el cuerpo de
        ``_compute_debit_sequence``."""
        return journal_type in cls.DEFAULT_TYPES

    @classmethod
    def wants_debit_sequence(cls, journal) -> bool:
        """Valor efectivo del flag para ``journal``, exista o no la fila.

        Antes de que exista un override guardado (diario creado antes de
        instalar este addon, o nunca sincronizado), el valor efectivo es el
        default por tipo — el mismo que Odoo calcularía en el primer
        recompute. Con fila, manda el valor guardado (la mitad editable del
        campo compute+store de la referencia).
        """
        if journal is None:
            return False
        row = cls.objects.filter(journal=journal).first()
        if row is None:
            return cls.default_for_type(journal.type)
        return row.debit_sequence

    @classmethod
    def sync_from_type(cls, journal):
        """Crea o recalcula el override desde ``journal.type`` — invocación
        explícita (ver la divergencia declarada arriba). Devuelve la fila."""
        row, created = cls.objects.get_or_create(
            journal=journal,
            defaults={'debit_sequence': cls.default_for_type(journal.type)},
        )
        if not created:
            row.debit_sequence = cls.default_for_type(journal.type)
            row.save(update_fields=['debit_sequence', 'updated_at'])
        return row
