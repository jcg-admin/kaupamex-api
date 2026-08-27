"""``hr.bank.account.allocation.wizard.line`` — una línea del asistente de
distribución de nómina.

Adaptación de Odoo hr/wizard/hr_bank_account_allocation_wizard_line.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3, 29 líneas) — atribución y aviso de
licencia preservados (DEC-KX-03).

``TransientModel`` → clase sin tabla con classmethods, mismo patrón que
``account_debit_note/wizard/account_debit_note.py`` (ver su docstring:
"formulario, no tabla"): el estado del wizard lo pasa el llamador, aquí
como **dicts de línea** con las claves de los campos de la referencia.

Porte símbolo por símbolo — 13 símbolos
========================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``_name`` / ``_description`` / ``_order`` (``:5-7``)
     - portados verbatim como atributos de clase
   * - ``wizard_id`` (``:9``)
     - resuelto con otra forma — la pertenencia línea → wizard es la lista
       que arma ``BankAccountAllocationWizard._prepare_allocations_from_employee``
   * - ``bank_account_id`` (``:10``)
     - clave ``'bank_account_id'`` del dict de línea
   * - ``acc_number`` (``related``, ``:12``)
     - se lee de ``bank_account.acc_number`` — el related era espejo de
       formulario
   * - ``amount`` (``:13``)
     - clave ``'amount'``
   * - ``amount_type`` (``:14``)
     - clave ``'amount_type'``; sus opciones son
       ``_get_amount_type_selection_vals``
   * - ``symbol`` (compute, ``:15``)
     - ``_compute_symbol`` (abajo)
   * - ``trusted`` (``:16``)
     - clave ``'trusted'``
   * - ``sequence`` (``:17``)
     - clave ``'sequence'`` (default 10, el de la referencia)
   * - ``_compute_symbol`` (``:19-26``)
     - portado — recibe la línea y el empleado (el ``wizard_id.employee_id``
       de la referencia) como argumentos
   * - ``_get_amount_type_selection_vals`` (``:28-29``)
     - portado verbatim
"""
from orm.models_transient import TransientModel


class BankAccountAllocationLineWizard(TransientModel):
    """Una línea de la distribución — ≙
    ``hr.bank.account.allocation.wizard.line``.

    Sin tabla: la línea es un dict con las claves ``bank_account_id``,
    ``amount``, ``amount_type``, ``trusted`` y ``sequence`` (ver
    ``BankAccountAllocationWizard``).
    """

    class Meta:
        abstract = True
        managed = False

    # ---- Atributos de clase de modelo — verbatim (``:5-7``) ----
    _name = 'hr.bank.account.allocation.wizard.line'
    _description = 'Bank Account Allocation Line (Wizard)'
    _order = 'sequence, id'

    #: ≙ el ``default=10`` de ``sequence`` (``:17``).
    DEFAULT_SEQUENCE = 10

    @classmethod
    def _compute_symbol(cls, line, bank_account, employee=None):
        """El símbolo que acompaña al monto — ≙ ``_compute_symbol``
        (``:19-26``): el de la moneda de la cuenta (o el de la empresa del
        empleado) para montos fijos; ``%`` para porcentajes."""
        if line.get('amount_type') == 'fixed':
            if bank_account is not None and bank_account.currency_id:
                return bank_account.currency.symbol
            if (employee is not None and employee.company_id
                    and employee.company.currency_id):
                return employee.company.currency.symbol
            return ''
        return '%'

    @classmethod
    def _get_amount_type_selection_vals(cls):
        """≙ ``_get_amount_type_selection_vals`` (``:28-29``) — verbatim."""
        return [('percentage', 'Percentage'), ('fixed', 'Fixed')]
