"""ACL de ``base`` — el rol de ``base/security/ir.model.access.csv``.

En la referencia los permisos de un addon son **dato**: un CSV por módulo que
el instalador carga en ``ir_model_access``
(``odoo19c: odoo/addons/base/security/ir.model.access.csv``, 146 filas). Este
puerto no tiene ese cargador, así que lo que allá instala el módulo aquí lo
siembra una **migración de datos** — el camino que este árbol ya usa para lo
que la referencia instala con el módulo (``0017`` países, ``0026`` idiomas,
``0027`` grupos).

**Dos entradas, un solo cuerpo**, como ``res_groups_data``: :func:`seed` sobre
los modelos vivos —la que ``tests/conftest.py`` re-aplica tras un ``flush``
transaccional (:ref:`h-api-337`)— y :func:`seed_base_acl` sobre los históricos,
que es la de la migración.

Qué se siembra, y por qué esas y no más
========================================

**Las filas del CSV cuyo modelo existe en este árbol, y ninguna más.** Las
demás nombran modelos que aún no están portados (``base.language.import``,
los asistentes de módulo…); sembrarlas crearía una fila de ``ir_model`` para
un modelo inexistente, que es dato falso, no dato adelantado.

**La lista de abajo se DERIVA, no se escribe.** La genera
``derive_base_acl.py`` (``probes/`` del banco
``orm-continuation-plan-20261103T095630``) desde el CSV: una fila entra si su
``model_id:id`` es el identificador externo de un modelo cargado (``model_``
más su ``_name`` con los puntos como guion bajo). Su cuenta la publica el
script al ejecutarse, no esta prosa: el docstring anterior decía *«23 de las
146»* y siguió diciéndolo mientras se portaban modelos, hasta que un recordset
nuevo denegó todo por una fila que faltaba (:ref:`h-api-1143`).

*Métrica:* filas del CSV cuyo ``model_id:id`` coincide con el de un modelo
cargado.
*Ciega a:* un modelo portado que declare su ``_name`` de otra forma que la
fuente — su fila se leería como "sin destino". Y ciega a la ACL de los otros
addons: cada uno siembra la suya, igual que sus reglas.

Los permisos van **verbatim del CSV**, con sus ceros
=====================================================

La fila global de ``ir.ui.view`` lleva los cuatro permisos en cero
(``ir.model.access.csv:35``: ``"…","model_ir_ui_view",,0,0,0,0``). Existe y no
concede nada. Es tentador leerla como un descuido y escribirla con
``perm_read=True`` —*«leer una vista lo puede todo el mundo»*—, y sería un
cambio de política disfrazado de corrección: en la fuente el renderizador de
vistas lee bajo elevación, no con el permiso del usuario.

Por eso se copian los cuatro enteros tal cual, y el control
``test_the_global_row_grants_nothing_not_even_read`` existe precisamente para
que un sembrador "arreglado" falle.

Lo que NO se porta, con su razón
=================================

- **El identificador externo de cada ACL.** La fuente lo guarda en
  ``ir.model.data`` para poder actualizar o borrar la fila al recargar el
  módulo. Aquí la clave es la terna ``(name, modelo, grupo)``: el CSV repite
  ``name`` con grupos distintos (``res_company group_user`` sale tres veces),
  así que el nombre solo no identifica una fila. **Nada resuelve una ACL por
  identificador externo** — medido: 0 consumidores. Los grupos SÍ lo llevan
  porque ``has_group`` los resuelve así
  (``res_groups_data.py``); replicar la plomería donde no hay quien la consulte
  sería carga sin lector.
"""

from django.apps import apps as _live_apps
from django.db import DEFAULT_DB_ALIAS

from addons.base.models.ir_model import (
    IrModel as _IrModel,
    IrModelAccess as _IrModelAccess,
    IrModelData as _IrModelData,
)
from addons.base.models.res_groups import ResGroups as _ResGroups

