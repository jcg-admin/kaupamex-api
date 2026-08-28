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
- ``properties_base_definition_mixin.py`` → ``PropertiesBaseDefinitionMixin``
  (propiedades de usuario cuyo esquema no cuelga de un padre).
- ``properties_base_definition.py`` → ``PropertiesBaseDefinition`` (ese
  esquema; FK **real** a ``ir.model.fields``).
- ``ir_exports.py`` → ``IrExports`` + ``IrExportsLine`` (exportaciones guardadas).
- ``report_layout.py`` → ``ReportLayout`` (diseños de documento impreso).
- ``res_groups_privilege.py`` → ``ResGroupsPrivilege`` (agrupa grupos en el form).
- ``res_company.py`` → ``ResCompany`` (entidad legal con sucursales; NO es
  ``company.Company``, el tenant L1).
- ``res_groups.py`` → ``ResGroups`` (grupos con implicación transitiva y
  disjuntos; NO reemplaza la autorización por capacidad de ``authz``).

- ``assetsbundle.py`` → el contrato de la URL versionada de un bundle y su
  algoritmo de versión (el empaquetado lo hace Webpack en ``ui``).
- ``ir_asset.py`` → ``IrAsset`` + ``AssetPaths`` (directivas sobre bundles; el
  resolutor de rutas contra manifests no aplica — lo hace Webpack en ``ui``).
- ``ir_autovacuum.py`` → ``IrAutovacuum`` + ``is_autovacuum`` (colector de los
  métodos ``@api.autovacuum``).
- ``ir_actions.py`` → los ocho modelos de la familia ``ir.actions.*``
  (ventana, URL, cliente, servidor, cierre, vista, todo).
- ``ir_actions_report.py`` → ``IrActionsReport`` (declaración del reporte;
  el motor de render es propio — libharu, ADR-017 — no wkhtmltopdf).
- ``ir_embedded_actions.py`` → ``IrEmbeddedActions`` (acciones embebidas en
  la vista de otro registro; cierra H-API-142).
- ``ir_model.py`` → las diez clases del registro reflejado (``Base``,
  ``Unknown``, ``IrModel``, ``IrModelFields``, ``IrModelInherit``,
  ``IrModelFieldsSelection``, ``IrModelConstraint``, ``IrModelRelation``,
  ``IrModelAccess``, ``IrModelData``).
- ``ir_mail_server.py`` → ``IrMailServer`` (registro de servidores SMTP
  salientes con prioridad y enrutado por remitente; el transporte sigue siendo
  ``django.core.mail`` vía ``addons/mail``).
- ``res_config.py`` → ``ResConfig`` + ``ResConfigSettings`` (motor de
  configuración por convención de nombre de campo; abstractos, sin tabla).
- ``ir_qweb.py`` → ``IrQweb`` + ``MALICIOUS_SCHEMES`` + ``keep_query``
  (vocabulario y primitivas de QWeb; el compilador NO se porta — este árbol
  renderiza en el cliente).
- ``ir_qweb_fields.py`` → los conversores ``ir.qweb.field.*`` (cómo se
  escribe un valor para que lo lea una persona; valen sin QWeb).
- ``ir_ui_view.py`` → ``IrUiView`` + ``IrUiViewCustom`` + ``ResetViewArchWizard``
  (registro de vistas y reglas de herencia; el combinador de XML no se porta).
- ``ir_http.py`` → ``IrHttp`` + ``slugify`` (utilidades de URL; el enrutado
  y el despacho los hace Django, y la autenticación ya está decidida).
- ``ir_rule.py`` → ``IrRule`` (reglas de registro: acceso por fila).
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
- ``ir_cron.py`` → ``IrCron`` (registro de horario + runner ``ir.cron``;
  ejecutado por el subcomando ``cron``).
