"""ACL de ``base`` — el rol de ``base/security/ir.model.access.csv``.

En la referencia los permisos de un addon son **dato**: un CSV por módulo que
el instalador carga en ``ir_model_access``
(``odoo19c: odoo/addons/base/security/ir.model.access.csv``, 146 filas). Este
puerto no tiene ese cargador, así que lo que allá instala el módulo aquí lo
siembra un ``seed()`` idempotente — el mismo patrón que ``base_security.py`` ya
usa para las record rules, registrado en ``tests/conftest.py`` (``_SEEDERS``).

Qué se siembra, y por qué esas y no más
========================================

**23 de las 146 filas del CSV.** La diferencia no es un recorte: son las filas
cuyo modelo **existe en este árbol**. Las otras 123 nombran modelos que aún no
están portados (``base.language.import``, ``ir.profile``, los asistentes de
módulo…); sembrarlas crearía una fila de ``ir_model`` para un modelo
inexistente, que es dato falso, no dato adelantado.

*Métrica:* filas del CSV cuyo ``model_id:id`` resuelve a un modelo cargado, con
``orm.registry.model_by_name``.
*Ciega a:* un modelo portado que declare su ``_name`` de otra forma que la
fuente — resolvería a ``None`` y su fila se leería como "sin destino". Y ciega
a la ACL de los otros addons: cada uno siembra la suya, igual que sus reglas.

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
  módulo. Aquí la clave natural es el ``name`` del CSV, que es único entre las
  23, y **nada resuelve una ACL por identificador externo** — medido: 0
  consumidores. Los grupos SÍ lo llevan porque ``has_group`` los resuelve así
  (``res_groups_data.py``); replicar la plomería donde no hay quien la consulte
  sería carga sin lector.
"""
from django.apps import apps
from django.db import DEFAULT_DB_ALIAS

from addons.base.models.ir_model import IrModel, IrModelAccess, IrModelData
from addons.base.models.res_groups import ResGroups

#: ``(nombre, label del modelo, identificador del grupo o None, permisos)``.
#: Los permisos son ``(read, write, create, unlink)``, copiados del CSV de la
#: referencia sin reinterpretar. ``None`` en el grupo = fila global.
_ACCESS = (
    ('ir_cron group_cron', 'base.IrCron', 'group_system', (1, 1, 1, 1)),
    ('ir_cron_progress group_cron', 'base.IrCronProgress', 'group_system',
     (1, 1, 1, 1)),
    ('ir_cron_trigger group_cron', 'base.IrCronTrigger', 'group_system',
     (1, 1, 1, 1)),
    ('ir_module_category', 'base.IrModuleCategory', 'group_erp_manager',
     (1, 0, 0, 0)),
    ('ir_module_module', 'base.IrModule', 'group_system', (1, 1, 1, 1)),
    ('ir_module_module_dependency', 'base.IrModuleDependency', 'group_system',
     (1, 1, 1, 1)),
    ('ir_sequence group_user', 'base.IrSequence', 'group_user', (1, 0, 0, 0)),
    ('ir_sequence group_system', 'base.IrSequence', 'group_system',
     (1, 1, 1, 1)),
    ('ir_ui_view group_user', 'base.IrUiView', None, (0, 0, 0, 0)),
    ('ir_ui_view group_system', 'base.IrUiView', 'group_system', (1, 1, 1, 1)),
    ('ir_ui_view_custom_group_user', 'base.IrUiViewCustom', 'group_system',
     (1, 1, 1, 1)),
    ('res_partner group_user', 'base.ResPartner', 'group_user', (1, 0, 0, 0)),
    ('res_partner group_portal', 'base.ResPartner', 'group_portal',
     (1, 0, 0, 0)),
    ('res_partner group_public', 'base.ResPartner', 'group_public',
     (1, 0, 0, 0)),
    ('res_partner group_partner_manager', 'base.ResPartner',
     'group_partner_manager', (1, 1, 1, 1)),
    ('res_partner_category group_user', 'base.ResPartnerCategory',
     'group_user', (1, 0, 0, 0)),
    ('res_partner_category group_partner_manager', 'base.ResPartnerCategory',
     'group_partner_manager', (1, 1, 1, 1)),
    ('res_users group_user', 'base.ResUsers', 'group_user', (1, 0, 0, 0)),
    ('res_users group_portal', 'base.ResUsers', 'group_portal', (1, 0, 0, 0)),
    ('res_users group_public', 'base.ResUsers', 'group_public', (1, 0, 0, 0)),
    ('res_users group_erp_manager', 'base.ResUsers', 'group_erp_manager',
     (1, 1, 1, 1)),
    ('res_users_apikeys group_user', 'base.ResUsersApikeys', 'group_user',
     (1, 0, 0, 0)),
    ('res_users_apikeys group_portal', 'base.ResUsersApikeys', 'group_portal',
     (1, 0, 0, 0)),
)


def _group_by_xmlid(xmlid, using):
    """El grupo de ese identificador externo, o ``None`` si no está sembrado.

    Devolver ``None`` en vez de reventar es deliberado y **fail-closed**: una
    ACL cuyo grupo no existe queda sin sembrar, así que no concede nada. Lo
    contrario —sembrarla como global— la convertiría en un permiso para todos.
    """
    data = IrModelData.objects.using(using).filter(
        module='base', name=xmlid, model='base.ResGroups').first()
    if data is None:
        return None
    return ResGroups.objects.using(using).filter(pk=data.res_id).first()


def seed(using=DEFAULT_DB_ALIAS):
    """Siembra la ACL de ``base`` — idempotente por el nombre de la fila."""
    for name, label, group_xmlid, perms in _ACCESS:
        try:
            model_class = apps.get_model(label)
        except LookupError:
            continue
        group = None
        if group_xmlid is not None:
            group = _group_by_xmlid(group_xmlid, using)
            if group is None:
                continue
        model_row, _ = IrModel.objects.using(using).get_or_create(
            model=label,
            defaults={'name': model_class._meta.verbose_name or label},
        )
        read, write, create, unlink = perms
        IrModelAccess.objects.using(using).get_or_create(
            name=name,
            defaults={
                'model_id': model_row,
                'group_id': group,
                'perm_read': bool(read),
                'perm_write': bool(write),
                'perm_create': bool(create),
                'perm_unlink': bool(unlink),
            },
        )
