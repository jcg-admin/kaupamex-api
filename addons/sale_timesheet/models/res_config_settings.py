"""``res.config.settings`` — el ajuste "facturar según hojas de horas"
(Odoo ``sale_timesheet``).

Adaptación de Odoo ``sale_timesheet/models/res_config_settings.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 10 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Medido por AST sobre la referencia: 1 clase (``ResConfigSettings``,
``TransientModel``, ``_inherit``), **1 campo**, **0 métodos**.

Porte símbolo por símbolo — 0 de 1, por la QUINTA ocurrencia del mismo bloqueo
===============================================================================

``invoice_policy`` (:9) — ``fields.Boolean(string="Invoice Policy",
help="Timesheets taken when invoicing time spent")``. **BLOQUEADO.**

La causa, medida: ``src/addons/base/models/res_config.py`` declara
``ResConfigSettings`` con ``class Meta: abstract = True``. Un campo colgado
sobre una clase abstracta de Django **no genera columna** — el ajuste
existiría en el registro y no en la base.

Es exactamente el bloqueo que ya declararon ``account_check_printing``,
``l10n_mx``, ``product_expiry`` y ``hr`` en sus propios
``res_config_settings.py``. Se declara la divergencia y se espera, para no
fabricar una quinta forma: la decisión de forma es de la tarea **#278**
(``ResConfigSettings`` abstracto sin subclase consumidora), donde se resuelve
para los cinco addons a la vez.

Nota de contenido: el campo es un espejo de formulario sobre
``product.template.invoice_policy`` (``odoo19c: sale/models/
product_template.py:35``), que tampoco existe en este árbol — así que aunque
#278 resolviera la forma hoy, seguiría faltando la columna que espeja.
Sucesor de esa segunda mitad: la misma tarea PENDIENTE DE ASIGNAR que
bloquea a ``models/product_template.py``.
"""


def apply_sale_timesheet_res_config_settings_extensions():
    """No-op declarado — ver el docstring del módulo (bloqueo #278)."""
    return None


__all__ = ['apply_sale_timesheet_res_config_settings_extensions']
