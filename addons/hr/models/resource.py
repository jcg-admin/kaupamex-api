"""Extensión de ``resource.resource`` — el recurso que es un empleado
(Odoo ``hr``).

Adaptación de Odoo hr/models/resource.py (odoo-tools@622ddc2a, odoo19c:,
LGPL-3, 137 líneas) — atribución y aviso de licencia preservados
(DEC-KX-03).

Porte símbolo por símbolo — 19 símbolos: 12 portados/resueltos, 3 sin
código necesario, 4 BLOQUEADOS
======================================================================

Campos (10):

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``user_id = fields.Many2one(copy=False)`` (``:15``)
     - DIVERGENCIA — sólo cambia el atributo ``copy`` del campo existente;
       este árbol no tiene ``copy()`` genérico de registros (medido ya en
       ``account_debit_note``), así que no hay atributo que apagar
   * - ``employee_id`` (One2many, ``:16``)
     - sin código — es el reverso real del mixin:
       ``resource.hr_hremployee_resource_mixin_set`` (el ``related_name``
       que Django genera para ``ResourceMixin.resource`` en ``hr.employee``)
   * - ``job_title`` (compute, ``:18``)
     - propiedad; cómputo verbatim ``_compute_job_title``
   * - ``department_id`` (compute, ``:19``)
     - propiedad ``department``; cómputo verbatim ``_compute_department_id``
   * - ``work_location_id`` (related, ``:20``)
     - propiedad ``work_location``
   * - ``work_email`` / ``work_phone`` (related, ``:21-22``)
     - propiedades
   * - ``show_hr_icon_display`` / ``hr_icon_display`` (related, ``:23-24``)
     - propiedades (delegan a los campos del empleado, que a su vez están
       BLOQUEADOS por la infraestructura de presencia — ver
       ``hr_employee.py``, sucesor #21; aquí sólo se delega)
   * - ``calendar_id = fields.Many2one(inverse=…)`` (``:25``)
     - el inverse se porta como método ``_inverse_calendar_id``; el campo
       ``calendar`` ya existe en ``resource.ResourceResource``

Métodos (9):

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``_compute_job_title`` (``:27-30``)
     - portado
   * - ``_compute_department_id`` (``:32-35``)
     - portado
   * - ``_compute_avatar_128`` (``:37-52``)
     - portado con DIVERGENCIA — devuelve el avatar del empleado vía su
       ``AvatarMixin``; la rama ``hr.employee.public`` (avatar público para
       no-RR.HH.) queda BLOQUEADA por la vista SQL de
       ``hr_employee_public.py`` (ver su docstring). Además, NO sustituye a
       la propiedad ``avatar_128`` existente del recurso:
       ``extend_model(propiedades=…)`` no pisa una existente por diseño —
       el método queda disponible con su nombre verbatim
   * - ``_inverse_calendar_id`` (``:54-57``)
     - portado
   * - ``_get_resource_without_contract`` (``:59-73``)
     - portado — el ``_read_group`` se traduce a un ``values_list`` con
       ``distinct``
   * - ``_get_contracts_valid_periods`` (``:75-88``)
     - BLOQUEADO por ``tools.intervals.Intervals`` — el motor de intervalos
       no está portado (medido: 0 hits de ``class Intervals`` en ``src/`` y
       ``addons/``). Sucesor: tarea **#514** (el mismo que bloquea
       ``_get_unusual_days`` y familia en ``hr_employee.py``)
   * - ``_get_calendars_validity_within_period`` (``:90-106``)
     - BLOQUEADO por #514 — además su ``super()`` (la implementación base
       en ``resource.resource``) tampoco existe en este árbol
   * - ``_get_flexible_resources_calendars_validity_within_period``
       (``:108-125``)
     - BLOQUEADO por #514 + ``_get_flexible_resources_default_work_intervals``
       ausente en la base
   * - ``_get_calendar_at`` (``:127-133``)
     - BLOQUEADO por ``hr.employee._get_calendars`` (familia bloqueada en
       ``hr_employee.py``, sucesor #514); la base de este árbol expone
       ``calendar_at`` (sin prefijo) que sigue siendo el camino vivo

``_inherit`` lo expresa ``extend_model``; par de Django porque el destino no
declara ``_name``.
"""
from addons.hr.models.hr_version import HrVersion
from orm.model_classes import extend_model


