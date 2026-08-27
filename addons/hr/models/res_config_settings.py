"""``res.config.settings`` — los ajustes de RR.HH. en el formulario general.

Adaptación de Odoo hr/models/res_config_settings.py (odoo-tools@622ddc2a,
odoo19c:, LGPL-3, 21 líneas) — atribución y aviso de licencia preservados
(DEC-KX-03).

Porte BLOQUEADO — 0 de 11 símbolos, por la misma causa que en otros tres addons
================================================================================

``odoo19c: addons/hr/models/res_config_settings.py``: 11 campos, 0 métodos.

===============================================  ==================================
Símbolo de la referencia (línea)                 Estado
===============================================  ==================================
``resource_calendar_id`` (``:7-9``)              bloqueado
``module_hr_presence`` (``:10``)                 bloqueado
``module_hr_skills`` (``:11``)                   bloqueado
``hr_presence_control_login`` (``:12``)          bloqueado
``hr_presence_control_email`` (``:13``)          bloqueado
``hr_presence_control_ip`` (``:14``)             bloqueado
``module_hr_attendance`` (``:15``)               bloqueado
``hr_presence_control_email_amount`` (``:16``)   bloqueado
``hr_presence_control_ip_list`` (``:17``)        bloqueado
``contract_expiration_notice_period`` (``:18``)  bloqueado
``work_permit_expiration_notice_period`` (``:19``) bloqueado
===============================================  ==================================

La causa, medida (es la CUARTA ocurrencia del mismo bloqueo)
-------------------------------------------------------------

``src/addons/base/models/res_config.py`` declara ``ResConfigSettings`` con
``class Meta: abstract = True``. Un campo colgado sobre una clase abstracta de
Django **no genera columna**: el ajuste existiría en el registro y no en la
base. Es exactamente el bloqueo ya declarado por
``account_check_printing``, ``l10n_mx`` y ``product_expiry`` en sus
``res_config_settings.py`` — se declara la divergencia y se espera, para no
fabricar una cuarta forma. Sucesor: tarea **#278** (``ResConfigSettings``
abstracto sin subclase consumidora), donde se decide la forma para los
cuatro addons a la vez.

Nota de contenido: DIEZ de los once campos son ``related='company_id.*'`` o
``module_*`` — espejos de formulario. Las columnas reales que espejan ya
están portadas en este mismo pase (``hr/models/res_company.py``), así que el
día que #278 resuelva la forma, este archivo es puro espejo sin lógica.
``resource_calendar_id`` espeja ``company_id.resource_calendar_id``, que en
este árbol es la propiedad ``ResCompany.resource_calendar``
(``resource/models/res_company.py``).
"""


def apply_hr_res_config_settings_extensions():
    """No-op declarado — ver el docstring del módulo (bloqueo #278)."""
    return None


__all__ = ['apply_hr_res_config_settings_extensions']
