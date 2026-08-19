"""``account.automatic.entry.wizard`` — cambiar periodo o cuenta de apuntes.

Adaptación de Odoo ``addons/account/wizard/account_automatic_entry_wizard.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3 —
atribución y aviso de licencia preservados, DEC-KX-03).

``TransientModel`` → clase con classmethods, no tabla — mismo patrón que
``AccountDebitNoteWizard``.

Cuarenta y tres símbolos de la referencia (15 campos + 28 defs)
================================================================

Campos → parámetros de los classmethods (``action``, ``move_line_ids`` →
``lines``, ``date``, ``company_id`` → ``company``, ``percentage``,
``total_amount``, ``journal_id`` → ``journal``, ``account_type``,
``expense_accrual_account`` / ``revenue_accrual_account`` →
``accrual_account``, ``destination_account_id`` → ``destination_account``).
``company_currency_id`` (related) y ``display_currency_helper`` /
``lock_date_message`` / ``move_data`` / ``preview_move_data`` son soporte
del formulario; sus computes se listan abajo.

===================================  ======================================
Defs de la referencia                 Qué pasa aquí
===================================  ======================================
``_compute_expense_accrual_account``  NO — lee
                                       ``company.expense_accrual_account_id``
                                       (campo de ``res.company`` de la
                                       referencia no portado —
                                       ``models/res_company.py`` porta
                                       candados y cuentas de utilidad, no
                                       las de devengo). La cuenta viaja por
                                       parámetro (``accrual_account``).
``_inverse_expense_accrual_account``  NO — escribe el mismo campo.
``_compute_revenue_accrual_account``  NO — ídem.
``_inverse_revenue_accrual_account``  NO — ídem.
``_compute_journal_id``               NO — lee
                                       ``company.automatic_entry_default_
                                       journal_id`` (no portado); el diario
                                       viaja por parámetro.
``_inverse_journal_id``               NO — escribe el mismo campo.
``_constraint_percentage``            PORTADO
``_compute_total_amount``             PORTADO
``_compute_percentage``               PORTADO
``_compute_account_type``             PORTADO
``_compute_lock_date_message``        PORTADO — sobre
                                       ``get_violated_lock_dates`` /
                                       ``format_lock_dates`` ya portados en
                                       ``models/res_company.py``
``_compute_display_currency_helper``  PORTADO
``_check_date``                       PORTADO — mismas funciones de candado
``default_get``                       PORTADO (parcial declarado, ver su
                                       docstring)
``_get_cut_off_label_format``         PORTADO
``_get_move_dict_vals_change_account``  PORTADO (parcial declarado)
``_get_move_line_dict_vals_change_period``  PORTADO (parcial declarado)
``_get_lock_safe_date``               PORTADO (adaptado declarado, ver su
                                       docstring)
``_get_move_dict_vals_change_period``  PORTADO
``_compute_move_data``                PORTADO
``_compute_preview_move_data``        NO — bloqueado por
                                       ``account.move._move_dict_to_
                                       preview_vals`` (previsualizador del
                                       cliente web, no portado — misma
                                       exclusión que ``accrued_orders.py``).
``do_action``                         PORTADO
``_do_action_change_period``          PORTADO (parcial declarado)
``_do_action_change_account``         PORTADO (parcial declarado)
``_format_new_transfer_move_log``     NO — HTML de chatter (``Markup`` +
                                       ``message_post``); el chatter de
                                       ``mail`` sobre ``account.move`` no
                                       está portado.
``_format_transfer_source_log``       NO — ídem.
``_format_move_link``                 NO — ``move._get_html_link``
                                       (chatter).
``_format_strings``                   PORTADO (parcial declarado:
                                       ``formatLang``/``format_date`` por
                                       locale → f-string/isoformat; sin las
                                       claves ``link``/``account_*`` que
                                       sólo consumen los logs de chatter
                                       de arriba)
===================================  ======================================

Divergencias transversales declaradas (mismas que el resto del directorio):

- ``amount_currency`` / ``currency_id`` por línea y
  ``analytic_distribution`` no existen en el puerto de
  ``account.move.line`` — todo importe es en moneda de la empresa y el
  prorrateo analítico de la contrapartida queda fuera (se incorpora con
  esos campos, sin cambiar firmas).
- ``partner_id`` por línea tampoco existe: el agrupado de contrapartidas de
  ``change_account`` es por cuenta (la referencia agrupa por
  ``(partner, currency)``); el agrupado de líneas fuente, por cuenta en vez
  de ``(partner, currency, account, analytic)``.
- ``line.reconciled`` → aquí "tiene partials": ``matched_debit_ids`` /
  ``matched_credit_ids`` (los related que ``account_partial_reconcile.py``
  ya declara).
- El árbol de empresas (``root_id`` / ``parent_ids`` / la empresa hija más
  baja por cuentas) se colapsa a la empresa de las líneas — el puerto de
  cuenta tiene FK simple de empresa, no ``company_ids``.
"""
import json
from collections import defaultdict
from datetime import timedelta

