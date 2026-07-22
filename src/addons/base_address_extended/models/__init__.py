"""Modelos de ``base_address_extended`` — paquete espejo de
``odoo/addons/base_address_extended/models/``.

Un archivo por modelo (monolito modular, como Odoo):

- ``res_city.py`` → ``ResCity`` (catálogo de ciudades).
- ``res_country.py`` → ``CountryAddressPolicy`` (``enforce_cities`` RELATED).
- ``res_partner.py`` → ``AddressStructured`` (street-split + city RELATED sobre
  ``users.Address``).
- ``res_city_zip.py`` → ``CatalogPostalCode`` (~ ``res.city.zip``, catálogo CP).
"""
from .res_city import ResCity
from .res_country import CountryAddressPolicy
from .res_city_zip import CatalogPostalCode
from .res_partner import AddressStructured

__all__ = ['ResCity', 'CountryAddressPolicy', 'AddressStructured', 'CatalogPostalCode']
