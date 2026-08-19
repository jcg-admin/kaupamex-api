"""``account.resequence.wizard`` — renumerar asientos de un diario.

Adaptación de Odoo ``addons/account/wizard/account_resequence.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3 —
atribución y aviso de licencia preservados, DEC-KX-03).

``TransientModel`` → clase con classmethods, no tabla — mismo patrón que
``AccountDebitNoteWizard``. La maquinaria de secuencias que este wizard
consume ya está portada en ``models/sequence_mixin.py``; los nombres de allá
perdieron el guion bajo en un pase anterior a la regla H-API-581 (deuda
congelada del baseline), así que la correspondencia es:

- ``_deduce_sequence_number_reset`` → ``deduce_sequence_number_reset``
- ``_get_sequence_format_param``    → ``get_sequence_format_param``
- ``_get_sequence_date_range``      → ``get_sequence_date_range``

Catorce símbolos de la referencia (8 campos + 6 defs) — el desglose
====================================================================

================================  =========================================
Símbolo de la referencia           Qué pasa aquí
================================  =========================================
``sequence_number_reset``          PORTADO — ``_compute_sequence_number_reset``
``first_date`` (campo)             NO — la vista lo declara pero **ningún
                                    método de la referencia lo lee** (sólo
                                    su ``help``); sin lector, no hay qué
                                    portar.
``end_date`` (campo)               NO — ídem.
``first_name`` (campo)             PORTADO — ``_compute_first_name`` +
                                    parámetro ``first_name``
``ordering`` (campo)               PORTADO — parámetro ``ordering``
``move_ids`` (campo)               PORTADO — parámetro ``moves``
``new_values`` (campo)             PORTADO — retorno de
                                    ``_compute_new_values``
``preview_moves`` (campo)          PORTADO — retorno de
                                    ``_compute_preview_moves``
``default_get``                    PORTADO (parcial declarado, ver su
                                    docstring)
``_compute_sequence_number_reset`` PORTADO
``_compute_first_name``            PORTADO
``_compute_preview_moves``         PORTADO
``_compute_new_values``            PORTADO (parcial declarado)
``resequence``                     PORTADO (parcial declarado)
================================  =========================================

Divergencias declaradas
========================

- ``default_get``: las dos validaciones sobre ``refund_sequence`` /
  ``payment_sequence`` del diario están **bloqueadas por esos dos campos**
  (``odoo19c: account_journal.py``, no portados en ``account_journal.py`` —
  el diario del puerto no segmenta la serie por refund/payment todavía).
  Se porta la validación con contraparte real: un solo diario.
- ``_compute_new_values``: el ``_get_move_key`` de la referencia usa
  ``get_fiscal_year(move.date, company.fiscalyear_last_day/month)`` —
  bloqueado por los dos campos de cierre fiscal de ``res.company`` (no
  portados; ver ``models/res_company.py``, que porta los candados pero no
  el cierre). El año fiscal se toma como año calendario — coincide con la
  referencia cuando el cierre es 31/12, el default de allá. Por lo mismo,
  ``get_sequence_date_range`` local devuelve 2-tupla (sin
  ``forced_year_start/end``). ``format_date(self.env, …)`` (formato por
  locale) → ``isoformat()``.
- ``resequence``: el guard ``restrict_mode_hash_table`` está bloqueado por
  el mecanismo de hash inalterable (no portado). El doble pase de la
  referencia (vaciar ``name`` + ``flush_recordset``, luego asignar) se
  conserva: evita el choque transitorio de nombres.
"""
import json
from collections import defaultdict

from exceptions import UserError
from orm.models_transient import TransientModel
from tools.translate import _


