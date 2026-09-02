"""AppConfig — addons.base_address_extended.

Fiel al addon ``base_address_extended`` de Odoo (18/19): extiende ``base`` con
el catálogo de ciudades (``res.city``), el flag ``enforce_cities`` sobre el país
y el parsing estructurado de calle. Cross-app ``_inherit`` de Odoo sobre
``res.country`` → RELATED OneToOne en Django (DEC-SALE-01): Django no inyecta
columnas cross-app, así que ``enforce_cities`` vive en ``CountryAddressPolicy``.

Es catálogo global de instancia (como ``base``), por eso su app_label se
registra en ``MULTIDB_CONTROL_PLANE_APPS`` (SOL-091).

Los cuatro símbolos que la fuente declara sobre ``res.partner`` —
``_address_fields``, ``_onchange_city_id``, ``_onchange_country_id`` y
``_get_res_city_by_name`` — se cuelgan de ``base.ResPartner`` en ``ready()``,
que es el equivalente de su ``_inherit``.
"""
import importlib

from django.apps import AppConfig


class BaseAddressExtendedConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.base_address_extended'
    label = 'base_address_extended'
    verbose_name = 'Base — direcciones estructuradas (res.city, street split)'

    #: Módulos que cuelgan algo de un modelo AJENO — ≙ ``_inherit``.
    _EXTENSIONS = (
        'addons.base_address_extended.models.res_partner',
    )

    def ready(self):
        """Aplica lo que este addon cuelga de ``base.ResPartner``.

        ``importlib.import_module`` y no un ``import`` al top — excepción #4 de
        ``no-lazy-imports.md``: es una llamada de función, no un statement.
        """
        for path in self._EXTENSIONS:
            importlib.import_module(path).apply_base_address_extended_extensions()
