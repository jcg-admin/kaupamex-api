"""``hr.employee`` — la compañía por defecto al mapear un empleado a un
proyecto (Odoo ``sale_timesheet``).

Adaptación de Odoo ``sale_timesheet/models/hr_employee.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 15 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Medido por AST sobre la referencia: 1 clase (``HrEmployee``, ``_inherit``),
**0 campos**, **1 método**. **No-op medido**, no un olvido.

Porte símbolo por símbolo — 0 de 1
=====================================

``default_get`` (:9-15) — **BLOQUEADO por mecanismo ausente**.

Su cuerpo entero está condicionado a una clave de **contexto**::

    project_company_id = self.env.context.get('create_project_employee_mapping', False)
    if project_company_id:
        result['company_id'] = project_company_id

Es decir: *"cuando este empleado se está creando desde el formulario de
tarifas de un proyecto, hereda la compañía de ese proyecto"*. El canal es
``env.context``, que no existe en este árbol — no hay contexto ambiental que
consultar, y ``default_get`` como tal tampoco tiene análogo (el default de un
campo Django es del campo, no del alta).

**Y no hace falta fabricarlo.** El llamador que crea el empleado desde
``project.sale.line.employee.map`` ya tiene el proyecto en la mano, y por
tanto su compañía: la asignación que la fuente hace por contexto aquí es un
argumento explícito. Inventar un canal de contexto para replicar un default
sería exactamente el mecanismo que este árbol evita a propósito — mismo
criterio que ``AccountAnalyticLine.user`` (*"sin default a env.user: esta API
no acopla el modelo al usuario ambiental"*, ``api: addons/analytic/models/
analytic_line.py``) y que ``AccountAnalyticLineCalendarEmployee.user`` en
``hr_timesheet``.

Sucesor: **ninguno**. Es una divergencia de mecanismo cerrada, no deuda.
"""


def apply_sale_timesheet_hr_employee_extensions():
    """No-op declarado — el único símbolo de la referencia es una divergencia
    de mecanismo cerrada. Ver el docstring del módulo.

    Se conserva la función (y su entrada en
    ``SaleTimesheetConfig._EXTENSIONES``) para que el archivo exista con el
    nombre de la referencia: el SITIO se lee contra la fuente, y su ausencia
    haría parecer que el símbolo se olvidó.
    """
    return None


__all__ = ['apply_sale_timesheet_hr_employee_extensions']