def _first_employee(resource):
    """El empleado del recurso, o ``None`` — helper propio del puerto (la
    referencia usa el One2many ``employee_id`` como si fuera único, que es
    exactamente lo que este helper hace explícito)."""
    return resource.hr_hremployee_resource_mixin_set.first()


def _compute_job_title(self):
    """≙ ``_compute_job_title`` (``:27-30``)."""
    employee = _first_employee(self)
    return employee.job_title if employee is not None else ''


def job_title(self):
    """≙ ``job_title``."""
    return self._compute_job_title()


def _compute_department_id(self):
    """≙ ``_compute_department_id`` (``:32-35``)."""
    employee = _first_employee(self)
    return employee.department if employee is not None else None


def department(self):
    """≙ ``department_id``."""
    return self._compute_department_id()


def work_location(self):
    """≙ ``work_location_id`` (``related='employee_id.work_location_id'``)."""
    employee = _first_employee(self)
    return employee.work_location if employee is not None else None


def work_email(self):
    """≙ ``work_email``."""
    employee = _first_employee(self)
    return employee.work_email if employee is not None else ''


def work_phone(self):
    """≙ ``work_phone``."""
    employee = _first_employee(self)
    return employee.work_phone if employee is not None else ''


def show_hr_icon_display(self):
    """≙ ``show_hr_icon_display``."""
    employee = _first_employee(self)
    return bool(employee and employee.show_hr_icon_display)


def hr_icon_display(self):
    """≙ ``hr_icon_display``."""
    employee = _first_employee(self)
    return employee.hr_icon_display if employee is not None else ''


def _compute_avatar_128(self):
    """≙ ``_compute_avatar_128`` (``:37-52``) — el avatar del recurso es el
    de su empleado; sin empleado, ``False`` (ver DIVERGENCIA en la tabla del
    docstring: la rama pública para no-RR.HH. está bloqueada)."""
    employee = _first_employee(self)
    if employee is None:
        return False
    return employee.avatar_128


def _inverse_calendar_id(self):
    """≙ ``_inverse_calendar_id`` (``:54-57``) — escribir el calendario del
    recurso lo propaga al calendario del empleado."""
    employee = _first_employee(self)
    if employee is not None and employee.resource_calendar_id != self.calendar_id:
        employee.resource_calendar = self.calendar
        employee.save(update_fields=['resource_calendar'])


def _get_resource_without_contract(cls, resources):
    """Los recursos cuyo empleado nunca ha tenido contrato — ≙
    ``_get_resource_without_contract`` (``:59-73``).

    DIVERGENCIA: ``self`` (recordset) → ``classmethod`` que recibe
    ``resources``, mismo patrón que ``_get_tz_batch`` en
    ``hr_employee.py``.
    """
    employee_by_resource = {
        resource.pk: _first_employee(resource) for resource in resources
    }
    employee_ids = [
        employee.pk for employee in employee_by_resource.values()
        if employee is not None
    ]
    with_contract = set(
        HrVersion.objects.filter(
            employee_id__in=employee_ids,
            contract_date_start__isnull=False,
        ).values_list('employee_id', flat=True).distinct(),
    )
    return [
        resource for resource in resources
        if employee_by_resource[resource.pk] is None
        or employee_by_resource[resource.pk].pk not in with_contract
    ]


def apply_hr_resource_extensions():
    """Cuelga sobre ``resource.resource`` lo que ``hr`` le añade — ≙
    ``_inherit``."""
    extend_model(
        'resource', 'ResourceResource',
        metodos={
            '_compute_job_title': _compute_job_title,
            '_compute_department_id': _compute_department_id,
            '_compute_avatar_128': _compute_avatar_128,
            '_inverse_calendar_id': _inverse_calendar_id,
            '_get_resource_without_contract': classmethod(_get_resource_without_contract),
        },
        propiedades={
            'job_title': job_title,
            'department': department,
            'work_location': work_location,
            'work_email': work_email,
            'work_phone': work_phone,
            'show_hr_icon_display': show_hr_icon_display,
            'hr_icon_display': hr_icon_display,
        },
    )
