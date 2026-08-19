"""``mail.activity.plan.template`` — responsables coach/gerente/empleado
(Odoo ``hr``).

Adaptación de Odoo hr/models/mail_activity_plan_template.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3, 108 líneas) — atribución y aviso de
licencia preservados (DEC-KX-03).

Porte PARCIAL DECLARADO — 2 de 4 símbolos; los otros 2 BLOQUEADOS
==================================================================

La clase destino ``mail.activity.plan.template`` **no existe** (mismo
ausente que ``mail_activity_plan.py`` de este pase — medido allá). Pero, a
diferencia de aquel archivo, DOS de los cuatro símbolos son pura lógica
sobre ``hr.employee`` (recorrer la cadena de gerentes buscando un usuario)
y se portan como funciones de módulo consultables hoy; el día que el
template exista, se cuelgan con ``extend_model``.

===========================================================  ================
Símbolo de la referencia (línea)                             Estado
===========================================================  ================
``responsible_type`` (``selection_add``, ``:11-15``)         bloqueado — no
                                                             hay Selection
                                                             que extender
``_check_responsible_hr`` (``:17-24``)                       bloqueado —
                                                             valida
                                                             ``plan_id.res_model``
                                                             del modelo
                                                             ausente
``_get_closest_parent_user`` (``:26-54``)                    **portado** —
                                                             función de
                                                             módulo, nombre
                                                             verbatim
``_determine_responsible`` (``:56-108``)                     **portado** —
                                                             función de
                                                             módulo, nombre
                                                             verbatim
===========================================================  ================

Divergencias declaradas
========================

1. **``self.env.user`` → argumento ``current_user``** — el usuario que cae
   como responsable de último recurso se recibe explícito (no hay entorno).
2. **``self`` (el template) → argumentos ``responsible_type`` y
   ``employee``** — las dos funciones no leen nada más del template; cuando
   la clase exista, el método adaptador es una línea.
3. **La rama ``super()._determine_responsible`` devuelve ``None``** — es el
   relevo de ``chain_method`` hacia la implementación base del template
   ausente; quien llame hoy con un ``responsible_type`` ajeno a RR.HH.
   recibe ``None`` y decide.
4. **El "cae sin retorno" de la referencia se conserva** — la referencia
   termina con ``if result['error'] or result['responsible']: return
   result`` y **sin** ``else``: con empleado ligado a usuario pero sin
   error, devuelve el dict; sin ninguno de los dos, devuelve ``None``
   implícito. Se porta verbatim (reproducir la forma, no "corregirla").

Sucesor: el porte de ``mail.activity.plan.template`` a ``addons/mail``
(mismo DESCONOCIDO con condición de cierre que ``mail_activity_plan.py``).
"""
from tools.translate import _


def _get_closest_parent_user(employee, responsible, error_message, current_user=None):
    """El primer ancestro de ``responsible`` ligado a un usuario — ≙
    ``_get_closest_parent_user``
    (``odoo19c: hr/models/mail_activity_plan_template.py:26-54``).

    Sube por la cadena de gerentes hasta hallar uno con usuario; si la
    cadena se agota, cae a ``current_user`` con la advertencia
    ``error_message``; si detecta un ciclo sin usuario, devuelve el error de
    estructura de equipo.
    """
    responsible_parent = responsible
    viewed_responsible = [employee]
    while True:
        if not responsible_parent:
            return {
                'error': False,
                'responsible': current_user,
                'warning': error_message,
            }
        if responsible_parent.user is not None:
            return {
                'error': False,
                'responsible': responsible_parent.user,
                'warning': False,
            }
        if responsible_parent in viewed_responsible:
            return {
                'error': _(
                    '¡Vaya! Parece que hay un problema con la estructura del '
                    'equipo. Encontramos un ciclo de reporte y nadie en ese '
                    'ciclo está ligado a un usuario. Verifica que cada quien '
                    'reporte al gerente correcto.'
                ),
                'warning': False,
                'responsible': False,
            }
        viewed_responsible.append(responsible_parent)
        responsible_parent = responsible_parent.parent


def _determine_responsible(responsible_type, employee, current_user=None):
    """El responsable de la actividad según ``responsible_type`` — ≙
    ``_determine_responsible``
    (``odoo19c: hr/models/mail_activity_plan_template.py:56-108``).

    Devuelve ``None`` para tipos ajenos a RR.HH. (el relevo al template
    base ausente — divergencia 3 del docstring).
    """
    if responsible_type not in {'coach', 'manager', 'employee'}:
        return None
    result = {'error': '', 'warning': '', 'responsible': False}
    if responsible_type == 'coach':
        if not employee.coach_id:
            result['error'] = _('El coach del empleado %s no está asignado.', employee.name)
        result['responsible'] = employee.coach.user if employee.coach_id else None
        if employee.coach_id and not result['responsible']:
            # Si el coach no está ligado a un usuario, se intenta con el
            # gerente del coach, subiendo hasta hallar uno con usuario; si
            # nadie aparece, cae al usuario actual.
            result = _get_closest_parent_user(
                employee=employee,
                responsible=employee.coach.parent,
                error_message=_(
                    'El usuario del coach de %s no está asignado.', employee.name,
                ),
                current_user=current_user,
            )
    elif responsible_type == 'manager':
        if not employee.parent_id:
            result['error'] = _('El gerente del empleado %s no está asignado.', employee.name)
        result['responsible'] = employee.parent.user if employee.parent_id else None
        if employee.parent_id and not result['responsible']:
            result = _get_closest_parent_user(
                employee=employee,
                responsible=employee.parent.parent,
                error_message=_(
                    'El gerente de %s debería estar ligado a un usuario.', employee.name,
                ),
                current_user=current_user,
            )
    elif responsible_type == 'employee':
        result['responsible'] = employee.user
        if not result['responsible']:
            result = _get_closest_parent_user(
                employee=employee,
                responsible=employee.parent,
                error_message=_(
                    'El empleado %s debería estar ligado a un usuario.', employee.name,
                ),
                current_user=current_user,
            )

    if result['error'] or result['responsible']:
        return result
    # Verbatim de la referencia: sin error y sin responsable, ``None``
    # implícito (ver divergencia 4 del docstring).


def apply_hr_mail_activity_plan_template_extensions():
    """No-op declarado — el template destino no existe (ver docstring)."""
    return None
