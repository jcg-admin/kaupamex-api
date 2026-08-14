"""AppConfig — addons.base_geolocalize.

Fiel al addon ``base_geolocalize`` de Odoo (18/19, "Partners Geolocation"):
convierte direcciones en coordenadas GPS via un proveedor externo
(OpenStreetMap Nominatim por defecto; Google Maps opcional). El catálogo de
proveedores (``base.geo_provider``) es global de instancia — por eso su
app_label se registra en ``MULTIDB_CONTROL_PLANE_APPS`` (mismo patrón que
``base`` y ``base_address_extended``, SOL-091).

``base.geocoder`` (AbstractModel en Odoo, sin tabla) se porta como la clase de
servicio ``Geocoder`` en ``models/base_geocoder.py`` — no un ``models.Model``,
fiel a que Odoo tampoco le da persistencia propia.
"""
from django.apps import AppConfig


class BaseGeolocalizeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.base_geolocalize'
    label = 'base_geolocalize'
    verbose_name = 'Base — geolocalización de direcciones (base_geolocalize)'
