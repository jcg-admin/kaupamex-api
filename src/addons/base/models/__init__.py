"""Modelos del addon ``base`` — paquete espejo de ``odoo/addons/base/models/``.

Un archivo por modelo (monolito modular, como Odoo):

- ``ir_config_parameter.py`` → ``SystemParameter`` (config L2 global, key/value).
- ``res_currency.py`` → ``ResCurrency`` (moneda ISO 4217).
- ``res_country.py`` → ``ResCountry`` + ``ResCountryState`` (geografía política).

Se reexporta todo aquí para preservar el contrato de import histórico
``from addons.base.models import SystemParameter, ResCurrency, ...``.
"""
from .ir_config_parameter import (
    _DEFAULT_PARAMETERS,
    _PARAM_CACHE,
    _clear_cache,
    SystemParameter,
)
from .res_country import ResCountry, ResCountryState
from .res_currency import ResCurrency

__all__ = [
    '_DEFAULT_PARAMETERS',
    '_PARAM_CACHE',
    '_clear_cache',
    'SystemParameter',
    'ResCurrency',
    'ResCountry',
    'ResCountryState',
]
