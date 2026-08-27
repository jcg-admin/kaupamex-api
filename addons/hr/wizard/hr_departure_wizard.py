"""``hr.departure.wizard`` — registrar la baja de uno o más empleados.

Adaptación de Odoo hr/wizard/hr_departure_wizard.py (odoo-tools@622ddc2a,
odoo19c:, LGPL-3, 133 líneas) — atribución y aviso de licencia preservados
(DEC-KX-03).

``TransientModel`` → clase sin tabla con classmethods (patrón
``account_debit_note``): el estado del wizard (empleados, razón, fecha,
banderas) lo pasa el llamador como argumentos.

Porte símbolo por símbolo — 12 símbolos
========================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``_name`` / ``_description`` (``:8-9``)
     - portados verbatim
   * - ``_get_default_departure_date`` (``:11-18``)
     - portado — recibe los empleados activos como argumento (el
       ``context['active_ids']`` era mecánica del cliente)
   * - ``_get_default_employee_ids`` (``:20-24``)
     - portado — ídem
   * - ``_get_domain_employee_ids`` (``:26-27``)
     - portado — devuelve el queryset (dominio → ORM)
   * - ``departure_reason_id`` (``:29-31``)
     - resuelto con otra forma — argumento ``departure_reason``; su default
       (la primera razón del catálogo) es ``_default_departure_reason``
   * - ``departure_description`` (``:32``) / ``departure_date`` (``:33``) /
       ``employee_ids`` (``:34-39``) / ``remove_related_user`` (``:45-48``)
       / ``set_date_end`` (``:50-51``)
     - resueltos con otra forma — argumentos de
       ``action_register_departure``
   * - ``is_user_employee`` (``:41-44``) / ``_compute_is_user_employee``
       (``:53-59``)
     - portados — ``_compute_is_user_employee(employees)``
   * - ``action_register_departure`` (``:61-133``)
     - portado — ver divergencias

Divergencias declaradas
========================

1. **``action_archive`` → ``active = False`` + ``save()``** — el
   ``action_archive`` de la referencia es de la familia (b) de
   ``hr_employee.py`` (acciones de cliente); el efecto de negocio es el
   booleano. El ``with_context(no_wizard=True)`` era para no re-abrir este
   mismo wizard desde la acción — sin acción, no aplica.
2. **El archivado del usuario** usa la columna ``active`` de
   ``base.ResUsers`` (``deactivate(reason)`` existe pero registra causas de
   cuenta, no bajas de RR.HH.; se usa la forma neutra).
3. **Las notificaciones de cierre** (``ir.actions.client`` +
   ``display_notification``) son UI del cliente Odoo — familia (b); el
   método devuelve el resumen ``{'archived_users': […],
   'unarchived_users': […]}`` para que la capa DRF componga su respuesta.
4. **``set_date_end`` default** — la referencia lo inicializa con
   ``has_group('hr.group_hr_user')``; aquí es un argumento con default
   ``True`` y el llamador que conozca al usuario puede pasar
   ``user.has_group('hr.group_hr_user')``.
5. **Los campos de baja viven en la versión** (``hr.version``): la
   referencia escribe en el empleado vía la delegación ``_inherits``.
"""
from datetime import date

from addons.hr.models.hr_departure_reason import HrDepartureReason
from addons.hr.models.hr_employee import HrEmployee
from addons.hr.models.hr_version import HrVersion
from exceptions import UserError
from orm.environments import get_current_companies
from orm.models_transient import TransientModel
from tools.translate import _


