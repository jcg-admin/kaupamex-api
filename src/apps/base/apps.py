"""AppConfig — apps.base (equivalente del addon ``base`` de Odoo).

``apps.base`` es el **addon fundacional** del proyecto, fiel a
``odoo/addons/base`` (Odoo 19/18) y a ``pretix/base``: aloja los modelos de
infraestructura tipo ``ir.*`` que no pertenecen a un dominio concreto. Ni Odoo
ni pretix usan una app "config" para esto — el modelo global key/value vive en
``base`` (``ir.config_parameter`` en Odoo; ``GlobalSettingsObject`` en pretix).
"config" en Odoo es la **L1** (``odoo/conf`` — removido en v19 — y
``odoo.tools.config``), que en nuestro árbol es ``src/config`` (settings), no
una app.

Primer inquilino: ``SystemParameter`` (config runtime **global** L2, key/value,
editable en caliente, sembrada y cacheada; equivalente Django de
``ir.config_parameter``). Diseño: ``analisis-estrategia-configuracion-capas``
(L2); portación fiel: ``implementar-systemparameter-l2``.

``apps.base`` vive en el **plano de control** (base ``default``): son modelos
globales de la instancia, no per-empresa (eso es L3 = ``Company``/
``CompanySetting``, SOL-085). Por eso su app_label ``base`` se registra en
``MULTIDB_CONTROL_PLANE_APPS`` (SOL-091) para que el router lo enrute siempre a
``default`` bajo N>1.
"""
from django.apps import AppConfig


class BaseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.base'
    label = 'base'
    verbose_name = 'Base (infraestructura fundacional ir.*)'
