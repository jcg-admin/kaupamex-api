"""``res.config.settings`` extendido por ``web`` — nombre de la app PWA.

Adaptación de ``odoo19c: addons/web/models/res_config_settings.py``
(``odoo-tools@622ddc2a``, 10 líneas, LGPL-3 — atribución y aviso de licencia
preservados, DEC-KX-03). Cierra la tarea **#397** (``check_mirrored_roots.py``,
13 archivos / 22 ``def`` del addon raíz ``web``); este archivo aporta 0 de
esos 22 (es un campo declarativo, sin ``def``).

Medición símbolo-por-símbolo (``re.findall(r'^\\s{4}def (\\w+)', ref)``, mismo
criterio que ``porte-completo-no-parcial.md``): **0** métodos — la clase
entera es un único campo declarativo (``web_app_name``) sobre
``res.config.settings``. El nodo ``class:`` sí cuenta como símbolo
(``H-API-379``, igual criterio que ``res_users_settings_embedded_action.py``):
**1 clase, 1 portada**.

Por qué es un modelo NUEVO, no un ``chain_method`` sobre uno existente
==========================================================================

A diferencia de ``res_partner.py``/``ir_http.py`` de este mismo addon —que
cuelgan métodos sobre un modelo YA concreto vía ``chain_method``—,
``res.config.settings`` en la referencia es un formulario **abstracto** que
cada addon extiende con SUS campos propios (``_inherit`` fusiona todos los
``_inherit`` en una sola clase Python en tiempo de carga). Django no tiene
esa fusión de clases entre apps; el patrón ya establecido en este árbol
—``addons/base_setup/models/res_config_settings.py::SiteConfigSettings``,
la extensión de referencia de ``res.config.settings``— es que **cada addon
declara su propia subclase concreta** de
``addons.base.models.res_config.ResConfigSettings`` (la base abstracta,
``odoo/addons/base/models/res_config.py``, ya portada). Se sigue el mismo
patrón aquí: ``WebConfigSettings`` es la subclase de ``web``.

``managed = False`` — ``TransientModel``, sin ``CREATE TABLE``
==================================================================

Igual que ``SiteConfigSettings``: la referencia declara
``models.TransientModel`` (formulario que no persiste). El equivalente
Django es ``managed = False`` — la clase existe y se instancia en memoria, y
Django **no** emite ``CREATE TABLE`` para ella al migrar.

Django SÍ registra el modelo en el grafo de migraciones aunque no cree
tabla (medido: ``manage.py makemigrations web --dry-run`` propone
``CreateModel`` para esta clase igual que lo hace para
``base_setup.SiteConfigSettings``, ambas ``managed=False`` — la migración
resultante lleva ``"managed": False`` en sus ``options``, que es lo que le
dice al ejecutor de SQL que omita el ``CREATE TABLE``). Se añade
``migrations/0002_webconfigsettings.py`` por esa razón — no por necesidad de
esquema, sino porque el grafo de migraciones de Django lo exige para
reconocer la clase.

El campo, verbatim
=====================

``web_app_name = fields.Char('Web App Name',
config_parameter='web.web_app_name')`` — un ``Char`` con ``config_parameter``,
sin ``default_model``/``implied_group``. Se porta como
``models.CharField`` + ``field_attrs`` (ver el docstring de ``res_config.py``
para por qué el atributo extra vive en un dict de clase y no colgado del
campo). El destino sigue siendo ``SystemParameter`` — infra/ops de
plataforma (L0, DEC-KX-05): el nombre visible de la PWA es una decisión de
despliegue, no de tenant.
"""
from django.db import models

from addons.base.models.res_config import ResConfigSettings


class WebConfigSettings(ResConfigSettings):
    """``res.config.settings`` de ``web`` — nombre visible de la app PWA.

    Fiel a ``odoo19c: web/models/res_config_settings.py:8-10``.
    """

    web_app_name = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name='Nombre de la app web',
        help_text='Nombre visible de la PWA (Odoo web_app_name, '
                  'config_parameter=web.web_app_name).',
    )

    #: ≙ ``config_parameter='web.web_app_name'`` colgado del campo en la
    #: referencia — aquí vive aparte (ver el docstring del módulo).
    field_attrs = {
        'web_app_name': {'config_parameter': 'web.web_app_name'},
    }

    class Meta:
        # El equivalente Django del ``TransientModel`` — ver el docstring
        # del módulo. Un ``abstract = True`` no serviría: el formulario
        # necesita instanciarse para aplicar sus valores.
        managed = False
        db_table = 'web_webconfigsettings_unmanaged'
        verbose_name = 'Ajustes de la app web'