from django.db import transaction

from addons.account.models.account_move import AccountMove
from addons.account.models.account_move_line import AccountMoveLine
from addons.account.models.account_partial_reconcile import AccountPartialReconcile
from addons.account.models.res_company import (
    format_lock_dates,
    get_violated_lock_dates,
)
from exceptions import UserError, ValidationError
from orm.models_transient import TransientModel
from tools.misc import groupby
from tools.translate import _

#: ≙ el selection del campo ``action`` — las dos operaciones del wizard.
ACTION_SELECTION = [
    ('change_period', 'Change Period'),
    ('change_account', 'Change Account'),
]


def _line_is_reconciled(line):
    """``line.reconciled`` de la referencia — aquí, tener algún partial."""
    return line.matched_debit_ids.exists() or line.matched_credit_ids.exists()


class AccountAutomaticEntryWizard(TransientModel):
    """≙ ``account.automatic.entry.wizard`` — genera los asientos que mueven
    apuntes publicados de periodo (devengo) o de cuenta (traspaso)."""

    _name = 'account.automatic.entry.wizard'
    _description = 'Create Automatic Entries'
    _check_company_auto = True

    class Meta:
        abstract = True
        managed = False

    # -- computes / constraints ------------------------------------------

    @classmethod
    def _constraint_percentage(cls, percentage, action):
        """≙ ``_constraint_percentage``."""
        if not (0.0 < percentage <= 100.0) and action == 'change_period':
            raise UserError(_("Percentage must be between 0 and 100"))

    @classmethod
    def _compute_total_amount(cls, lines, percentage=None):
        """≙ ``_compute_total_amount`` — el porcentaje del balance total."""
        return (percentage or 100) * sum(
            line.balance for line in lines) / 100

    @classmethod
    def _compute_percentage(cls, lines, total_amount):
        """≙ ``_compute_percentage`` — el porcentaje que ``total_amount``
        representa (min 100, mismo guard de redondeo)."""
        total = sum(line.balance for line in lines) or total_amount
        if total != 0:
            return min((total_amount / total) * 100, 100)
        return 100

    @classmethod
    def _compute_account_type(cls, lines):
        """≙ ``_compute_account_type`` — ingreso si el balance es negativo."""
        return 'income' if sum(line.balance for line in lines) < 0 else 'expense'

    @classmethod
    def _compute_lock_date_message(cls, action, lines):
        """≙ ``_compute_lock_date_message`` — el primer candado que la fecha
        de algún apunte viola. La referencia delega en
        ``move._get_lock_date_message`` (no portado); aquí se compone con
        las funciones de candado ya portadas en ``models/res_company.py``."""
        if action != 'change_period':
            return False
        for line in lines:
            move = line.move
            violations = get_violated_lock_dates(
                move.company, move.date, False)
            if violations:
                return format_lock_dates(move.company, violations)
        return False

    @classmethod
    def _compute_display_currency_helper(cls, destination_account):
        """≙ ``_compute_display_currency_helper`` — hay ayuda de conversión
        cuando la cuenta destino declara moneda propia."""
        return bool(destination_account is not None
                    and destination_account.currency_id)

    @classmethod
    def _check_date(cls, date, lines):
        """≙ ``_check_date`` — la fecha elegida no puede caer en un periodo
        bloqueado."""
        for line in lines:
            move = line.move
            violated = get_violated_lock_dates(
                move.company, date, False)
            if violated:
                raise ValidationError(_(
                    'The date selected is protected by: %(lock_date_info)s.'
                ) % {'lock_date_info': format_lock_dates(move.company,
                                                          violated)})

    @classmethod
    def default_get(cls, lines, default_action=None):
        """≙ ``default_get`` (parcial declarado) — las tres validaciones y
        la elección de acción. El ``root_id`` del árbol de empresas se
        colapsa a igualdad de empresa (ver el docstring del módulo).

        Devuelve ``(lines, company, action)``.
        """
        lines = list(lines)
        if not lines:
            raise UserError(_('This can only be used on journal items'))
        if any(line.move.state != 'posted' for line in lines):
            raise UserError(_(
                "Oops! You can only change the period or account for "
                "posted entries! Other ones aren't up for an adventure "
                "like that!"))
        if any(_line_is_reconciled(line) for line in lines):
            raise UserError(_(
                "Oops! You can only change the period or account for items "
                "that are not yet reconciled! Other ones aren't up for an "
                "adventure like that!"))
        companies = {line.move.company_id for line in lines}
        if len(companies) > 1:
            raise UserError(_(
                'You cannot use this wizard on journal entries belonging '
                'to different companies.'))
        company = lines[0].move.company

        allowed_actions = set(dict(ACTION_SELECTION))
        if default_action:
            allowed_actions = {default_action}
        if any(line.account.account_type != lines[0].account.account_type
               for line in lines):
            allowed_actions.discard('change_period')
        if not allowed_actions:
            raise UserError(_(
                'No possible action found with the selected lines.'))
        return lines, company, allowed_actions.pop()

    # -- construcción de asientos ----------------------------------------

    @classmethod
    def _get_cut_off_label_format(cls, percentage):
        """ Get the translated format string used in cut-off labels

        (Docstring verbatim de la referencia.)"""
        return _("Cut-off {label}") if percentage == 100 \
            else _("Cut-off {label} {percent}%")

    @classmethod
    def _get_move_dict_vals_change_account(cls, lines, journal,
                                            destination_account, date):
        """≙ ``_get_move_dict_vals_change_account`` (parcial declarado —
        agrupado por cuenta, sin partner/moneda/analítica por línea; ver el
        docstring del módulo)."""
        line_vals = []

        counterpart_balance = 0
        grouped_source_lines = defaultdict(list)
        for line in lines:
            if line.account_id == (destination_account.pk
                                   if destination_account else None):
                continue
            counterpart_balance += line.balance
            grouped_source_lines[line.account].append(line)

        source_accounts = {line.account for line in lines}
        if len(source_accounts) == 1:
            counterpart_label = _("Transfer from %s") % next(
                iter(source_accounts))
        else:
            counterpart_label = _("Transfer counterpart")

        if counterpart_balance:
            line_vals.append({
                'name': counterpart_label,
                'debit': counterpart_balance if counterpart_balance > 0 else 0,
                'credit': -counterpart_balance if counterpart_balance < 0 else 0,
                'account_id': destination_account.pk,
            })

        for account, account_lines in grouped_source_lines.items():
            account_balance = sum(line.balance for line in account_lines)
            if account_balance:
                line_vals.append({
                    'name': _('Transfer to %s') % (
                        destination_account or _('[Not set]')),
                    'debit': -account_balance if account_balance < 0 else 0,
                    'credit': account_balance if account_balance > 0 else 0,
                    'account_id': account.pk,
                })

        return [{
            'move_type': 'entry',
            'name': '/',
            'journal_id': journal.pk,
            'date': date.isoformat(),
            'ref': _("Transfer entry to %s") % (destination_account or ''),
            'line_ids': line_vals,
        }]

    @classmethod
    def _get_move_line_dict_vals_change_period(cls, aml, date_key,
                                                accrual_account, percentage):
        """≙ ``_get_move_line_dict_vals_change_period`` — el par de líneas
        (cuenta original ↔ cuenta de devengo) por apunte, prorrateado
        (parcial declarado: sin ``amount_currency``/analítica/partner)."""
        reported_debit = round((percentage / 100) * float(aml.debit), 2)
        reported_credit = round((percentage / 100) * float(aml.credit), 2)
        name = cls._format_strings(
            cls._get_cut_off_label_format(percentage), aml.move, percentage)

        if date_key == 'new_date':
            return [
                {'name': name, 'debit': reported_debit,
                 'credit': reported_credit, 'account_id': aml.account_id},
                {'name': name, 'debit': reported_credit,
                 'credit': reported_debit, 'account_id': accrual_account.pk},
            ]
        return [
            {'name': name, 'debit': reported_credit,
             'credit': reported_debit, 'account_id': aml.account_id},
            {'name': name, 'debit': reported_debit,
             'credit': reported_credit, 'account_id': accrual_account.pk},
        ]

    @classmethod
    def _get_lock_safe_date(cls, date, company):
        """≙ ``_get_lock_safe_date`` (adaptado declarado).

        La referencia delega en ``account.move._get_accounting_date`` sobre
        un asiento de referencia del diario (no portado). El efecto que ese
        método produce —empujar la fecha fuera de los periodos bloqueados—
        se compone aquí con las funciones de candado ya portadas: si la
        fecha viola algún candado, se corre al día siguiente del candado
        más alto violado.
        """
        violations = get_violated_lock_dates(company, date, False)
        if not violations:
            return date
        latest = max(lock_date for lock_date, _field in violations)
        return latest + timedelta(days=1)

    @classmethod
    def _get_move_dict_vals_change_period(cls, lines, journal, date,
                                           accrual_account, percentage):
        """≙ ``_get_move_dict_vals_change_period`` — un asiento en la fecha
        nueva y uno por cada fecha (a salvo de candados) de origen."""
        ref_format = cls._get_cut_off_label_format(percentage)

        def get_lock_safe_date(aml):
            # La línea del puerto no lleva fecha propia: la del asiento.
            return cls._get_lock_safe_date(aml.move.date, aml.move.company)

        move_data = {'new_date': {
            'move_type': 'entry',
            'line_ids': [],
            'ref': cls._format_strings(ref_format, lines[0].move, percentage),
            'date': date.isoformat(),
            'journal_id': journal.pk,
        }}
        for date_key, grouped_lines in groupby(lines, get_lock_safe_date):
            grouped_lines = list(grouped_lines)
            amount = sum(l.balance for l in grouped_lines)
            move_data[date_key] = {
                'move_type': 'entry',
                'line_ids': [],
                'ref': cls._format_strings(
                    ref_format, grouped_lines[0].move, percentage, amount),
                'date': date_key.isoformat(),
                'journal_id': journal.pk,
            }

        for aml in lines:
            for date_key in ('new_date', get_lock_safe_date(aml)):
                move_data[date_key]['line_ids'] += \
                    cls._get_move_line_dict_vals_change_period(
                        aml, date_key, accrual_account, percentage)

        return list(move_data.values())

    @classmethod
    def _compute_move_data(cls, action, lines, journal, date,
                            accrual_account=None, percentage=100,
                            destination_account=None):
        """≙ ``_compute_move_data`` — el JSON de los asientos a crear."""
        if action == 'change_period':
            if any(line.account.account_type != lines[0].account.account_type
                   for line in lines):
                raise UserError(_(
                    'All accounts on the lines must be of the same type.'))
            return json.dumps(cls._get_move_dict_vals_change_period(
                lines, journal, date, accrual_account, percentage))
        if action == 'change_account':
            return json.dumps(cls._get_move_dict_vals_change_account(
                lines, journal, destination_account, date))
        return None

    # -- ejecución --------------------------------------------------------

    @classmethod
    def _create_moves_from_vals(cls, move_vals_list, company):
        """Materializa los dicts de ``move_data`` — el ``create`` +
        ``_post`` que la referencia hace vía ORM."""
        created = []
        for move_vals in move_vals_list:
            line_vals = move_vals.pop('line_ids')
            move = AccountMove.objects.create(
                move_type=move_vals['move_type'],
                ref=move_vals.get('ref') or '',
                journal_id=move_vals['journal_id'],
                date=move_vals['date'],
                company=company,
                state='draft',
            )
            for values in line_vals:
                AccountMoveLine.objects.create(
                    move=move,
                    name=values['name'],
                    debit=values['debit'],
                    credit=values['credit'],
                    account_id=values['account_id'],
                )
            move.post()
            created.append(move)
        return created

    @classmethod
    @transaction.atomic
    def do_action(cls, action, lines, journal, date, company,
                   accrual_account=None, percentage=100,
                   destination_account=None):
        """≙ ``do_action`` — despacha a la operación elegida."""
        move_vals = json.loads(cls._compute_move_data(
            action, lines, journal, date,
            accrual_account=accrual_account, percentage=percentage,
            destination_account=destination_account))
        if action == 'change_period':
            return cls._do_action_change_period(
                move_vals, lines, company, accrual_account)
        if action == 'change_account':
            return cls._do_action_change_account(
                move_vals, lines, company, destination_account)
        return None

    @classmethod
    def _do_action_change_period(cls, move_vals, lines, company,
                                  accrual_account):
        """≙ ``_do_action_change_period`` (parcial declarado — sin los
        ``message_post`` de chatter ni el ``ir.actions.act_window`` final;
        devuelve los asientos creados).

        La reconciliación de las líneas de devengo entre el asiento destino
        y los de origen se hace con ``create_partial`` cuando la cuenta es
        conciliable — el mismo álgebra que ``account_payment_register.py``.
        """
        created_moves = cls._create_moves_from_vals(move_vals, company)
        if accrual_account is not None and accrual_account.reconcile:
            destination_move = created_moves[0]
            destination_lines = list(destination_move.line_ids.filter(
                account=accrual_account))
            for accrual_move in created_moves[1:]:
                accrual_lines = list(accrual_move.line_ids.filter(
                    account=accrual_account))
                for dest, accr in zip(destination_lines, accrual_lines):
                    debit_line = dest if dest.debit else accr
                    credit_line = accr if dest.debit else dest
                    amount = debit_line.debit
                    if amount:
                        AccountPartialReconcile.create_partial(
                            debit_move=debit_line, credit_move=credit_line,
                            amount=amount)
        return created_moves

    @classmethod
    def _do_action_change_account(cls, move_vals, lines, company,
                                   destination_account):
        """≙ ``_do_action_change_account`` (parcial declarado — mismo
        recorte que ``_do_action_change_period``: sin chatter ni acción de
        ventana; reconcilia por cuenta conciliable vía ``create_partial``).
        """
        new_moves = cls._create_moves_from_vals(move_vals, company)
        new_move = new_moves[0]

        grouped_lines = defaultdict(list)
        for line in lines:
            if destination_account is not None \
                    and line.account_id == destination_account.pk:
                continue
            grouped_lines[line.account].append(line)

        for account, account_lines in grouped_lines.items():
            if not account.reconcile:
                continue
            counterparts = list(new_move.line_ids.filter(account=account))
            for original, counterpart in zip(account_lines, counterparts):
                debit_line = original if original.debit else counterpart
                credit_line = counterpart if original.debit else original
                amount = debit_line.debit
                if amount:
                    AccountPartialReconcile.create_partial(
                        debit_move=debit_line, credit_move=credit_line,
                        amount=amount)
        return new_moves

    # -- formato ----------------------------------------------------------

    @classmethod
    def _format_strings(cls, string, move, percentage, amount=None):
        """≙ ``_format_strings`` (parcial declarado — sin
        ``formatLang``/``format_date`` por locale ni las claves de chatter
        ``link``/``account_source_name``/``account_target_name``; ver la
        tabla del módulo)."""
        return string.format(
            label=move.name or _('Adjusting Entry'),
            percent=f'{percentage:.2f}',
            name=move.name,
            id=move.id,
            amount=f'{abs(amount):.2f}' if amount else '',
            date=move.date.isoformat() if move.date else '',
        )
