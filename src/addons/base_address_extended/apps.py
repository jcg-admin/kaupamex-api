"""AppConfig — addons.base_address_extended.

Fiel al addon ``base_address_extended`` de Odoo (18/19): extiende ``base`` con
el catálogo de ciudades (``res.city``), el flag ``enforce_cities`` sobre el país
y el parsing estructurado de calle. Cross-app ``_inherit`` de Odoo sobre
``res.country`` → RELATED OneToOne en Django (DEC-SALE-01): Django no inyecta
columnas cross-app, así que ``enforce_cities`` vive en ``CountryAddressPolicy``.

Es catálogo global de instancia (como ``base``), por eso su app_label se
registra en ``MULTIDB_CONTROL_PLANE_APPS`` (SOL-091).
"""
from django.apps import AppConfig


class BaseAddressExtendedConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.base_address_extended'
    label = 'base_address_extended'
    verbose_name = 'Base — direcciones estructuradas (res.city, street split)'
