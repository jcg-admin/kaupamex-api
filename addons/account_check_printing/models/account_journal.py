"""``account.journal`` — lo que ``account_check_printing`` le cuelga.

Adaptación de ``odoo19c: addons/account_check_printing/models/
account_journal.py`` (``odoo-tools@622ddc2a``, LGPL-3 — atribución y aviso
de licencia preservados, DEC-KX-03).

Símbolos de la referencia — qué pasa aquí (medido, no supuesto)
=====================================================================

=================================  ===========================================
Símbolo de la referencia            Qué pasa aquí
=================================  ===========================================
``_default_outbound_payment_methods``  NO — Divergencia 1
``check_manual_sequencing``         PORTADO — ``CheckPrintingJournalSettings.manual_sequencing``
``check_sequence_id``               PORTADO — ``CheckPrintingJournalSettings.sequence``
``check_next_number`` (compute)     PORTADO — ``next_check_number()``
``_compute_check_next_number``      PORTADO — cuerpo de ``next_check_number()``
``_inverse_check_next_number``      PORTADO — ``set_next_check_number()``
``bank_check_printing_layout``      PORTADO — ``CheckPrintingJournalSettings.layout``
``_get_check_printing_layouts``     PORTADO — ``CheckPrintingCompanySettings.available_layouts``
``create`` (auto-provisión)         PORTADO por OTRO mecanismo — Divergencia 2
``_create_check_sequence``          PORTADO — ``ensure_check_sequence()``
``_get_journal_dashboard_data_batched``  NO — Divergencia 3
``action_checks_to_print``          NO — navegación pura (ver Divergencia 3)
=================================  ===========================================

Divergencia 1 — sin ``outbound_payment_method_line_ids``
============================================================

``AccountJournal`` de este árbol no modela métodos de pago por diario
(``grep -n "payment_method_line" account/models/account_journal.py`` →
**0 hits** [PROVEN]) — es infraestructura de ``account`` (fuera de alcance:
"no tocar ningún otro addon"). ``_default_outbound_payment_methods`` sólo
tiene sentido sobre ese campo ausente. **DESCONOCIDO declarado**: se decide
cuando ``account`` porte la selección de métodos de pago por diario
(sucesor pendiente, fuera de este addon).

La elegibilidad de un diario para Cheques SÍ se responde igual, por
consulta directa sobre ``AccountPaymentMethodLine`` (que sí existe) — ver
``CheckPrintingPaymentInfo.checks_to_print_queryset`` en
``models/account_payment.py`` (no aquí, para evitar un ciclo de imports
entre los dos archivos).

Divergencia 2 — auto-provisión por señal ``post_save``, no por ``create()``
================================================================================

Esta capa ORM expone ``Model.objects.create(...)`` (Django puro) — no hay
un ``create(self, vals_list)`` de instancia que se pueda encadenar como en
Odoo (``@api.model_create_multi``). El punto de enganche equivalente en
este árbol es una señal ``post_save`` — mismo patrón que
``account/models/res_company.py::apply_account_extensions`` usa para
``load_chart_for_new_company``. Se conecta en ``AppConfig.ready()``
(``apps.py``); ``on_journal_saved`` de este archivo es el receptor.

Divergencia 3 — sin tablero de diarios
==========================================

``_get_journal_dashboard_data_batched``/``_fill_dashboard_data_count`` no
existen en este ``AccountJournal`` (``grep -n
"_get_journal_dashboard_data_batched\\|_fill_dashboard_data_count"
account/models/account_journal.py`` → **0 hits** [PROVEN]) — es el sistema
de agregación del tablero contable de ``account``, no de este addon.
**DESCONOCIDO declarado.** Lo mismo aplica a ``action_checks_to_print``
(``ir.actions.act_window`` — navegación pura del cliente web, sin
DRF-view en este pase; mismo criterio que
``account_debit_note``/``action_view_debit_notes``). La CIFRA que ambos
expondrían SÍ es consultable — ver
``CheckPrintingPaymentInfo.checks_to_print_queryset``.
"""
import re

from django.db import models as dj_models

import fields
import models
from addons.account.models import AccountJournal
from addons.account_check_printing.models.res_company import CheckPrintingCompanySettings
from addons.base.models import IrSequence, TimeStampedModel
from exceptions import ValidationError
from tools.translate import _

#: ≙ Odoo ``MAX_INT32`` (``odoo19c: account_journal.py:7``) — límite de
#: ``number_next_actual``/``number_next`` como entero de 32 bits con signo.
MAX_INT32 = 2147483647

#: ≙ ``self.type == 'bank'`` — filtro de
#: ``create_check_sequence_on_bank_journals`` (post_init_hook de la
#: referencia, ``odoo19c: __init__.py:7-8``).
BANK_JOURNAL_TYPE = 'bank'


