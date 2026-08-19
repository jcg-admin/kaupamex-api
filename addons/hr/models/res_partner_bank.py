"""Extensión de ``res.partner.bank`` — la cuenta bancaria del empleado
(Odoo ``hr``).

Adaptación de Odoo hr/models/res_partner_bank.py (odoo-tools@622ddc2a,
odoo19c:, LGPL-3, 58 líneas) — atribución y aviso de licencia preservados
(DEC-KX-03).

Porte símbolo por símbolo — 17 símbolos: 15 portados, 2 BLOQUEADOS
===================================================================

Campos (12) — todos ``related``/``compute`` sin ``store``: propiedades de
sólo lectura, mismo criterio que las delegaciones de ``hr_employee.py``.

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Forma aquí
   * - ``bank_street``/``bank_street2``/``bank_zip``/``bank_city``/
       ``bank_state``/``bank_country``/``bank_email``/``bank_phone``
       (``related='bank_id.*'``, ``:9-16``)
     - propiedades sobre ``self.bank`` — DIVERGENCIA: ``readonly=False`` de
       la referencia (escribir a través del related) no aplica; quien
       edite escribe en ``self.bank`` directamente
   * - ``employee_id`` (compute, ``:17``)
     - propiedad ``employee`` (la FK delegada pierde el sufijo ``_id``,
       mismo criterio que ``user``/``department`` en ``hr_employee.py``);
       el cómputo verbatim es ``_compute_employee_id``
   * - ``employee_salary_amount`` /
       ``employee_salary_amount_is_percentage`` (``:18-19``)
     - propiedades; el cómputo verbatim es ``_compute_salary_amount``
   * - ``currency_symbol`` (``related='currency_id.symbol'``, ``:20``)
     - propiedad sobre ``self.currency``
   * - ``employee_has_multiple_bank_accounts`` (``:21``)
     - propiedad que delega en ``employee.has_multiple_bank_accounts``

Métodos (5):

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``_compute_salary_amount`` (``:23-33``)
     - portado — devuelve ``(monto, es_porcentaje)`` en vez de asignar dos
       pseudo-campos (aquí son propiedades que lo consumen)
   * - ``_search_employee_id`` (``:35-37``)
     - portado — DIVERGENCIA: el dominio Odoo se traduce a un queryset de
       cuentas; recibe los ids de empleado ya resueltos (``operator`` de
       dominio → filtro directo del ORM)
   * - ``action_open_allocation_wizard`` (``:39-41``)
     - BLOQUEADO — delega en
       ``hr.employee.action_open_allocation_wizard``, familia (b) de
       ``hr_employee.py`` (acciones de cliente Odoo); el trabajo real del
       wizard sí está portado en ``wizard/hr_bank_account_wizard.py``
   * - ``_compute_employee_id`` (``:43-49``)
     - portado
   * - ``_compute_display_name`` (``:51-58``)
     - BLOQUEADO a medias — el enmascarado del número de cuenta se porta
       como ``_masked_acc_number()``; el override del ``display_name`` del
       recordset (``sudo(self.env.su)``, resta de recordsets) es mecánica
       del ORM de Odoo sin análogo; el consumidor DRF decide cuándo
       enmascarar pasando el usuario

``_inherit`` lo expresa ``extend_model``; par de Django porque el destino no
declara ``_name``.
"""
from orm.environments import get_current_companies
from orm.model_classes import extend_model


def bank_street(self):
    """≙ ``bank_street`` (``related='bank_id.street'``)."""
    return self.bank.street if self.bank_id else ''


def bank_street2(self):
    """≙ ``bank_street2``."""
    return self.bank.street2 if self.bank_id else ''


def bank_zip(self):
    """≙ ``bank_zip``."""
    return self.bank.zip if self.bank_id else ''


def bank_city(self):
    """≙ ``bank_city``."""
    return self.bank.city if self.bank_id else ''


def bank_state(self):
    """≙ ``bank_state`` (``related='bank_id.state'``)."""
    return self.bank.state if self.bank_id else None


def bank_country(self):
    """≙ ``bank_country`` (``related='bank_id.country'``)."""
    return self.bank.country if self.bank_id else None


def bank_email(self):
    """≙ ``bank_email``."""
    return self.bank.email if self.bank_id else ''


def bank_phone(self):
    """≙ ``bank_phone``."""
    return self.bank.phone if self.bank_id else ''


def currency_symbol(self):
    """≙ ``currency_symbol`` (``related='currency_id.symbol'``)."""
    return self.currency.symbol if self.currency_id else ''