#: ``(nombre, label del modelo, identificador del grupo o None, permisos)``.
#: Los permisos son ``(read, write, create, unlink)``, copiados del CSV de la
#: referencia sin reinterpretar. ``None`` en el grupo = fila global.
_ACCESS = (
    (
        'decimal.precision configuration',
        'base.DecimalPrecision',
        'group_system',
        (1, 1, 0, 0),
    ),
    (
        'ir_attachment group_user',
        'base.IrAttachment',
        'group_user',
        (1, 1, 1, 1),
    ),
    (
        'ir_attachment group_portal_public',
        'base.IrAttachment',
        None,
        (0, 0, 0, 0),
    ),
    ('ir_cron group_cron', 'base.IrCron', 'group_system', (1, 1, 1, 1)),
    (
        'ir_cron_progress group_cron',
        'base.IrCronProgress',
        'group_system',
        (1, 1, 1, 1),
    ),
    (
        'ir_cron_trigger group_cron',
        'base.IrCronTrigger',
        'group_system',
        (1, 1, 1, 1),
    ),
    (
        'ir_model group_erp_manager',
        'base.IrModel',
        'group_erp_manager',
        (1, 1, 1, 1),
    ),
    (
        'ir_model_constraint group_erp_manager',
        'base.IrModelConstraint',
        'group_erp_manager',
        (1, 1, 0, 1),
    ),
    (
        'ir_model_relation group_erp_manager',
        'base.IrModelRelation',
        'group_erp_manager',
        (1, 1, 1, 1),
    ),
    ('ir_model_inherit nobody', 'base.IrModelInherit', None, (0, 0, 0, 0)),
    (
        'ir_model_access_group_erp_manager',
        'base.IrModelAccess',
        'group_erp_manager',
        (1, 1, 1, 1),
    ),
    (
        'ir_model_data group_erp_manager',
        'base.IrModelData',
        'group_erp_manager',
        (1, 1, 1, 1),
    ),
    (
        'ir_model_fields group_erp_manager',
        'base.IrModelFields',
        'group_erp_manager',
        (1, 1, 1, 1),
    ),
    (
        'ir_model_fields_selection group_erp_manager',
        'base.IrModelFieldsSelection',
        'group_erp_manager',
        (1, 1, 1, 1),
    ),
    ('ir_model_all', 'base.IrModel', 'group_user', (0, 0, 0, 0)),
    ('ir_model_data user', 'base.IrModelData', 'group_user', (0, 0, 0, 0)),
    ('ir_model_fields all', 'base.IrModelFields', 'group_user', (0, 0, 0, 0)),
    (
        'ir_model_fields_selection all',
        'base.IrModelFieldsSelection',
        'group_user',
        (0, 0, 0, 0),
    ),
    (
        'ir_module_category group_user',
        'base.IrModuleCategory',
        'group_erp_manager',
        (1, 0, 0, 0),
    ),
    (
        'ir_module_module group_user',
        'base.IrModule',
        'group_system',
        (1, 1, 1, 1),
    ),
    (
        'ir_module_module_dependency group_system',
        'base.IrModuleDependency',
        'group_system',
        (1, 1, 1, 1),
    ),
    (
        'ir_module_module_exclusion group_system',
        'base.IrModuleExclusion',
        'group_system',
        (1, 1, 1, 1),
    ),
    (
        'ir_rule group_erp_manager',
        'base.IrRule',
        'group_erp_manager',
        (1, 1, 1, 1),
    ),
    ('ir_sequence group_user', 'base.IrSequence', 'group_user', (1, 0, 0, 0)),
    (
        'ir_sequence group_system',
        'base.IrSequence',
        'group_system',
        (1, 1, 1, 1),
    ),
    (
        'ir_sequence_date_range group_user',
        'base.IrSequenceDateRange',
        'group_user',
        (1, 0, 0, 0),
    ),
    (
        'ir_sequence_date_range group_system',
        'base.IrSequenceDateRange',
        'group_system',
        (1, 1, 1, 1),
    ),
    ('ir_ui_menu group_user', 'base.IrUiMenu', 'group_user', (1, 0, 0, 0)),
    ('ir_ui_menu group_system', 'base.IrUiMenu', 'group_system', (1, 1, 1, 1)),
    ('ir_ui_view group_user', 'base.IrUiView', None, (0, 0, 0, 0)),
    ('ir_ui_view group_system', 'base.IrUiView', 'group_system', (1, 1, 1, 1)),
    (
        'ir_ui_view_custom_group_user',
        'base.IrUiViewCustom',
        'group_system',
        (1, 1, 1, 1),
    ),
    ('ir_default all', 'base.IrDefault', None, (0, 0, 0, 0)),
    ('ir_default group_user', 'base.IrDefault', 'group_user', (1, 1, 1, 1)),
    (
        'ir_default group_system',
        'base.IrDefault',
        'group_system',
        (1, 1, 1, 1),
    ),
    (
        'res_company group_erp_manager',
        'base.ResCompany',
        'group_erp_manager',
        (1, 1, 1, 1),
    ),
    (
        'res_company group_user',
        'base.ResCompany',
        'group_public',
        (1, 0, 0, 0),
    ),
    (
        'res_company group_user',
        'base.ResCompany',
        'group_portal',
        (1, 0, 0, 0),
    ),
    ('res_company group_user', 'base.ResCompany', 'group_user', (1, 0, 0, 0)),
    (
        'res_country group_user_all',
        'base.ResCountry',
        'group_public',
        (1, 0, 0, 0),
    ),
    (
        'res_country group_user_all',
        'base.ResCountry',
        'group_portal',
        (1, 0, 0, 0),
    ),
    (
        'res_country group_user_all',
        'base.ResCountry',
        'group_user',
        (1, 0, 0, 0),
    ),
    (
        'res_country_state group_user_all',
        'base.ResCountryState',
        'group_public',
        (1, 0, 0, 0),
    ),
    (
        'res_country_state group_user_all',
        'base.ResCountryState',
        'group_portal',
        (1, 0, 0, 0),
    ),
    (
        'res_country_state group_user_all',
        'base.ResCountryState',
        'group_user',
        (1, 0, 0, 0),
    ),
    (
        'res_country group_user',
        'base.ResCountry',
        'group_partner_manager',
        (1, 0, 0, 0),
    ),
    (
        'res_country_group_system',
        'base.ResCountry',
        'group_system',
        (1, 1, 1, 1),
    ),
    (
        'res_country_state group_user',
        'base.ResCountryState',
        'group_partner_manager',
        (1, 1, 1, 1),
    ),
    (
        'res_currency group_all',
        'base.ResCurrency',
        'group_public',
        (1, 0, 0, 0),
    ),
    (
        'res_currency group_all',
        'base.ResCurrency',
        'group_portal',
        (1, 0, 0, 0),
    ),
    ('res_currency group_all', 'base.ResCurrency', 'group_user', (1, 0, 0, 0)),
    (
        'res_currency_rate group_all',
        'base.ResCurrencyRate',
        'group_public',
        (1, 0, 0, 0),
    ),
    (
        'res_currency_rate group_all',
        'base.ResCurrencyRate',
        'group_portal',
        (1, 0, 0, 0),
    ),
    (
        'res_currency_rate group_all',
        'base.ResCurrencyRate',
        'group_user',
        (1, 0, 0, 0),
    ),
    (
        'res_currency group_system',
        'base.ResCurrency',
        'group_system',
        (1, 1, 1, 1),
    ),
    (
        'res_currency_rate group_system',
        'base.ResCurrencyRate',
        'group_system',
        (1, 1, 1, 1),
    ),
    (
        'res_groups group_erp_manager',
        'base.ResGroups',
        'group_erp_manager',
        (1, 1, 1, 1),
    ),
    ('res_groups group_user', 'base.ResGroups', 'group_user', (1, 0, 0, 0)),
    ('res_lang group_all', 'base.ResLang', 'group_public', (1, 0, 0, 0)),
    ('res_lang group_all', 'base.ResLang', 'group_portal', (1, 0, 0, 0)),
    ('res_lang group_all', 'base.ResLang', 'group_user', (1, 0, 0, 0)),
    ('res_lang group_user', 'base.ResLang', 'group_system', (1, 1, 1, 1)),
    (
        'res_partner group_public',
        'base.ResPartner',
        'group_public',
        (1, 0, 0, 0),
    ),
    (
        'res_partner group_portal',
        'base.ResPartner',
        'group_portal',
        (1, 0, 0, 0),
    ),
    (
        'res_partner group_partner_manager',
        'base.ResPartner',
        'group_partner_manager',
        (1, 1, 1, 1),
    ),
    ('res_partner group_user', 'base.ResPartner', 'group_user', (1, 0, 0, 0)),
    (
        'res_partner_bank group_user',
        'base.ResPartnerBank',
        'group_user',
        (1, 0, 0, 0),
    ),
    (
        'res_partner_bank group_partner_manager',
        'base.ResPartnerBank',
        'group_partner_manager',
        (1, 1, 1, 1),
    ),
    (
        'res_partner_category group_user',
        'base.ResPartnerCategory',
        'group_user',
        (1, 0, 0, 0),
    ),
    (
        'res_partner_category group_partner_manager',
        'base.ResPartnerCategory',
        'group_partner_manager',
        (1, 1, 1, 1),
    ),
    ('res_users all', 'base.ResUsers', 'group_public', (1, 0, 0, 0)),
    ('res_users all', 'base.ResUsers', 'group_portal', (1, 0, 0, 0)),
    ('res_users all', 'base.ResUsers', 'group_user', (1, 0, 0, 0)),
    (
        'res_users group_erp_manager',
        'base.ResUsers',
        'group_erp_manager',
        (1, 1, 1, 1),
    ),
    (
        'API keys access employees',
        'base.ResUsersApikeys',
        'group_user',
        (1, 0, 0, 0),
    ),
    (
        'API keys access portal',
        'base.ResUsersApikeys',
        'group_portal',
        (1, 0, 0, 0),
    ),
    ('ir_asset_group_system', 'base.IrAsset', 'group_system', (1, 1, 1, 1)),
    (
        'ir_actions_report_group_system',
        'base.IrActionsReport',
        'group_system',
        (1, 1, 1, 1),
    ),
    (
        'ir_actions_server_group_system',
        'base.IrActionsServer',
        'group_system',
        (1, 1, 1, 1),
    ),
    (
        'ir_actions_server_history_group_system',
        'base.IrActionsServerHistory',
        'group_system',
        (1, 1, 1, 0),
    ),
    ('res_bank_group_system', 'base.ResBank', 'group_system', (1, 1, 1, 1)),
    (
        'res_bank_group_partner_manager',
        'base.ResBank',
        'group_partner_manager',
        (1, 1, 1, 1),
    ),
    ('res_bank user', 'base.ResBank', 'group_user', (1, 0, 0, 0)),
    (
        'ir_config_parameter_system',
        'base.SystemParameter',
        'group_system',
        (1, 1, 1, 1),
    ),
    (
        'ir_actions_report_paperformat group_portal',
        'base.ReportPaperformat',
        'group_user',
        (1, 0, 0, 0),
    ),
    (
        'ir_actions_report_paperformat group_system',
        'base.ReportPaperformat',
        'group_system',
        (1, 1, 1, 1),
    ),
    (
        'access.server.action.history.wizard',
        'base.ServerActionHistoryWizard',
        'group_system',
        (1, 1, 1, 0),
    ),
    ('ir_profile', 'base.IrProfile', 'group_system', (1, 1, 1, 1)),
    (
        'access.base.enable.profiling.wizard',
        'base.BaseEnableProfilingWizard',
        'group_system',
        (1, 1, 1, 0),
    ),
)


