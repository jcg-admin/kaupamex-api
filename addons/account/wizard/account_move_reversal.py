"""``account.move.reversal`` — el asistente "Revertir asiento / Nota de crédito".

Adaptación de Odoo ``addons/account/wizard/account_move_reversal.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3 —
atribución y aviso de licencia preservados, DEC-KX-03).

``TransientModel`` → clase con classmethods, no tabla — mismo patrón que
``AccountDebitNoteWizard``: el estado del wizard (asientos, fecha, razón,
diario) lo pasa el llamador como argumentos.

Veintiún símbolos de la referencia (11 campos + 10 defs) — el desglose
=======================================================================

================================  =========================================
Símbolo de la referencia           Qué pasa aquí
================================  =========================================
``move_ids`` (campo)               PORTADO — parámetro ``moves``
``new_move_ids`` (campo)           PORTADO — valor de retorno de
                                    ``reverse_moves``
``date`` (campo)                   PORTADO — parámetro ``date``
``reason`` (campo)                 PORTADO — parámetro ``reason``
``journal_id`` (campo)             PORTADO — parámetro ``journal`` +
                                    ``_compute_journal_id``
``company_id`` (campo)             PORTADO — lo deriva ``default_get``
``available_journal_ids``          PORTADO — ``_compute_available_journal_ids``
``country_code`` (related)         NO — sólo visibilidad condicional del
                                    formulario Odoo (widgets por país), sin
                                    lector de negocio.
``residual`` (compute)             PORTADO — ``_compute_from_moves``
``currency_id`` (compute)          PORTADO — ``_compute_from_moves``
``move_type`` (compute)            PORTADO — ``_compute_from_moves``
``_compute_journal_id``            PORTADO
``_compute_available_journal_ids`` PORTADO
``_check_journal_type``            PORTADO
``default_get``                    PORTADO (la parte con lógica real; la
                                    lectura de ``active_ids`` es mecánica
                                    del cliente web — el llamador pasa
                                    ``moves``)
``_compute_from_moves``            PORTADO
``_prepare_default_reversal``      PORTADO (parcial declarado, ver su
                                    docstring)
``reverse_moves``                  PORTADO (parcial declarado, ver su
                                    docstring)
``refund_moves``                   PORTADO
``modify_moves``                   PORTADO
``_modify_default_reverse_values`` PORTADO (parcial declarado)
================================  =========================================

La mecánica de reversión — construida aquí, no excusada
========================================================

La referencia delega en ``account.move._reverse_moves``
(``odoo19c: account_move.py:5452``), que no está en el puerto de
``account_move.py``. En vez de declarar todo bloqueado, la mecánica se
construye en ``_reverse_single_move`` con las piezas que sí existen:

- ``TYPE_REVERSE_MAP`` — verbatim de ``odoo19c: account_move.py:58-66``.
- La negación del balance (``Command.update(balance=-balance)`` de la
  referencia) aquí es intercambiar ``debit`` ↔ ``credit`` por línea — misma
  aritmética sobre el esquema de dos columnas del puerto.
- ``cancel=True`` (rama ``is_modify`` / asientos ``entry``): la referencia
  concilia el reverso contra el original y postea duro; aquí se postea el
  reverso y se emparejan las líneas receivable/payable originales contra
  las del reverso vía ``AccountPartialReconcile.create_partial`` +
  ``AccountFullReconcile.create_from_partials`` — el mismo álgebra que ya
  consume ``account_payment_register.py``.

Divergencias declaradas (por símbolo)
======================================

- ``_prepare_default_reversal``: ``invoice_date_due`` / ``invoice_date`` /
  ``invoice_payment_term_id`` / ``invoice_user_id`` / ``auto_post`` /
  ``invoice_origin`` no existen en el puerto de ``account.move`` (la capa
  de factura con vencimientos/términos no está portada). Se portan las
  claves con contraparte real: ``ref`` (con el texto "Reversal of" de la
  referencia), ``date`` y ``journal``. El resto se incorpora cuando esos
  campos aterricen — sin tocar la firma.
- ``reverse_moves``: el bacheo por ``auto_post`` colapsa — sin ``auto_post``
  todo reverso es inmediato, así que ``is_cancel_needed`` queda en
  ``is_modify or move_type == 'entry'`` (la otra mitad de la condición de
  la referencia). ``_compute_partner_bank_id`` y ``_message_log_batch``
  (chatter) no están portados — el reverso no deja mensaje. El retorno es
  la lista de movimientos nuevos, no un ``ir.actions.act_window`` (misma
  exclusión de navegación que ``AccountDebitNoteWizard``).
- ``reverse_moves`` con ``is_modify=True``: la referencia además **recrea**
  el asiento original (``move.copy_data(...)`` filtrando líneas de
  producto/sección). ``copy_data`` no existe en este árbol (medido en el
  porte de ``account_debit_note``); la recreación copia explícitamente los
  campos del movimiento y sus líneas de producto/sección/nota — los
  ``display_type`` de la referencia, contra el vocabulario que el puerto
  de ``account_move_line`` declara.
- ``_modify_default_reverse_values``: la mitad del adjunto de proveedor
  (``message_main_attachment_id`` + ``attachment_ids``) está bloqueada por
  el chatter de ``mail`` sobre ``account.move`` (no portado aquí); se porta
  la mitad con contraparte: ``date`` (``invoice_origin``, ver arriba).
"""
from django.db import transaction
from django.utils import timezone