def _compute_employee_id(self):
    """El empleado dueño de la cuenta — ≙ ``_compute_employee_id``
    (``:43-49``): el primer empleado del partner dentro de las empresas
    activas, o ``None`` si el partner no es empleado."""
    if not self.partner_id or not self.partner.employee:
        return None
    employees = self.partner.employee_work_contacts.all()
    company_ids = get_current_companies()
    if company_ids:
        employees = employees.filter(company_id__in=company_ids)
    return employees.first()


def employee(self):
    """≙ ``employee_id`` — la propiedad que expone el cómputo."""
    return self._compute_employee_id()


def _compute_salary_amount(self):
    """≙ ``_compute_salary_amount`` (``:23-33``) — devuelve la tupla
    ``(monto, es_porcentaje)`` de la asignación de nómina de esta cuenta.

    Nota de forma: la rama ``get_remaining_percentage`` de la referencia
    (``:31``) sólo se alcanza si ``employee_id`` es falsy **y**
    ``employee_id.salary_distribution`` es truthy — imposible sobre un
    recordset vacío, así que es código muerto allá y no se reproduce aquí
    (mismo criterio que la condición muerta de ``copy_lines`` documentada
    en ``account_debit_note``).
    """
    owner = self.employee
    if owner is not None and owner.salary_distribution:
        return owner.get_bank_account_salary_allocation(self.pk)
    return 0, True


def employee_salary_amount(self):
    """≙ ``employee_salary_amount``."""
    return self._compute_salary_amount()[0]


def employee_salary_amount_is_percentage(self):
    """≙ ``employee_salary_amount_is_percentage``."""
    return self._compute_salary_amount()[1]


def employee_has_multiple_bank_accounts(self):
    """≙ ``employee_has_multiple_bank_accounts``
    (``related='employee_id.has_multiple_bank_accounts'``)."""
    owner = self.employee
    return bool(owner and owner.has_multiple_bank_accounts)


def _search_employee_id(cls, employee_ids):
    """Cuentas de los empleados dados — ≙ ``_search_employee_id``
    (``:35-37``). DIVERGENCIA: recibe ids de empleado y devuelve el
    queryset de cuentas (el dominio Odoo se traduce a ORM directo)."""
    return cls.objects.filter(hr_employees__pk__in=list(employee_ids)).distinct()


def _masked_acc_number(self):
    """El número de cuenta enmascarado — la mitad portable de
    ``_compute_display_name`` (``:51-58``): primeros 2 y últimos 4
    visibles, el resto en asteriscos."""
    acc_number = self.acc_number or ''
    if len(acc_number) <= 6:
        return acc_number
    return acc_number[:2] + '*' * len(acc_number[2:-4]) + acc_number[-4:]


def _compute_display_name(self, user=None):
    """≙ ``_compute_display_name`` (``:51-58``) — el nombre visible de la
    cuenta: enmascarado cuando el partner es empleado y ``user`` no es de
    RR.HH.

    DIVERGENCIA: ``self.env.user`` → argumento ``user``; sin usuario se
    enmascara (fail-closed, al revés que un ``sudo``).
    """
    is_hr = bool(user is not None and user.has_group('hr.group_hr_user'))
    if not is_hr and self.partner_id and self.partner.employee_work_contacts.exists():
        return self._masked_acc_number()
    return str(self)


def apply_hr_res_partner_bank_extensions():
    """Cuelga sobre ``res.partner.bank`` lo que ``hr`` le añade — ≙
    ``_inherit``."""
    extend_model(
        'base', 'ResPartnerBank',
        metodos={
            '_compute_employee_id': _compute_employee_id,
            '_compute_salary_amount': _compute_salary_amount,
            '_search_employee_id': classmethod(_search_employee_id),
            '_masked_acc_number': _masked_acc_number,
            '_compute_display_name': _compute_display_name,
        },
        propiedades={
            'bank_street': bank_street,
            'bank_street2': bank_street2,
            'bank_zip': bank_zip,
            'bank_city': bank_city,
            'bank_state': bank_state,
            'bank_country': bank_country,
            'bank_email': bank_email,
            'bank_phone': bank_phone,
            'currency_symbol': currency_symbol,
            'employee': employee,
            'employee_salary_amount': employee_salary_amount,
            'employee_salary_amount_is_percentage': employee_salary_amount_is_percentage,
            'employee_has_multiple_bank_accounts': employee_has_multiple_bank_accounts,
        },
    )
