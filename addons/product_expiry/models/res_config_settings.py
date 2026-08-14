"""``res.config.settings`` — el ajuste de caducidad en el albarán.

Adaptación de Odoo ``product_expiry/models/res_config_settings.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3) — atribución y aviso de
licencia preservados (DEC-KX-03).

Porte BLOQUEADO — 0 de 4 símbolos, por la misma causa que en otros dos addons
==============================================================================

``odoo19c: addons/product_expiry/models/res_config_settings.py`` (27 líneas):
1 campo + 3 ``@api.onchange``.

===============================================  ==================================
Símbolo de la referencia (línea)                 Estado
===============================================  ==================================
``group_expiry_date_on_delivery_slip`` (9-11)    bloqueado
``_onchange_group_lot_on_delivery_slip`` (13-16) bloqueado
``_onchange_group_stock_production_lot`` (18-21) bloqueado
``_onchange_module_product_expiry`` (23-27)      bloqueado
===============================================  ==================================

La causa, medida
------------------

``src/addons/base/models/res_config.py:196`` declara ``ResConfigSettings`` con
``class Meta: abstract = True``. Un campo colgado sobre una clase abstracta de
Django **no genera columna**: el ajuste existiría en el registro y no en la
base, y el primer ``.save()`` fallaría por columna inexistente.

Es la **tercera** ocurrencia del mismo bloqueo, y se resuelve igual que las dos
anteriores para no fabricar una tercera forma:
``addons/account_check_printing/models/res_config_settings.py`` y
``addons/l10n_mx/models/res_config_settings.py`` declaran la divergencia y
esperan. La única subclase concreta del árbol es ``SiteConfigSettings``
(``addons/base_setup/models/res_config_settings.py:108``), de otro addon:
colgar aquí el campo sobre ella pondría el símbolo en el addon equivocado.

Los tres ``onchange`` dependen además de tres campos de grupo que tampoco
existen (``group_lot_on_delivery_slip``, ``group_stock_production_lot``,
``module_product_expiry``) — los declara ``stock`` en su propio
``res_config_settings.py``, que no está portado.

Sucesor registrado: tarea **#278** (``ResConfigSettings`` abstracto sin
subclase consumidora), que es donde se decide la forma para los tres addons a
la vez.
"""


def apply_product_expiry_extensions():
    """No-op declarado — ver el docstring del módulo."""
    return None


__all__ = ['apply_product_expiry_extensions']