from addons.account.models.account_full_reconcile import AccountFullReconcile
from addons.account.models.account_journal import AccountJournal
from addons.account.models.account_move import AccountMove
from addons.account.models.account_move_line import AccountMoveLine
from addons.account.models.account_partial_reconcile import AccountPartialReconcile
from exceptions import UserError
from orm.models_transient import TransientModel
from tools.translate import _

#: ≙ ``TYPE_REVERSE_MAP`` (``odoo19c: account_move.py:58-66``), verbatim.
TYPE_REVERSE_MAP = {
    'entry': 'entry',
    'out_invoice': 'out_refund',
    'out_refund': 'out_invoice',
    'in_invoice': 'in_refund',
    'in_refund': 'in_invoice',
    'out_receipt': 'out_refund',
    'in_receipt': 'in_refund',
}

#: Los ``display_type`` que ``is_modify`` conserva al recrear el original —
#: ≙ la lista de ``reverse_moves`` (``odoo19c:
#: account_move_reversal.py:146``).
_MODIFY_KEPT_DISPLAY_TYPES = (
    'product', 'line_section', 'line_subsection', 'line_note',
)

#: Campos de línea que se copian al revertir/recrear — el subconjunto de
#: columnas propias de la línea (mismo criterio que
#: ``AccountDebitNoteWizard.LINE_COPY_FIELDS``).
_LINE_COPY_FIELDS = (
    'account', 'name', 'display_type', 'quantity', 'price_unit', 'currency',
)