class HrDepartureWizard(TransientModel):
    """El asistente de baja — ≙ ``hr.departure.wizard``."""

    class Meta:
        abstract = True
        managed = False

    # ---- Atributos de clase de modelo — verbatim (``:8-9``) ----
    _name = 'hr.departure.wizard'
    _description = 'Departure Wizard'

    @classmethod
    def _get_default_departure_date(cls, employees):
        """≙ ``_get_default_departure_date`` (``:11-18``) — la fecha de baja
        del único empleado seleccionado, u hoy."""
        departure_date = None
        employees = list(employees)
        if len(employees) == 1:
            departure_date = employees[0]._get_departure_date()
        return departure_date or date.today()

    @classmethod
    def _get_default_employee_ids(cls, employees):
        """≙ ``_get_default_employee_ids`` (``:20-24``) — la selección
        acotada a las empresas activas."""
        company_ids = get_current_companies()
        if not company_ids:
            return list(employees)
        return [employee for employee in employees
                if employee.company_id in company_ids]

    @classmethod
    def _get_domain_employee_ids(cls):
        """≙ ``_get_domain_employee_ids`` (``:26-27``) — los empleados
        elegibles, como queryset."""
        queryset = HrEmployee.objects.filter(active=True)
        company_ids = get_current_companies()
        if company_ids:
            queryset = queryset.filter(company_id__in=company_ids)
        return queryset

    @classmethod
    def _default_departure_reason(cls):
        """El default de ``departure_reason_id`` (``:30``) — la primera
        razón del catálogo."""
        return HrDepartureReason.objects.first()

    @classmethod
    def _compute_is_user_employee(cls, employees):
        """≙ ``_compute_is_user_employee`` (``:53-59``) — ¿algún empleado de
        la selección tiene usuario vinculado?"""
        return any(employee.user is not None for employee in employees)

    @classmethod
    def action_register_departure(cls, employees, departure_reason,
                                  departure_date, departure_description='',
                                  remove_related_user=False,
                                  set_date_end=True,
                                  employee_termination=False):
        """Registra la baja — ≙ ``action_register_departure`` (``:61-133``).

        Valida la fecha contra los contratos vigentes, archiva empleados (y
        opcionalmente sus usuarios, sólo cuando TODOS los empleados del
        usuario están en la selección), escribe los campos de baja en la
        versión vigente y, con ``set_date_end``, corta el contrato en la
        fecha de baja. Devuelve el resumen de usuarios archivados/no
        archivados (ver divergencia 3).
        """
        employees = list(employees)
        active_versions = [employee.version for employee in employees
                           if employee.version_id]

        if any(version.contract_date_start
               and version.contract_date_start > departure_date
               for version in active_versions):
            raise UserError(
                _('La fecha de baja no puede ser anterior al inicio del '
                  'contrato vigente.'),
            )

        allow_archived_users = []
        unarchived_users = []
        if remove_related_user:
            employees_by_user = {}
            for employee in employees:
                user = employee.user
                if user is None:
                    continue
                employees_by_user.setdefault(user.pk, (user, []))[1].append(employee)
            for user, selected in employees_by_user.values():
                total_linked = HrEmployee.objects.filter(
                    resource__user=user,
                ).count()
                if len(selected) == total_linked:
                    allow_archived_users.append(user)
                else:
                    unarchived_users.append(user)

        archived_employees = []
        archived_users = []
        allowed_user_pks = {user.pk for user in allow_archived_users}
        for employee in employees:
            if not employee.active:
                continue
            if employee_termination:
                archived_employees.append(employee)
                user = employee.user
                if (remove_related_user and user is not None
                        and user.pk in allowed_user_pks
                        and user not in archived_users):
                    archived_users.append(user)

        for employee in archived_employees:
            employee.active = False
            employee.save(update_fields=['active'])
        for user in archived_users:
            user.active = False
            user.save(update_fields=['active'])

        for employee in employees:
            version = employee.version if employee.version_id else None
            if version is None:
                continue
            version.departure_reason = departure_reason
            version.departure_description = departure_description or ''
            version.departure_date = departure_date
            version.save(update_fields=[
                'departure_reason', 'departure_description', 'departure_date',
            ])

        if set_date_end:
            # Corta el fin de contrato en TODAS las versiones del contrato
            # vigente (mismo criterio de sincronía que ``create_version``).
            contract_versions = [version for version in active_versions
                                 if version.contract_date_start]
            for version in contract_versions:
                HrVersion.objects.filter(
                    employee_id=version.employee_id,
                    contract_date_start=version.contract_date_start,
                ).update(contract_date_end=departure_date)

        return {
            'archived_users': [user.pk for user in archived_users],
            'unarchived_users': [user.pk for user in unarchived_users],
        }
