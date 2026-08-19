"""Extensión de ``ir.ui.menu`` — menús vetados según el rol de RR.HH.

Adaptación de Odoo hr/models/ir_ui_menu.py (odoo-tools@622ddc2a, odoo19c:,
LGPL-3, 19 líneas) — atribución y aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 1 de 1
===================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
     - Forma aquí
   * - ``_load_menus_blacklist`` (``:9-19``)
     - portado (una rama BLOQUEADA, ver abajo)
     - ``extend_model('base', 'IrUiMenu', metodos=…)``; nombre **verbatim**,
       instalado como ``classmethod``

``_inherit`` lo expresa ``extend_model``; par de Django porque
``base.IrUiMenu`` no declara ``_name``.

Divergencias y bloqueos declarados
===================================

1. **``self.env.user`` → argumento ``user`` explícito** — este ORM no tiene
   entorno; mismo criterio que ``hr_employee.py::_get_first_versions``
   (contexto → argumento).
2. **``env.ref('hr.menu_hr_employee')`` → búsqueda por ``key``** — el campo
   ``key`` de ``base.IrUiMenu`` "cumple el papel del xmlid de Odoo" (su
   propio ``help_text``); ``raise_if_not_found=False`` ≙ ``.first()``.
3. **``has_group('hr.group_hr_user')``** — ``base.ResUsers.has_group``
   existe (``src/addons/base/models/res_users.py:518``) y resuelve contra
   ``authz``; el external id de la referencia se pasa verbatim. Que el grupo
   ``hr.group_hr_user`` exista como fila sembrada es data, no esquema — sin
   la fila, ``has_group`` devuelve ``False`` y la rama simplemente no
   aplica.
4. **BLOQUEADO — la rama del gerente de departamento.** La referencia
   pregunta si el usuario es gerente (``hr.department.manager_id``);
   ``hr.HrDepartment`` de este árbol tiene ese campo **DEFERIDO** (su
   propio docstring: "manager / member_ids — requieren hr.employee"; el
   empleado ya existe pero la columna sigue sin declararse). Efecto: nadie
   es gerente, así que el menú kanban de departamentos se veta siempre que
   el usuario no sea de RR.HH. — el mismo resultado que daría la referencia
   con cero gerentes. Sucesor: la migración aditiva de
   ``HrDepartment.manager`` (tarea **#524**, reconexión hr ↔ hr.employee).
5. **Sin consumidor cableado (declarado, no omitido).**
   ``CapabilityPrunedMenuManager.load_menus`` no consulta ninguna
   blacklist — mismo estado que ``web/models/ir_ui_menu.py::load_web_menus``
   ("no es el consumidor actual, y se declara por qué"): el método queda
   disponible para cuando el podado por rol se cablee en el manager; cablear
   ese consumo cambia el contrato del endpoint de menú y se decide aparte.
"""
from orm.model_classes import extend_model


def _load_menus_blacklist(cls, user):
    """Ids de menú vetados para ``user`` — ≙ ``_load_menus_blacklist``
    (``odoo19c: hr/models/ir_ui_menu.py:9-19``).

    Un usuario de RR.HH. no ve el menú simplificado de empleados; un usuario
    que no es gerente de ningún departamento no ve el kanban de
    departamentos.
    """
    result = []
    if user is not None and user.has_group('hr.group_hr_user'):
        emp_menu = cls.objects.filter(key='hr.menu_hr_employee').first()
        if emp_menu is not None:
            result.append(emp_menu.pk)
    else:
        # BLOQUEADO por ``hr.HrDepartment.manager`` (columna deferida):
        # sin ella nadie es gerente, así que ``is_department_manager`` es
        # ``False`` por vacuidad — ver la divergencia 4 del docstring.
        is_department_manager = False
        if not is_department_manager:
            dep_menu = cls.objects.filter(
                key='hr.menu_hr_department_kanban',
            ).first()
            if dep_menu is not None:
                result.append(dep_menu.pk)
    return result


def apply_hr_ir_ui_menu_extensions():
    """Cuelga sobre ``ir.ui.menu`` lo que ``hr`` le añade — ≙ ``_inherit``."""
    extend_model('base', 'IrUiMenu', metodos={
        '_load_menus_blacklist': classmethod(_load_menus_blacklist),
    })
