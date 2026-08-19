"""``res.config.settings`` — ajustes de hoja de horas (Odoo ``hr_timesheet``).

Adaptación de Odoo ``hr_timesheet/models/res_config_settings.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3) — atribución y aviso de
licencia preservados (DEC-KX-03).

Porte BLOQUEADO — 0 de 8 símbolos, misma causa que otros tres addons
========================================================================

Medido por AST: 1 clase (``_inherit``, ``TransientModel``), 6 campos,
3 métodos.

======================================  ==================================
Símbolo de la referencia (línea)         Estado
======================================  ==================================
``module_project_timesheet_holidays``    bloqueado
``reminder_user_allow``/``reminder_allow`` bloqueado
``project_time_mode_id``                 bloqueado
``is_encode_uom_days``                   bloqueado
``timesheet_encode_method``              bloqueado
``_compute_timesheet_encode_method``     bloqueado
``_inverse_timesheet_encode_method``     bloqueado
``_compute_is_encode_uom_days``          bloqueado
``_compute_timesheet_modules``           bloqueado
======================================  ==================================

La causa, medida
------------------

``src/addons/base/models/res_config.py:196`` declara ``ResConfigSettings``
con ``class Meta: abstract = True``. Un campo colgado sobre una clase
abstracta de Django **no genera columna**: el ajuste existiría en el
registro y no en la base, y el primer ``.save()`` fallaría por columna
inexistente.

Es la **cuarta** ocurrencia del mismo bloqueo, y se resuelve igual que las
tres anteriores para no fabricar una cuarta forma:
``addons/product_expiry/models/res_config_settings.py``,
``addons/account_check_printing/models/res_config_settings.py`` y
``addons/l10n_mx/models/res_config_settings.py`` declaran la divergencia y
esperan. La única subclase concreta del árbol sigue siendo
``SiteConfigSettings`` (``addons/base_setup/models/res_config_settings.py``),
de otro addon.
"""


def apply_hr_timesheet_res_config_settings_extensions():
    """No-op declarado — ver el docstring del módulo."""
    return None
