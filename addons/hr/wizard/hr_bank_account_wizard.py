"""``hr.bank.account.allocation.wizard`` — el asistente de distribución de
nómina entre cuentas.

Adaptación de Odoo hr/wizard/hr_bank_account_wizard.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3, 63 líneas) — atribución y aviso de
licencia preservados (DEC-KX-03).

``TransientModel`` → clase sin tabla con classmethods (patrón
``account_debit_note``). El estado (las líneas de asignación) viaja como
lista de dicts con las claves de
``hr.bank.account.allocation.wizard.line``.

Porte símbolo por símbolo — 7 símbolos
=======================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``_name`` / ``_description`` (``:7-8``)
     - portados verbatim
   * - ``employee_id`` (``:10``)
     - resuelto con otra forma — argumento ``employee`` de los classmethods
   * - ``allocation_ids`` (``:11``)
     - resuelto con otra forma — la lista de dicts que produce
       ``_prepare_allocations_from_employee`` y consume ``action_save``
   * - ``_prepare_allocations_from_employee`` (``:13-31``)
     - portado — devuelve la lista (el ``Command.create`` era la escritura
       del One2many transitorio)
   * - ``create`` (``:33-38``)
     - resuelto con otra forma — el override sólo encadenaba
       ``_prepare_allocations_from_employee`` tras crear la fila
       transitoria; sin fila, el llamador invoca el prepare directamente
   * - ``action_save`` (``:40-63``)
     - portado

Divergencias declaradas
========================

1. **``sudo()``** en la escritura de ``allow_out_payment`` — sin análogo ni
   necesidad (no hay record rules que eludir).
2. **``self.env._(…)``** → ``tools.translate._``.
3. **``ba.id`` como clave del JSON** — se conserva ``str(pk)`` verbatim: es
   el contrato de ``hr.employee.salary_distribution`` ya portado
   (``hr_employee.py``).
"""
from addons.hr.wizard.hr_bank_account_allocation_wizard_line import (
    BankAccountAllocationLineWizard,
)
from exceptions import ValidationError
from orm.models_transient import TransientModel
from tools.float_utils import float_is_zero, float_round
from tools.translate import _


class BankAccountAllocationWizard(TransientModel):
    """El asistente de distribución de nómina — ≙
    ``hr.bank.account.allocation.wizard``."""

    class Meta:
        abstract = True
        managed = False

    # ---- Atributos de clase de modelo — verbatim (``:7-8``) ----
    _name = 'hr.bank.account.allocation.wizard'
    _description = 'Bank Account Allocation Wizard'

    @classmethod
    def _prepare_allocations_from_employee(cls, employee):
        """Las líneas iniciales del wizard, desde la distribución vigente —
        ≙ ``_prepare_allocations_from_employee`` (``:13-31``)."""
        wizard_lines = []
        distribution = employee.salary_distribution or {}
        for bank_account in employee.bank_account.all():
            if str(bank_account.pk) not in distribution:
                raise ValidationError(
                    _('La cuenta bancaria %(account)s no aparece en la '
                      'distribución de nómina del empleado',
                      account=str(bank_account)),
                )
            dist_entry = distribution.get(str(bank_account.pk))
            wizard_lines.append({
                'bank_account_id': bank_account.pk,
                'amount': dist_entry.get('amount'),
                'amount_type': ('percentage'
                                if dist_entry.get('amount_is_percentage')
                                else 'fixed'),
                'trusted': bank_account.allow_out_payment,
                'sequence': dist_entry.get(
                    'sequence',
                    BankAccountAllocationLineWizard.DEFAULT_SEQUENCE,
                ),
            })
        return wizard_lines

    @classmethod
    def action_save(cls, employee, allocations):
        """Valida y persiste la distribución — ≙ ``action_save``
        (``:40-63``).

        ``allocations`` es la lista de dicts de línea; escribe
        ``allow_out_payment`` en cada cuenta y la distribución completa en
        ``employee.salary_distribution``. Si hay líneas porcentuales, el
        total debe ser 100 %.
        """
        distribution = {}
        total = 0.0
        check_for_total = False

        accounts_by_pk = {
            account.pk: account for account in employee.bank_account.all()
        }
        for line in allocations:
            line_amount = float_round(
                line['amount'], precision_digits=2, rounding_method='DOWN',
            )
            distribution[str(line['bank_account_id'])] = {
                'amount': line_amount,
                'sequence': line.get(
                    'sequence',
                    BankAccountAllocationLineWizard.DEFAULT_SEQUENCE,
                ),
                'amount_is_percentage': line.get('amount_type') == 'percentage',
            }
            if line.get('amount_type') == 'percentage':
                total += line_amount
                check_for_total = True
            bank_account = accounts_by_pk.get(line['bank_account_id'])
            if bank_account is not None:
                bank_account.allow_out_payment = bool(line.get('trusted'))
                bank_account.save(update_fields=['allow_out_payment'])
        if check_for_total and not float_is_zero(total - 100.0, precision_digits=4):
            raise ValidationError(
                _('La asignación porcentual total debe sumar 100%.'),
            )

        employee.salary_distribution = distribution
        employee.save(update_fields=['salary_distribution'])
        return distribution