- ``ir_default.py`` → ``IrDefault`` (valores por defecto de campo ``ir.default``).
- ``ir_filters.py`` → ``IrFilters`` (filtros de búsqueda guardados ``ir.filters``).
- ``ir_ui_menu.py`` → ``IrUiMenu`` (árbol de navegación ``ir.ui.menu``, podado
  por capacidad; vive en ``base`` igual que en la referencia).
- ``res_currency.py`` → ``ResCurrency`` (moneda ISO 4217).
- ``res_country.py`` → ``ResCountry`` + ``ResCountryState`` (geografía política).
- ``res_partner.py`` → ``ResPartner`` (el party: persona, empresa o dirección).
- ``res_users.py`` → ``ResUsers`` (credencial; delega identidad al partner).
- ``res_config.py`` → ``ResConfigSettings`` (el formulario de ajustes; su
  concreción vive en ``base_setup``, que es quien sirve la superficie).

Se reexporta todo aquí para preservar el contrato de import histórico
``from addons.base.models import SystemParameter, ResCurrency, ...``.
"""
from .timestamped_mixin import TimeStampedModel
from .hierarchy import _reject_hierarchy_cycle
from .append_only_mixin import AppendOnlyModel
from .soft_delete_mixin import (
    SoftDeleteModel,
    SoftDeleteQuerySet,
    SoftDeleteManager,
    AllObjectsManager,
)
from .image_mixin import ImageMixin
from .avatar_mixin import AvatarMixin
from .properties_base_definition import (
    PropertiesBaseDefinition,
    _clear_definition_cache,
)
from .properties_base_definition_mixin import PropertiesBaseDefinitionMixin
from .decimal_precision import DecimalPrecision
from .ir_config_parameter import (
    _DEFAULT_PARAMETERS,
    _PARAM_CACHE,
    _clear_cache,
    SystemParameter,
)
from .assetsbundle import (
    ANY_UNIQUE,
    AssetError,
    AssetNotFound,
    CompileError,
    bundle_checksum,
    bundle_name,
    bundle_version,
)
from .ir_asset import IrAsset, AssetPaths
from .ir_attachment import IrAttachment
from .ir_autovacuum import IrAutovacuum, is_autovacuum
from .ir_binary import IrBinary
from .ir_fields import IrFieldsConverter
from .ir_demo import IrDemo
from .ir_demo_failure import IrDemoFailure, IrDemoFailureWizard
from .ir_profile import IrProfile, BaseEnableProfilingWizard
from .ir_qweb import (
    IrQweb,
    QWebError,
    QWebErrorInfo,
    MALICIOUS_SCHEMES,
    VOID_ELEMENTS,
    keep_query,
)
from .ir_qweb_fields import (
    IrQwebField,
    IrQwebFieldDuration,
    IrQwebFieldFloat_Time,
    TIMEDELTA_UNITS,
    format_duration_digital,
    nl2br,
    nl2br_enclose,
)
from .ir_ui_view import (
    IrUiView,
    IrUiViewCustom,
    ResetViewArchWizard,
    VIEW_TYPE_CHOICES,
)
from .ir_http import (
    IrHttp,
    AUTH_METHODS,
    EXTENSION_TO_WEB_MIMETYPES,
)
from .ir_rule import IrRule
from .ir_embedded_actions import IrEmbeddedActions
from .ir_actions import (
    IrActionsActions,
    IrActionsActWindow,
    IrActionsActWindowClose,
    IrActionsActWindowView,
    IrActionsActUrl,
    IrActionsClient,
    IrActionsServer,
    IrActionsTodo,
)
# ir_cron delega su "que ejecutar" en IrActionsServer (_inherits): despues.
from .ir_cron import IrCron
from .ir_actions_report import IrActionsReport
from .ir_default import IrDefault
from .res_config import (
    ResConfig,
    ResConfigSettings,
    ConfigWarning,
)
from .ir_model import (
    Base,
    Unknown,
    IrModel,
    IrModelFields,
    IrModelInherit,
    IrModelFieldsSelection,
    IrModelConstraint,
    IrModelRelation,
    IrModelAccess,
    IrModelData,
    FIELD_TYPES,
    DJANGO_TYPE_TO_TTYPE,
)
from .ir_filters import IrFilters
from .ir_logging import IrLogging
from .ir_mail_server import (
    IrMailServer,
    MailDeliveryException,
    extract_rfc2822_addresses,
    is_ascii,
)
from .ir_exports import IrExports, IrExportsLine
from .ir_module import (IrModule, IrModuleCategory, IrModuleDependency,
                        IrModuleExclusion)
from .ir_ui_menu import IrUiMenu
from .report_layout import ReportLayout
from .report_paperformat import ReportPaperformat, PAPER_SIZES
from .res_groups_privilege import ResGroupsPrivilege
from .res_groups import ResGroups
from .company_setting import CompanySetting
from .res_company import ResCompany
from .ir_sequence import IrSequence
from .report_export_job import ExportJob
from .res_bank import ResBank, ResPartnerBank, sanitize_account_number
from .res_country import ResCountry, ResCountryState
from .res_country_group import ResCountryGroup
from .res_partner import ResPartner
from .res_users import ResUsers, ResUsersLog
from .res_device import ResDeviceLog
from .res_users_deletion import ResUsersDeletion
from .res_users_settings import ResUsersSettings
from .res_currency import ResCurrency, ResCurrencyRate

from .res_lang import ResLang

__all__ = [
    'TimeStampedModel',
    '_reject_hierarchy_cycle',
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
    'ResPartnerBank',
    'sanitize_account_number',
    'DecimalPrecision',
    'IrModule',
    'IrModuleDependency',
    'IrModuleExclusion',
    'AvatarMixin',
    'ImageMixin',
    'IrExports',
    'IrExportsLine',
    'IrModuleCategory',
    'ReportLayout',
    'ResGroupsPrivilege',
    'ResGroups',
    'CompanySetting',
    'ResCompany',
    'IrRule',
    'IrActionsActions',
    'IrActionsActWindow',
    'IrActionsActWindowClose',
    'IrActionsActWindowView',
    'IrActionsActUrl',
    'IrActionsClient',
    'IrActionsServer',
    'IrActionsTodo',
    'IrActionsReport',
    'IrQweb',
    'QWebError',
    'QWebErrorInfo',
    'MALICIOUS_SCHEMES',
    'VOID_ELEMENTS',
    'keep_query',
    'IrQwebField',
    'IrQwebFieldDuration',
    'IrQwebFieldFloat_Time',
    'TIMEDELTA_UNITS',
    'format_duration_digital',
    'nl2br',
    'nl2br_enclose',
    'IrUiView',
    'IrUiViewCustom',
    'ResetViewArchWizard',
    'VIEW_TYPE_CHOICES',
    'IrHttp',
    'AUTH_METHODS',
    'EXTENSION_TO_WEB_MIMETYPES',
    'PropertiesBaseDefinition',
    'PropertiesBaseDefinitionMixin',
    '_clear_definition_cache',
    'ANY_UNIQUE',
    'AssetError',
    'AssetNotFound',
    'CompileError',
    'bundle_checksum',
    'bundle_name',
    'bundle_version',
    'IrEmbeddedActions',
    'IrUiMenu',
    'IrSequence',
    'ExportJob',
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
    'Base',
    'Unknown',
    'IrModel',
    'IrModelFields',
    'IrModelInherit',
    'IrModelFieldsSelection',
    'IrModelConstraint',
    'IrModelRelation',
    'IrModelAccess',
    'IrModelData',
    'FIELD_TYPES',
    'DJANGO_TYPE_TO_TTYPE',
    'ResConfig',
    'ResConfigSettings',
    'ConfigWarning',
    'IrMailServer',
    'MailDeliveryException',
    'extract_rfc2822_addresses',
    'is_ascii',
]

from .checkout_attempt import CheckoutAttempt  # noqa: E402