class AccountMoveReversal(TransientModel):
    """
    Account move reversal wizard, it cancel an account move by reversing it.

    (Docstring verbatim de la referencia.) ≙ ``account.move.reversal``.
    """

    _name = 'account.move.reversal'
    _description = 'Account Move Reversal'
    _check_company_auto = True

    class Meta:
        abstract = True
        managed = False

    # -- computes / constraints ------------------------------------------

    @classmethod
    def _compute_journal_id(cls, moves, journal=None):
        """El diario por defecto — ≙ ``_compute_journal_id``: el elegido, o
        el primer diario activo de los asientos a revertir."""
        if journal is not None:
            return journal
        for move in moves:
            if move.journal is not None and move.journal.active:
                return move.journal
        return None

    @classmethod
    def _compute_available_journal_ids(cls, company, moves=None):
        """Diarios elegibles — ≙ ``_compute_available_journal_ids``: los de
        la empresa, acotados al tipo de los diarios de los asientos."""
        queryset = AccountJournal.objects.filter(company=company)
        if moves:
            types = {move.journal.type for move in moves if move.journal}
            queryset = queryset.filter(type__in=types)
        return queryset

    @classmethod
    def _check_journal_type(cls, journal, moves):
        """≙ ``_check_journal_type`` — el diario del reverso debe ser del
        mismo tipo que el del asiento revertido."""
        move_types = {move.journal.type for move in moves if move.journal}
        if journal is not None and journal.type not in move_types:
            raise UserError(_(
                'Journal should be the same type as the reversed entry.'))

    @classmethod
    def default_get(cls, moves):
        """Las dos validaciones de ``default_get`` (la parte con lógica
        real) — devuelve la empresa común de los asientos."""
        moves = list(moves)
        companies = {move.company_id for move in moves}
        if len(companies) > 1:
            raise UserError(_(
                'All selected moves for reversal must belong to the same '
                'company.'))
        if any(move.state != 'posted' for move in moves):
            raise UserError(_(
                'To reverse a journal entry, it has to be posted first.'))
        return moves[0].company if moves else None

    @classmethod
    def _compute_from_moves(cls, moves):
        """Los tres derivados del formulario — ≙ ``_compute_from_moves``.

        Devuelve ``{'residual', 'currency', 'move_type'}`` con la misma
        semántica: sólo hay residual/moneda con un único asiento;
        ``move_type`` colapsa a ``'some_invoice'`` cuando hay mezcla con
        alguna factura.
        """
        moves = list(moves)
        currencies = {move.currency for move in moves if move.currency}
        if len(moves) == 1:
            move_type = moves[0].move_type
        elif any(move.move_type in ('in_invoice', 'out_invoice')
                 for move in moves):
            move_type = 'some_invoice'
        else:
            move_type = False
        return {
            'residual': moves[0].get_amount_residual() if len(moves) == 1 else 0,
            'currency': currencies.pop() if len(currencies) == 1 else None,
            'move_type': move_type,
        }

    # -- reversión --------------------------------------------------------

    @classmethod
    def _prepare_default_reversal(cls, move, date=None, reason=None,
                                   journal=None):
        """Los valores del reverso — ≙ ``_prepare_default_reversal``
        (parcial declarado — ver el docstring del módulo)."""
        reverse_date = date or timezone.now().date()
        if reason:
            ref = _('Reversal of: %(move_name)s, %(reason)s') % {
                'move_name': move.name, 'reason': reason}
        else:
            ref = _('Reversal of: %s') % move.name
        return {
            'ref': ref,
            'date': reverse_date,
            'journal': journal or move.journal,
        }

    @classmethod
    def _reverse_single_move(cls, move, default_values):
        """Crea el reverso de ``move`` — la mecánica de
        ``account.move._reverse_moves`` construida aquí (ver el docstring
        del módulo): tipo mapeado por ``TYPE_REVERSE_MAP``, líneas con
        ``debit`` ↔ ``credit`` intercambiados."""
        reverse_move = AccountMove.objects.create(
            move_type=TYPE_REVERSE_MAP[move.move_type],
            partner=move.partner,
            company=move.company,
            currency=move.currency,
            state='draft',
            **default_values,
        )
        for line in move.line_ids.all():
            values = {field: getattr(line, field)
                      for field in _LINE_COPY_FIELDS}
            AccountMoveLine.objects.create(
                move=reverse_move, debit=line.credit, credit=line.debit,
                **values,
            )
        return reverse_move

    @classmethod
    def _cancel_with_reverse(cls, move, reverse_move):
        """La mitad ``cancel=True`` de ``_reverse_moves``: empareja las
        líneas receivable/payable del original contra las del reverso —
        mismo álgebra que ``account_payment_register.py``."""
        residual_types = AccountMove._RESIDUAL_ACCOUNT_TYPES
        original_lines = list(move.line_ids.filter(
            account__account_type__in=residual_types))
        reverse_lines = list(reverse_move.line_ids.filter(
            account__account_type__in=residual_types))
        partials = []
        for original, reverse in zip(original_lines, reverse_lines):
            debit_line = original if original.debit else reverse
            credit_line = reverse if original.debit else original
            amount = original.debit or original.credit
            if not amount:
                continue
            partials.append(AccountPartialReconcile.create_partial(
                debit_move=debit_line, credit_move=credit_line,
                amount=amount,
            ))
        if partials and move.get_amount_residual() <= 0:
            AccountFullReconcile.create_from_partials(partials)
        return partials

    @classmethod
    def _recreate_move(cls, move, modify_values):
        """La recreación del original en ``is_modify=True`` — el
        ``move.copy_data(...)`` de la referencia, con la copia explícita
        que este árbol usa en vez de ``copy()`` (ver el docstring del
        módulo). Conserva sólo las líneas de producto/sección/nota."""
        new_move = AccountMove.objects.create(
            move_type=move.move_type,
            ref=move.ref,
            journal=move.journal,
            partner=move.partner,
            currency=move.currency,
            company=move.company,
            state='draft',
            **modify_values,
        )
        for line in move.line_ids.all():
            if line.display_type not in _MODIFY_KEPT_DISPLAY_TYPES:
                continue
            values = {field: getattr(line, field)
                      for field in _LINE_COPY_FIELDS}
            AccountMoveLine.objects.create(
                move=new_move, debit=line.debit, credit=line.credit,
                **values,
            )
        return new_move

    @classmethod
    @transaction.atomic
    def reverse_moves(cls, moves, date=None, reason=None, journal=None,
                      is_modify=False):
        """Revierte los asientos — ≙ ``reverse_moves`` (parcial declarado,
        ver el docstring del módulo).

        Devuelve la lista de movimientos creados (reversos, más los
        recreados si ``is_modify``) — sin ``ir.actions.act_window``.
        """
        moves = cls.default_get(moves)
        cls._check_journal_type(journal, moves) if journal else None
        from_moves = cls._compute_from_moves(moves)

        new_moves = []
        for move in moves:
            default_values = cls._prepare_default_reversal(
                move, date=date, reason=reason, journal=journal)
            # Sin ``auto_post`` todo reverso es inmediato — la condición de
            # bacheo de la referencia se reduce a esta mitad.
            is_cancel_needed = is_modify or from_moves['move_type'] == 'entry'
            reverse_move = cls._reverse_single_move(move, default_values)
            reverse_move.post()
            if is_cancel_needed:
                cls._cancel_with_reverse(move, reverse_move)
                move.compute_payment_state()
            new_moves.append(reverse_move)

            if is_modify:
                modify_values = cls._modify_default_reverse_values(
                    move, date=date)
                new_moves.append(cls._recreate_move(move, modify_values))

        return new_moves

    @classmethod
    def refund_moves(cls, moves, date=None, reason=None, journal=None):
        """≙ ``refund_moves`` — reverso sin recrear el original."""
        return cls.reverse_moves(moves, date=date, reason=reason,
                                 journal=journal, is_modify=False)

    @classmethod
    def modify_moves(cls, moves, date=None, reason=None, journal=None):
        """≙ ``modify_moves`` — reverso + recreación editable del original."""
        return cls.reverse_moves(moves, date=date, reason=reason,
                                 journal=journal, is_modify=True)

    @classmethod
    def _modify_default_reverse_values(cls, origin_move, date=None):
        """≙ ``_modify_default_reverse_values`` (parcial declarado — la
        mitad del adjunto de proveedor está bloqueada por el chatter de
        ``mail`` sobre ``account.move``; ver el docstring del módulo)."""
        return {
            'date': date or timezone.now().date(),
        }
