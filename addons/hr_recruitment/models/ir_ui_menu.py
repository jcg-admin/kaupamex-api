"""``ir.ui.menu`` — menús vetados según el rol de reclutamiento (Odoo
``hr_recruitment``).

Adaptación de Odoo ``hr_recruitment/models/ir_ui_menu.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 22 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03). Porte completo (formal) — 1 de 1
símbolo, con la mitad de dato BLOQUEADA (ver divergencia 2).

``_inherit`` lo expresa ``extend_model``; par de Django porque
``base.IrUiMenu`` no declara ``_name`` — mismo patrón que
``hr/models/ir_ui_menu.py``.

Divergencias declaradas
==========================

1. **``self.env.user`` → argumento ``user`` explícito** — mismo criterio
   que ``hr/models/ir_ui_menu.py::_load_menus_blacklist``.
2. **``env.ref('hr_recruitment.menu_hr_job_position')``/
   ``…menu_hr_job_position_interviewer`` → búsqueda por ``key``** — el
   campo ``key`` de ``base.IrUiMenu`` cumple el papel del xmlid. Sin las
   filas sembradas (data, no esquema), la rama simplemente no aplica.
"""
from orm.method_chain import chain_method, extend_list
from orm.model_classes import extend_model


def _load_menus_blacklist(cls, user):
    """≙ ``_load_menus_blacklist`` (``odoo19c: hr_recruitment/models/
    ir_ui_menu.py:9-19``) — encadena sobre el veto de ``hr`` (menú de
    empleados) con el propio de reclutamiento."""
    result = []
    is_interviewer = user is not None and user.has_group(
        'hr_recruitment.group_hr_recruitment_interviewer',
    )
    if not is_interviewer:
        job_menu = cls.objects.filter(key='hr.menu_view_hr_job').first()
        if job_menu is not None:
            result.append(job_menu.pk)
    elif not user.has_group('hr_recruitment.group_hr_recruitment_user'):
        pos_menu = cls.objects.filter(key='hr_recruitment.menu_hr_job_position').first()
        if pos_menu is not None:
            result.append(pos_menu.pk)
    else:
        int_menu = cls.objects.filter(
            key='hr_recruitment.menu_hr_job_position_interviewer',
        ).first()
        if int_menu is not None:
            result.append(int_menu.pk)
    return result


def _wire(model):
    """≙ ``res = super()._load_menus_blacklist(); res.append(...)`` — la
    referencia SIEMPRE combina (nunca releva); ``extend_model.metodos`` usa
    relevo por defecto, así que aquí se llama a ``chain_method`` directo
    con ``combine=extend_list`` desde ``luego=``."""
    chain_method(
        model, '_load_menus_blacklist',
        classmethod(_load_menus_blacklist), combine=extend_list,
    )


def apply_hr_recruitment_ir_ui_menu_extensions():
    """Cuelga sobre ``ir.ui.menu`` lo que ``hr_recruitment`` le añade — ≙
    ``_inherit``. Combina (no releva) con el veto de ``hr`` ya instalado:
    ambos vetos se suman, igual que la fuente."""
    extend_model('base', 'IrUiMenu', luego=_wire)
