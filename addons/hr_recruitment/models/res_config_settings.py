"""``res.config.settings`` — los ajustes de reclutamiento en el formulario
general (Odoo ``hr_recruitment``).

Adaptación de Odoo ``hr_recruitment/models/res_config_settings.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 11 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte BLOQUEADO — 0 de 3 símbolos, quinta ocurrencia del mismo bloqueo
==========================================================================

``src/addons/base/models/res_config.py`` declara ``ResConfigSettings`` con
``class Meta: abstract = True``. Un campo colgado sobre una clase abstracta
de Django **no genera columna**: el ajuste existiría en el registro y no en
la base. Es el mismo bloqueo ya declarado por ``account_check_printing``,
``l10n_mx``, ``product_expiry`` y ``hr`` en sus ``res_config_settings.py``
— se declara la divergencia y se espera la tarea **#278**
(``ResConfigSettings`` abstracto sin subclase consumidora), donde se
decide la forma para los cinco addons a la vez.

===============================================  ==========
Símbolo de la referencia (línea)                  Estado
===============================================  ==========
``module_website_hr_recruitment`` (``:9``)        bloqueado
``module_hr_recruitment_survey`` (``:10``)        bloqueado
``module_hr_recruitment_extract`` (``:11``)       bloqueado
===============================================  ==========

Los tres son banderas de instalación de módulos satélite (portal web de
empleos, formularios de entrevista, OCR de CV) que este árbol no modela
como addons instalables en caliente — divergencia de mecanismo adicional,
independiente del bloqueo #278.
"""


def apply_hr_recruitment_res_config_settings_extensions():
    """No-op declarado — ver el docstring del módulo (bloqueo #278)."""
    return None


__all__ = ['apply_hr_recruitment_res_config_settings_extensions']
