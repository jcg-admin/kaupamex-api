"""Modelos de ``base_geolocalize`` — paquete espejo de
``odoo/addons/base_geolocalize/models/``.

Un archivo por modelo (monolito modular, como Odoo):

- ``base_geocoder.py`` -> ``GeoProvider`` (catálogo) + ``Geocoder`` (servicio,
  ``base.geocoder`` de Odoo — ``AbstractModel`` sin tabla) +
  ``GeoProviderNotImplemented``.
- ``res_partner.py`` -> ``PartnerGeolocation`` (lat/lng/fecha RELATED sobre
  ``base.ResPartner``).
"""
from .base_geocoder import (
    BaseGeocoder, GeoProvider, GeoProviderNotImplemented, get_google_map_api_key)
from .res_partner import PartnerGeolocation

__all__ = [
    'GeoProvider',
    'BaseGeocoder',
    'get_google_map_api_key',
    'GeoProviderNotImplemented',
    'PartnerGeolocation',
]
