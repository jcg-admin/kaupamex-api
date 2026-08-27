"""``hr.manager.department.report`` — ¿este usuario puede ver a este
empleado como gerente?

Adaptación de Odoo hr/report/hr_manager_department_report.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3, 33 líneas) — atribución y aviso de
licencia preservados (DEC-KX-03).

En la referencia es un ``models.AbstractModel`` con ``_auto = False`` cuyo
único trabajo es responder, para las record rules, si el empleado de una
fila es el propio usuario o un subordinado (directo o transitivo) de algún
departamento que el usuario gerencia. Patrón de este árbol para
``AbstractModel`` sin tabla: clase plana con ``classmethod`` — el mismo que
``ReportBaseReportIrmodulereference`` y los ensambladores de
``account/report/account_invoice_report.py``.

Porte símbolo por símbolo — 7 símbolos: 5 portados, 2 a medias por bloqueo
===========================================================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``_name`` / ``_description`` / ``_auto`` (``:7-9``)
     - portados verbatim como atributos de clase
   * - ``employee_id`` (M2O, ``:11``)
     - resuelto con otra forma — sin tabla no hay columna; el empleado se
       recibe como argumento (mismo criterio que los campos de
       ``TransientModel`` en ``account_debit_note``)
   * - ``has_department_manager_access`` (``:12-13``)
     - resuelto con otra forma — el par search/compute de abajo
   * - ``_search_has_department_manager_access`` (``:15-22``)
     - portado con la rama de gerencia BLOQUEADA (ver abajo)
   * - ``_compute_has_department_manager_access`` (``:24-33``)
     - portado con la rama de gerencia BLOQUEADA (ver abajo)

Bloqueo declarado — la mitad de gerencia
=========================================

Ambos métodos buscan los departamentos cuyo ``manager_id`` es un empleado
del usuario. ``hr.HrDepartment`` de este árbol tiene ``manager`` DEFERIDO
(su propio docstring; misma pieza que bloquea la rama del kanban en
``models/ir_ui_menu.py`` de este pase). Sin la columna, la lista de
departamentos gerenciados es vacía por vacuidad y el acceso se reduce a
"el empleado es el propio usuario" — fail-closed, no fail-open. Sucesor: la
migración aditiva de ``HrDepartment.manager`` (tarea **#524**).

Divergencias declaradas
========================

1. **``self.env.user`` → argumento ``user``**; el dominio de la referencia
   se devuelve como queryset de ``hr.employee``.
2. **``child_of`` sobre departamentos** → ``parent_path`` (la ruta
   materializada de ``hr_department.py``), listo para cuando ``manager``
   exista.
"""
from django.db.models import Q

from addons.hr.models.hr_department import HrDepartment
from addons.hr.models.hr_employee import HrEmployee


class HrManagerDepartmentReport:
    """``hr.manager.department.report`` — sin tabla (``_auto = False``):
    responde por argumentos, no por filas."""

    # ---- Atributos de clase de modelo — verbatim (``:7-9``) ----
    _name = 'hr.manager.department.report'
    _description = 'Hr Manager Department Report'
    _auto = False

    @classmethod
    def _managed_department_ids(cls, user):
        """Los departamentos gerenciados por los empleados de ``user``.

        BLOQUEADO por ``hr.HrDepartment.manager`` (columna deferida): hoy
        devuelve la lista vacía — ver el docstring del módulo. Helper propio
        del puerto: la referencia inlinea esta búsqueda en ambos métodos.
        """
        del user  # la firma queda lista para cuando ``manager`` exista
        if not any(field.name == 'manager' for field in HrDepartment._meta.get_fields()):
            return []
        return []  # inalcanzable hoy; el cuerpo real llega con la columna

    @classmethod
    def _search_has_department_manager_access(cls, user):
        """Empleados visibles para ``user`` como gerente — ≙
        ``_search_has_department_manager_access`` (``:15-22``).

        DIVERGENCIA: devuelve el queryset de ``hr.employee`` (el dominio
        ``employee_id.user_id = uid OR employee_id.department_id child_of
        …`` traducido a ORM); el único operador soportado allá era ``in``.
        """
        own = Q(resource__user=user)
        department_ids = cls._managed_department_ids(user)
        if not department_ids:
            return HrEmployee.objects.filter(own)
        subtree = Q()
        for department in HrDepartment.objects.filter(pk__in=department_ids):
            subtree |= Q(
                version__department__parent_path__startswith=department.parent_path,
            )
        return HrEmployee.objects.filter(own | subtree)

    @classmethod
    def _compute_has_department_manager_access(cls, employee, user):
        """≙ ``_compute_has_department_manager_access`` (``:24-33``) —
        ``True`` si ``employee`` está entre los visibles para ``user``."""
        if employee is None or employee.pk is None:
            return False
        return cls._search_has_department_manager_access(user).filter(
            pk=employee.pk,
        ).exists()