class AccountResequenceWizard(TransientModel):
    """≙ ``account.resequence.wizard`` — propone y aplica nombres nuevos a
    los asientos de un diario, conservando el formato de la serie."""

    _name = 'account.resequence.wizard'
    _description = 'Remake the sequence of Journal Entries.'

    class Meta:
        abstract = True
        managed = False

    @classmethod
    def default_get(cls, moves):
        """Las validaciones de ``default_get`` con contraparte real (parcial
        declarado — ver el docstring del módulo): un solo diario."""
        moves = list(moves)
        journals = {move.journal_id for move in moves if move.journal_id}
        if len(journals) > 1:
            raise UserError(_(
                'You can only resequence items from the same journal'))
        return moves

    @classmethod
    def _compute_sequence_number_reset(cls, moves, first_name):
        """≙ ``_compute_sequence_number_reset`` — la periodicidad que el
        primer nombre nuevo implica."""
        return type(moves[0]).deduce_sequence_number_reset(first_name)

    @classmethod
    def _compute_first_name(cls, moves):
        """≙ ``_compute_first_name`` — el menor nombre actual, semilla del
        formato nuevo."""
        if not moves:
            return ""
        return min(move.name or "" for move in moves)

    @classmethod
    def _compute_preview_moves(cls, new_values, ordering,
                                sequence_number_reset):
        """Reduce the computed new_values to a smaller set to display in the preview.

        (Docstring verbatim de la referencia.) Misma elipsis: se muestran
        las 3 primeras, la última, y toda línea donde nombre-por-orden y
        nombre-por-fecha difieren o cambia el periodo.
        """
        values = sorted(json.loads(new_values).values(),
                        key=lambda x: x['server-date'], reverse=True)
        change_lines = []
        in_elipsis = 0
        previous_line = None
        for i, line in enumerate(values):
            if i < 3 or i == len(values) - 1 \
                    or line['new_by_name'] != line['new_by_date'] \
                    or (sequence_number_reset == 'year'
                        and line['server-date'][0:4] != previous_line['server-date'][0:4]) \
                    or (sequence_number_reset == 'year_range'
                        and line['server-year-start-date'][0:4] != previous_line['server-year-start-date'][0:4]) \
                    or (sequence_number_reset == 'month'
                        and line['server-date'][0:7] != previous_line['server-date'][0:7]):
                if in_elipsis:
                    change_lines.append({
                        'id': 'other_' + str(line['id']),
                        'current_name': _('... (%(nb_of_values)s other)') % {
                            'nb_of_values': in_elipsis},
                        'new_by_name': '...',
                        'new_by_date': '...',
                        'date': '...',
                    })
                    in_elipsis = 0
                change_lines.append(line)
            else:
                in_elipsis += 1
            previous_line = line

        return json.dumps({
            'ordering': ordering,
            'changeLines': change_lines,
        })

    @classmethod
    def _compute_new_values(cls, moves, first_name):
        """Compute the proposed new values.

        (Docstring de la referencia, adaptado.) Devuelve el JSON que mapea
        id de asiento → nombre propuesto por orden actual y por fecha —
        parcial declarado: año fiscal = año calendario (ver el docstring
        del módulo).
        """
        if not first_name or not moves:
            return "{}"
        moves = list(moves)
        sample = moves[0]
        sequence_number_reset = type(sample).deduce_sequence_number_reset(
            first_name)

        def _get_move_key(move):
            if sequence_number_reset == 'year':
                return move.date.year
            if sequence_number_reset == 'year_range':
                return "%s-%s" % (move.date.year, move.date.year)
            if sequence_number_reset == 'year_range_month':
                return "%s-%s/%s" % (move.date.year, move.date.year,
                                     move.date.month)
            if sequence_number_reset == 'month':
                return (move.date.year, move.date.month)
            return 'default'

        moves_by_period = defaultdict(list)
        for move in moves:
            moves_by_period[_get_move_key(move)].append(move)

        seq_format, format_values = sample.get_sequence_format_param(first_name)

        new_values = {}
        for j, period_recs in enumerate(moves_by_period.values()):
            date_start, date_end = period_recs[0].get_sequence_date_range(
                sequence_number_reset)
            for move in period_recs:
                new_values[move.id] = {
                    'id': move.id,
                    'current_name': move.name,
                    'state': move.state,
                    'date': move.date.isoformat(),
                    'server-date': str(move.date),
                    'server-year-start-date': str(date_start),
                }

            new_name_list = [seq_format.format(**{
                **format_values,
                'month': date_start.month,
                'year_end': date_end.year % (10 ** (format_values['year_end_length'] or 4)),
                'year': date_start.year % (10 ** (format_values['year_length'] or 4)),
                'seq': i + (format_values['seq']
                            if j == (len(moves_by_period) - 1) else 1),
            }) for i in range(len(period_recs))]

            by_name = sorted(period_recs,
                             key=lambda m: (m.sequence_prefix, m.sequence_number))
            for move, new_name in zip(by_name, new_name_list):
                new_values[move.id]['new_by_name'] = new_name
            by_date = sorted(period_recs,
                             key=lambda m: (m.date, m.name or "", m.id))
            for move, new_name in zip(by_date, new_name_list):
                new_values[move.id]['new_by_date'] = new_name

        return json.dumps(new_values)

    @classmethod
    def resequence(cls, moves, first_name, ordering='keep'):
        """Aplica los nombres propuestos — ≙ ``resequence`` (parcial
        declarado: sin guard de hash, ver el docstring del módulo)."""
        moves = cls.default_get(moves)
        new_values = json.loads(cls._compute_new_values(moves, first_name))

        # Primer pase: vaciar los nombres para no chocar transitoriamente —
        # ≙ ``moves_to_rename.name = False`` + ``flush_recordset``.
        moves_to_rename = [move for move in moves
                           if str(move.id) in new_values]
        for move in moves_to_rename:
            move.name = '/'
            move.save()

        key = 'new_by_name' if ordering == 'keep' else 'new_by_date'
        for move in moves_to_rename:
            move.name = new_values[str(move.id)][key]
            move.save()
        return new_values