class CheckPrintingJournalSettings(TimeStampedModel):
    """Ajustes de impresión de cheques de un diario — ≙ los campos
    ``check_*``/``bank_check_printing_layout`` de ``account.journal``."""

    journal = models.OneToOneField(
        AccountJournal, on_delete=models.CASCADE,
        related_name='check_printing_settings',
        help_text='Diario (Odoo _inherit account.journal).',
    )
    manual_sequencing = fields.Boolean(
        default=False, verbose_name='Numeración manual',
        help_text='Marcar si los cheques preimpresos no vienen numerados '
                  '(Odoo check_manual_sequencing).',
    )
    sequence = fields.Many2one(
        IrSequence, on_delete=dj_models.SET_NULL, null=True, blank=True,
        related_name='+',
        help_text='Secuencia de numeración de cheques de este diario (Odoo '
                  'check_sequence_id).',
    )
    layout = fields.Char(
        max_length=64, blank=True, default='',
        verbose_name='Diseño de cheque',
        help_text='Vacío = usa el de la empresa (Odoo '
                  'bank_check_printing_layout).',
    )

    class Meta:
        db_table = 'account_check_printing_journal_settings'
        verbose_name = 'Ajustes de impresión de cheques (diario)'
        verbose_name_plural = 'Ajustes de impresión de cheques (diarios)'

    def __str__(self) -> str:
        return f'Cheques — {self.journal}'

    # -- provisión de la fila / la secuencia --------------------------------

    @classmethod
    def ensure_for(cls, journal):
        """Fila de ajustes de ``journal``, creándola si falta — sin crear la
        secuencia (separado de ``ensure_check_sequence`` a propósito: crear
        la fila no implica siempre crear la secuencia, ver
        ``sync_bank_journal``)."""
        row, _created = cls.objects.get_or_create(journal=journal)
        return row

    @classmethod
    def ensure_check_sequence(cls, journal):
        """Crea la secuencia de cheques del diario si no existe — ≙
        ``_create_check_sequence`` (``odoo19c: account_journal.py:85-94``)."""
        row = cls.ensure_for(journal)
        if row.sequence_id:
            return row
        row.sequence = IrSequence.objects.create(
            name=_('%(journal)s: Check Number Sequence') % {'journal': journal.name},
            implementation='no_gap', padding=5, number_increment=1,
            company=journal.company,
        )
        row.save(update_fields=['sequence', 'updated_at'])
        return row

    @classmethod
    def sync_bank_journal(cls, journal):
        """≙ ``create_check_sequence_on_bank_journals`` (post_init_hook de
        la referencia) aplicado a UN diario — sólo diarios de banco."""
        if journal.type != BANK_JOURNAL_TYPE:
            return None
        return cls.ensure_check_sequence(journal)

    # -- número siguiente (peek + escritura directa) ------------------------

    def next_check_number(self):
        """≙ ``_compute_check_next_number``
        (``odoo19c: account_journal.py:48-55``). Con secuencia: el próximo
        valor SIN consumirlo (``get_next_char``, peek). Sin secuencia:
        ``'1'`` (el default de la referencia)."""
        if not self.sequence_id:
            return '1'
        return self.sequence.get_next_char(self.sequence.number_next)

    def set_next_check_number(self, value):
        """≙ ``_inverse_check_next_number``
        (``odoo19c: account_journal.py:57-77``). Valida el formato, que no
        retroceda respecto al último impreso, y el límite de 32 bits, antes
        de reescribir la secuencia."""
        if value and not re.match(r'^[0-9]+$', value):
            raise ValidationError(_('Next Check Number should only contains numbers.'))
        next_num = int(value)
        row = self if self.sequence_id else self.ensure_check_sequence(self.journal)
        if next_num < row.sequence.number_next:
            raise ValidationError(_(
                'The last check number was %(number)s. In order to avoid a '
                'check being rejected by the bank, you can only use a '
                'greater number.') % {'number': row.sequence.number_next})
        if next_num > MAX_INT32:
            raise ValidationError(_(
                'The check number you entered (%(num)s) exceeds the maximum '
                'allowed value of %(max)d. Please enter a smaller number.'
            ) % {'num': next_num, 'max': MAX_INT32})
        row.sequence.number_next = next_num
        row.sequence.padding = len(value)
        row.sequence.save(update_fields=['number_next', 'padding'])
        if row is not self:
            self.sequence = row.sequence
            self.save(update_fields=['sequence', 'updated_at'])

    # -- diseño --------------------------------------------------------------

    def effective_layout(self):
        """≙ ``bank_check_printing_layout or
        company_id.account_check_printing_layout``
        (``odoo19c: account_payment.py:210``, la mitad que lee el diario)."""
        if self.layout:
            return self.layout
        return CheckPrintingCompanySettings.layout_for(self.journal.company)


def on_journal_saved(sender, instance, created, **kwargs):
    """Receptor de la señal ``post_save`` de ``AccountJournal`` — ≙ la parte
    de ``create()`` de la referencia que da de alta la secuencia de cheques
    en un diario de banco NUEVO (Divergencia 2 del docstring del módulo).

    ``created`` descarta los ``save()`` posteriores (renombrar un diario no
    debe re-disparar la provisión) — mismo guard que
    ``load_chart_for_new_company`` ya usa para ``ResCompany``.
    """
    if not created:
        return
    CheckPrintingJournalSettings.sync_bank_journal(instance)
