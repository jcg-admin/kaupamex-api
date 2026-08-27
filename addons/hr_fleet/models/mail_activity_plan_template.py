"""``mail.activity.plan.template`` — el gestor de flota como responsable.

Adaptación de Odoo hr_fleet/models/mail_activity_plan_template.py
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 37 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte PARCIAL DECLARADO — 1 de 3 símbolos; los otros 2 BLOQUEADOS
==================================================================

La clase destino ``mail.activity.plan.template`` **no existe** en este
árbol — es el MISMO ausente que ``hr/models/mail_activity_plan_template.py``
ya midió y declaró (su porte de la rama coach/manager/employee sigue este
mismo patrón: funciones de módulo consultables hoy, colgadas con
``extend_model`` el día que el template exista).

===========================================================  ================
Símbolo de la referencia (línea)                             Estado
===========================================================  ================
``responsible_type`` (``selection_add``, ``:11-13``)         BLOQUEADO — no
                                                             hay Selection
                                                             que extender
``_check_responsible_hr_fleet`` (``:15-20``)                 BLOQUEADO —
                                                             valida
                                                             ``plan_id.res_model``
                                                             del modelo
                                                             ausente
``_determine_responsible`` (``:22-37``)                      **portado** —
                                                             función de
                                                             módulo, nombre
                                                             verbatim
===========================================================  ================

Divergencias declaradas (las mismas 1-3 del precedente de ``hr``)
==================================================================

1. **``self.env.user`` → argumento ``current_user``** — el usuario que cae
   como responsable cuando el vehículo no tiene gestor se recibe explícito.
2. **``self`` (el template) → argumento ``responsible_type``** — la función
   no lee nada más del template; cuando la clase exista, el método
   adaptador es una línea. El guard ``plan_id.res_model == 'hr.employee'``
   pertenece a esa futura adaptación (aquí el empleado YA llega tipado).
3. **La rama ``super()._determine_responsible`` devuelve ``None``** — el
   relevo hacia el template base ausente; con un ``responsible_type`` ajeno
   a flota, quien llame recibe ``None`` y decide.
4. **``employee._origin.id`` → ``employee``** — ``_origin`` es mecánica de
   formulario (registro virtual del cliente); aquí el empleado llega real.

Sucesor: el mismo del precedente de ``hr`` — el porte de
``mail.activity.plan.template`` a ``addons/mail`` (DESCONOCIDO con esa
condición de cierre).
"""
from tools.translate import _


def _determine_responsible(responsible_type, employee, current_user=None):
    """El responsable de la actividad para planes de flota — ≙
    ``_determine_responsible``
    (``odoo19c: hr_fleet/models/mail_activity_plan_template.py:22-37``).

    Devuelve ``None`` para tipos ajenos a flota (divergencia 3). Con
    ``'fleet_manager'``: el gestor del primer vehículo del empleado; sin
    vehículo → error; con vehículo sin gestor → advertencia y cae a
    ``current_user``.
    """
    if responsible_type != 'fleet_manager':
        return None
    vehicle = employee.car_ids.first()
    error = False
    warning = False
    if not vehicle:
        error = _('Employee %s is not linked to a vehicle.', employee.name)
    if vehicle and not vehicle.manager_id:
        warning = _(
            'The vehicle of employee %(employee)s is not linked to a fleet '
            'manager, assigning to you.', employee=employee.name,
        )
    return {
        'responsible': (vehicle.manager if vehicle and vehicle.manager_id
                        else current_user),
        'error': error,
        'warning': warning,
    }


def apply_hr_fleet_mail_activity_plan_template_extensions():
    """No-op declarado — el template destino no existe (ver docstring;
    mismo patrón que ``apply_hr_mail_activity_plan_template_extensions``
    de ``hr``)."""
    return None