def _group_by_xmlid(xmlid, using, IrModelData, ResGroups):
    """El grupo de ese identificador externo, o ``None`` si no está sembrado.

    Devolver ``None`` en vez de reventar es deliberado y **fail-closed**: una
    ACL cuyo grupo no existe queda sin sembrar, así que no concede nada. Lo
    contrario —sembrarla como global— la convertiría en un permiso para todos.
    """
    data = (
        IrModelData.objects.using(using)
        .filter(module='base', name=xmlid, model='base.ResGroups')
        .first()
    )
    if data is None:
        return None
    return ResGroups.objects.using(using).filter(pk=data.res_id).first()


def _seed(registry, IrModel, IrModelAccess, IrModelData, ResGroups, using):
    """El cuerpo, sobre los modelos que le den — idempotente por la terna
    ``(name, modelo, grupo)``.

    ``registry`` es de dónde sale la clase del modelo al que la fila da
    permiso: el registro **vivo** para :func:`seed` y el **histórico** de la
    migración para :func:`seed_base_acl`. Es el único sitio donde las dos
    entradas difieren en algo más que la clase del modelo a escribir, y por eso
    entra como parámetro en vez de resolverse dentro.
    """
    for name, label, group_xmlid, perms in _ACCESS:
        try:
            model_class = registry.get_model(label)
        except LookupError:
            continue
        group = None
        if group_xmlid is not None:
            group = _group_by_xmlid(group_xmlid, using, IrModelData, ResGroups)
            if group is None:
                continue
        model_row, _ = IrModel.objects.using(using).get_or_create(
            model=label,
            defaults={'name': model_class._meta.verbose_name or label},
        )
        read, write, create, unlink = perms
        IrModelAccess.objects.using(using).get_or_create(
            name=name,
            model_id=model_row,
            group_id=group,
            defaults={
                'perm_read': bool(read),
                'perm_write': bool(write),
                'perm_create': bool(create),
                'perm_unlink': bool(unlink),
            },
        )


def seed(using=DEFAULT_DB_ALIAS):
    """Sobre los modelos vivos — entrada del catálogo de tests."""
    return _seed(
        _live_apps, _IrModel, _IrModelAccess, _IrModelData, _ResGroups, using
    )


def seed_base_acl(apps, alias):
    """Sobre los modelos históricos — entrada de la migración."""
    return _seed(
        apps,
        apps.get_model('base', 'IrModel'),
        apps.get_model('base', 'IrModelAccess'),
        apps.get_model('base', 'IrModelData'),
        apps.get_model('base', 'ResGroups'),
        alias,
    )
