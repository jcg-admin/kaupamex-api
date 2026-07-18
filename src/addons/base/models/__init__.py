"""Modelos del addon ``base`` — paquete espejo de ``odoo/addons/base/models/``.

Un archivo por modelo (monolito modular, como Odoo):

- ``ir_config_parameter.py`` → ``SystemParameter`` (config L2 global, key/value).
- ``res_currency.py`` → ``ResCurrency`` (moneda ISO 4217).
- ``res_country.py`` → ``ResCountry`` + ``ResCountryState`` (geografía política).

Se reexporta todo aquí para preservar el contrato de import histórico
``from addons.base.models import SystemParameter, ResCurrency, ...``.
"""
from .decimal_precision import DecimalPrecision
from .ir_config_parameter import (
    _DEFAULT_PARAMETERS,
    _PARAM_CACHE,
    _clear_cache,
    SystemParameter,
)
from .ir_sequence import IrSequence
from .res_bank import ResBank
from .res_country import ResCountry, ResCountryState
from .res_country_group import ResCountryGroup
from .res_currency import ResCurrency
from .res_currency_rate import ResCurrencyRate
from .res_lang import ResLang

__all__ = [
    '_DEFAULT_PARAMETERS',
    '_PARAM_CACHE',
    '_clear_cache',
    'SystemParameter',
    'ResCurrency',
    'ResCurrencyRate',
    'ResCountry',
    'ResCountryState',
    'ResCountryGroup',
    'ResLang',
    'ResBank',
    'DecimalPrecision',
    'IrSequence',
]
