"""Modelos del addon ``base`` — paquete espejo de ``odoo/addons/base/models/``.

Un archivo por modelo (monolito modular, como Odoo) — **incluidos los
mixins**: la referencia tiene ``image_mixin.py`` / ``avatar_mixin.py`` /
``properties_base_definition_mixin.py``, uno por archivo, no un ``mixins.py``
que los agrupe por naturaleza.

- ``timestamped_mixin.py`` → ``TimeStampedModel`` (≙ log-access del ORM).
- ``append_only_mixin.py`` → ``AppendOnlyModel`` (inmutabilidad de logs).
- ``soft_delete_mixin.py`` → ``SoftDeleteModel`` + su QuerySet y managers
  (≙ campo ``active``).
- ``image_mixin.py`` → ``ImageMixin`` (imagen + sus cuatro reducciones).
- ``avatar_mixin.py`` → ``AvatarMixin`` (avatar; retrato SVG si no hay imagen).
- ``ir_exports.py`` → ``IrExports`` + ``IrExportsLine`` (exportaciones guardadas).
- ``report_layout.py`` → ``ReportLayout`` (diseños de documento impreso).
- ``res_groups_privilege.py`` → ``ResGroupsPrivilege`` (agrupa grupos en el form).

- ``ir_asset.py`` → ``IrAsset`` + ``AssetPaths`` (directivas sobre bundles; el
  resolutor de rutas contra manifests no aplica — lo hace Webpack en ``ui``).
- ``ir_autovacuum.py`` → ``IrAutovacuum`` + ``is_autovacuum`` (colector de los
  métodos ``@api.autovacuum``).
- ``ir_binary.py`` → ``IrBinary`` (sirve campos binarios como respuesta HTTP).
- ``ir_fields.py`` → ``IrFieldsConverter`` (conversión de valores de import).
- ``report_paperformat.py`` → ``ReportPaperformat`` + ``PAPER_SIZES``
  (formato de papel de impresión; 31 tamaños verbatim).
- ``ir_demo.py`` → ``IrDemo`` (asistente de datos de demostración).
- ``ir_demo_failure.py`` → ``IrDemoFailure`` + ``IrDemoFailureWizard``
  (módulos cuyo seed de demostración falló).
- ``ir_profile.py`` → ``IrProfile`` + ``BaseEnableProfilingWizard``
  (resultados de perfilado; sin el visor speedscope).

- ``ir_config_parameter.py`` → ``SystemParameter`` (config L2 global, key/value).
- ``ir_logging.py`` → ``IrLogging`` (log técnico ``ir.logging``, DEC-08).
- ``ir_attachment.py`` → ``IrAttachment`` (adjuntos archivo/URL ``ir.attachment``).
- ``ir_cron.py`` → ``IrCron`` (registro de horario ``ir.cron``; runner diferido).
- ``ir_default.py`` → ``IrDefault`` (valores por defecto de campo ``ir.default``).
- ``ir_filters.py`` → ``IrFilters`` (filtros de búsqueda guardados ``ir.filters``).
- ``ir_ui_menu.py`` → ``IrUiMenu`` (árbol de navegación ``ir.ui.menu``, podado
  por capacidad; vive en ``base`` igual que en la referencia).
- ``res_currency.py`` → ``ResCurrency`` (moneda ISO 4217).
- ``res_country.py`` → ``ResCountry`` + ``ResCountryState`` (geografía política).
- ``res_partner.py`` → ``ResPartner`` (el party: persona, empresa o dirección).
- ``res_users.py`` → ``ResUsers`` (credencial; delega identidad al partner).
- ``res_config_settings.py`` → ``SiteSettings`` (~ ``res.config.settings``, singleton).

Se reexporta todo aquí para preservar el contrato de import histórico
``from addons.base.models import SystemParameter, ResCurrency, ...``.
"""
from .timestamped_mixin import TimeStampedModel
from .append_only_mixin import AppendOnlyModel
from .soft_delete_mixin import (
    SoftDeleteModel,
    SoftDeleteQuerySet,
    SoftDeleteManager,
    AllObjectsManager,
)
from .image_mixin import ImageMixin
from .avatar_mixin import AvatarMixin
from .decimal_precision import DecimalPrecision
from .ir_config_parameter import (
    _DEFAULT_PARAMETERS,
    _PARAM_CACHE,
    _clear_cache,
    SystemParameter,
)
from .ir_asset import IrAsset, AssetPaths
from .ir_attachment import IrAttachment
from .ir_autovacuum import IrAutovacuum, is_autovacuum
from .ir_binary import IrBinary
from .ir_fields import IrFieldsConverter
from .ir_cron import IrCron
from .ir_demo import IrDemo
from .ir_demo_failure import IrDemoFailure, IrDemoFailureWizard
from .ir_profile import IrProfile, BaseEnableProfilingWizard
from .ir_default import IrDefault
from .ir_filters import IrFilters
from .ir_logging import IrLogging
from .ir_exports import IrExports, IrExportsLine
from .ir_module import IrModule, IrModuleCategory, IrModuleDependency
from .ir_ui_menu import IrUiMenu
from .report_layout import ReportLayout
from .report_paperformat import ReportPaperformat, PAPER_SIZES
from .res_groups_privilege import ResGroupsPrivilege
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
    'AvatarMixin',
    'ImageMixin',
    'IrExports',
    'IrExportsLine',
    'IrModuleCategory',
    'ReportLayout',
    'ResGroupsPrivilege',
    'IrUiMenu',
    'IrSequence',
    'ExportJob',
    'SiteSettings',
    'IrAutovacuum',
    'is_autovacuum',
    'IrDemo',
    'IrDemoFailure',
    'IrDemoFailureWizard',
    'IrProfile',
    'BaseEnableProfilingWizard',
    'IrAsset',
    'AssetPaths',
    'IrBinary',
    'IrFieldsConverter',
    'ReportPaperformat',
    'PAPER_SIZES',
]

from .checkout_attempt import CheckoutAttempt  # noqa: E402
