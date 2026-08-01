"""Modelos del addon ``base`` — paquete espejo de ``odoo/addons/base/models/``.

Un archivo por modelo (monolito modular, como Odoo):

- ``ir_config_parameter.py`` → ``SystemParameter`` (config L2 global, key/value).
- ``ir_logging_log.py`` → ``IrLogging`` (log técnico ``ir.logging``, DEC-08).
- ``ir_attachment.py`` → ``IrAttachment`` (adjuntos archivo/URL ``ir.attachment``).
- ``ir_cron.py`` → ``IrCron`` (registro de horario ``ir.cron``; runner diferido).
- ``ir_default.py`` → ``IrDefault`` (valores por defecto de campo ``ir.default``).
- ``ir_filters.py`` → ``IrFilters`` (filtros de búsqueda guardados ``ir.filters``).
- ``res_currency.py`` → ``ResCurrency`` (moneda ISO 4217).
- ``res_country.py`` → ``ResCountry`` + ``ResCountryState`` (geografía política).
- ``res_partner.py`` → ``ResPartner`` (el party: persona, empresa o dirección).
- ``res_users.py`` → ``ResUsers`` (credencial; delega identidad al partner).
- ``res_config_settings.py`` → ``SiteSettings`` (~ ``res.config.settings``, singleton).

Se reexporta todo aquí para preservar el contrato de import histórico
``from addons.base.models import SystemParameter, ResCurrency, ...``.
"""
from .mixins import (
    TimeStampedModel,
    AppendOnlyModel,
    SoftDeleteModel,
    SoftDeleteQuerySet,
    SoftDeleteManager,
    AllObjectsManager,
)
from .decimal_precision import DecimalPrecision
from .ir_config_parameter import (
    _DEFAULT_PARAMETERS,
    _PARAM_CACHE,
    _clear_cache,
    SystemParameter,
)
from .ir_attachment import IrAttachment
from .ir_cron import IrCron
from .ir_default import IrDefault
from .ir_filters import IrFilters
from .ir_logging_log import IrLogging
from .ir_module import IrModule, IrModuleDependency
from .ir_sequence import IrSequence
from .report_export_job import ExportJob
from .res_bank import ResBank
from .res_country import ResCountry, ResCountryState
from .res_country_group import ResCountryGroup
from .res_partner import ResPartner
from .res_users import ResUsers, ResUsersLog
from .res_device import ResDeviceLog
from .res_users_deletion import ResUsersDeletion
from .res_users_settings import ResUsersSettings
from .res_currency import ResCurrency
from .res_currency_rate import ResCurrencyRate
from .res_config_settings import SiteSettings
from .res_lang import ResLang

__all__ = [
    'TimeStampedModel',
    'AppendOnlyModel',
    'SoftDeleteModel',
    'SoftDeleteQuerySet',
    'SoftDeleteManager',
    'AllObjectsManager',
    '_DEFAULT_PARAMETERS',
    '_PARAM_CACHE',
    '_clear_cache',
    'SystemParameter',
    'IrLogging',
    'IrAttachment',
    'IrCron',
    'IrDefault',
    'IrFilters',
    'ResCurrency',
    'ResCurrencyRate',
    'ResCountry',
    'ResCountryState',
    'ResCountryGroup',
    'ResPartner',
    'ResUsers',
    'ResUsersLog',
    'ResDeviceLog',
    'ResUsersDeletion',
    'ResUsersSettings',
    'ResLang',
    'ResBank',
    'DecimalPrecision',
    'IrModule',
    'IrModuleDependency',
    'IrSequence',
    'ExportJob',
    'SiteSettings',
]

from .checkout_attempt import CheckoutAttempt  # noqa: E402
