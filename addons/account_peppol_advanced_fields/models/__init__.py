"""Modelos del addon ``account_peppol_advanced_fields``.

Adaptación de Odoo ``account_peppol_advanced_fields``
(``odoo19c: addons/account_peppol_advanced_fields/``, LGPL-3) — atribución y
aviso de licencia preservados (DEC-KX-03).

Este addon **no declara modelos propios**: como la referencia, extiende
``account.move`` con siete campos de texto. Por eso aquí no se importa nada —
sin modelo concreto no hay clase que registrar en el import de la app.

``account_move.py`` espeja el único archivo de la referencia y expone
``apply_account_peppol_advanced_fields_account_move_extensions()``, que
``AccountPeppolAdvancedFieldsConfig.ready()`` invoca: el idioma de extensión
cross-app ya establecido en este árbol (``project_account``,
``account_debit_note``, ``account_peppol``).
"""
