"""``res.config.settings`` — declarado NO PORTADO, con su medición.

Adaptación de ``odoo19c: addons/base_geolocalize/models/res_config_settings.py``
(``odoo-tools@622ddc2a``, LGPL-3 — atribución y aviso de licencia preservados,
DEC-KX-03):

.. code-block:: python

    class ResConfigSettings(models.TransientModel):
        _inherit = 'res.config.settings'

        geoloc_provider_id = fields.Many2one(
            'base.geo_provider', string='API',
            config_parameter='base_geolocalize.geo_provider',
            default=lambda x: x.env['base.geocoder']._get_provider())
        geoloc_provider_techname = fields.Char(
            related='geoloc_provider_id.tech_name', readonly=True)
        geoloc_provider_googlemap_key = fields.Char(
            string='Google Map API Key',
            config_parameter='base_geolocalize.google_map_api_key', help=…)

Tres campos, los tres pasarela de formulario — el dato ya está portado
======================================================================

Ninguno guarda nada propio. Dos son ``config_parameter=``: escriben y leen
**la clave de configuración**, que aquí es ``SystemParameter`` y ya la
consultan sus dos lectores reales —``BaseGeocoder._get_provider``
(``base_geolocalize.geo_provider``) y ``get_google_map_api_key``
(``base_geolocalize.google_map_api_key``), los dos en ``base_geocoder.py``—.
El tercero es un ``related`` de lectura sobre el primero.

Es decir: el DATO y su travesía están portados enteros; lo que falta es la
**superficie del formulario de Ajustes generales** del cliente web de Odoo.

Por qué no se porta la CLASE — medido, no supuesto
==================================================

``src/addons/base/models/res_config.py:196`` declara ``ResConfigSettings`` con
``Meta: abstract = True``: es una base de la que cada addon deriva **su propia
subclase concreta**, no un modelo único sobre el que varios addons cuelguen
campos como sí ocurre con ``ResCompany`` o ``IrActionsServer``.

.. code-block:: text

   grep -rn "class .*(ResConfigSettings)" src/addons addons --include=*.py
   → una sola subclase concreta:
     addons/base_setup/models/res_config_settings.py::SiteConfigSettings

   grep -rn "geoloc_provider" addons/base_setup/
   → 0 hits

Ese formulario —el único que existe, consumido por ``base_setup/controllers/``
(DRF)— no declara ningún campo de este addon. Fabricar aquí una subclase
paralela **no sería el mismo símbolo**: la referencia expone estos tres campos
en el formulario COMPARTIDO de ajustes, no en uno nuevo que nadie navegaría;
sería inventar superficie, que es lo que ``porte-completo-no-parcial.md``
prohíbe expresamente.

Es el mismo caso y el mismo desenlace que
``addons/account_check_printing/models/res_config_settings.py`` y
``addons/l10n_mx/models/res_config_settings.py`` ya documentan.

Lo que este archivo no cierra
==============================

Los tres campos, como superficie de formulario. Su condición de cierre es
concreta y está fuera de este addon: **que ``base_setup.SiteConfigSettings``
crezca el bloque de geolocalización**. Sucesor: el porte de ``base_setup``,
tarea **#281** de esta misma serie — donde queda registrado que este addon es
uno de sus consumidores pendientes.
"""
