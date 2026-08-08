"""AppConfig — addons.base (equivalente del addon ``base`` de Odoo).

``addons.base`` es el **addon fundacional** del proyecto, fiel a
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

``addons.base`` vive en el **plano de control** (base ``default``): son modelos
globales de la instancia, no per-empresa (eso es L3 = ``Company``/
``CompanySetting``, SOL-085). Por eso su app_label ``base`` se registra en
``MULTIDB_CONTROL_PLANE_APPS`` (SOL-091) para que el router lo enrute siempre a
``default`` bajo N>1.
"""
from django.apps import AppConfig, apps

from orm.inherits import apply_inherits


class BaseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.base'
    label = 'base'
    verbose_name = 'Base (infraestructura fundacional ir.*)'

    def ready(self):
        """Instala la delegación ``_inherits`` de ``res.users`` al partner.

        Equivale a ``_inherits = {'res.partner': 'partner_id'}`` de la
        referencia (``odoo19c: odoo/addons/base/models/res_users.py:165``),
        que es de donde el usuario obtiene ``tz``, ``lang`` y el resto de los
        campos del partner.

        Va en ``ready()`` y no al pie del módulo porque ``res_users`` resuelve
        el modelo de partner de forma perezosa (``_partner_model()``) para
        evitar el ciclo de importación; aquí el registro ya está poblado.
        ``apps.get_model`` es una **llamada**, no un ``import`` — el gate de
        no-lazy-imports da exit 0 (misma resolución que la excepción #4 de
        ``no-lazy-imports.md``).
        """
        apply_inherits(
            apps.get_model('base', 'ResUsers'),
            apps.get_model('base', 'ResPartner'),
            'partner',
        )
