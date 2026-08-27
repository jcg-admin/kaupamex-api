"""Modelos del addon ``project_account`` — rentabilidad contable de proyecto.

Adaptación de Odoo ``project_account`` (``odoo-tools@622ddc2a``, ``odoo19c:``,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Este addon **no declara modelos propios**: como la referencia, extiende el que
ya existe (``project.project``). ``models/project_project.py`` espeja el único
archivo de modelo de la referencia y expone
``apply_project_account_project_project_extensions()``, que
``ProjectAccountConfig.ready()`` invoca — el idioma de extensión cross-app ya
establecido en este árbol (``product_expiry``, ``hr_timesheet``,
``account_qr_code_*``). Por eso aquí no se importa nada: sin modelo concreto
no hay clase que registrar en el import de la app.
"""
