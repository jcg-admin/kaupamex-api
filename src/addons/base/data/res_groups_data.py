"""Siembra los 12 grupos de ``base`` con sus identificadores externos.

≙ ``odoo19c: odoo/addons/base/security/base_groups.xml`` (LGPL-3, copia con
atribución por DEC-KX-03). Es una data-migration por la misma razón que
``0017_seed_countries`` y ``0026_seed_langs``: este puerto no tiene el cargador
de archivos de datos de la referencia, así que lo que allá instala el módulo
aquí lo instala una migración.

**Qué desbloquea, y es lo único que la motiva.** ``ResUsers.has_group`` resuelve
el grupo por ``ir.model.data``; sobre una tabla sin filas devolvería ``False``
para todo — un mecanismo escrito e inerte, la misma forma de defecto que los
países tenían antes de :ref:`h-api-358`. Los consumidores que hoy citan
``base.group_user`` / ``base.group_system`` pasan a poder resolverlos.

Tres decisiones de forma, todas por diferencias declaradas del puerto
=====================================================================

1. **Las aristas ``implied_by_ids`` se graban del otro lado.** La fuente las
   declara en los dos sentidos (``group_no_one.implied_by_ids = [group_user,
   group_system]``) porque su ORM expone el mismo M2M leído al revés. Aquí
   ``implied_by_ids`` es el ``related_name`` de ``implied_ids``
   (``res_groups.py``): **una sola tabla**, ``res_groups_implied_rel``. Grabar
   ``A.implied_by_ids += B`` es literalmente grabar ``B.implied_ids += A``, y
   se hace así para no escribir sobre un reverso durante una migración.

2. **``user_type`` sustituye al conjunto disjunto por xmlid.** La fuente saca
   los grupos mutuamente excluyentes de tres identificadores fijos; este árbol
   lo declara en el registro (``ResGroups.USER_TYPE_*``), y ese es el motivo de
   que ``group_user`` / ``group_portal`` / ``group_public`` nazcan con tipo.
   La semántica es la misma; el docstring de ``res_groups.py`` lleva el porqué.

3. **``group_system.user_ids`` no se graba.** La fuente enlaza ``base.user_root``
   y ``base.user_admin``; este puerto **no siembra ningún usuario** — la empresa
   y el usuario inicial se declaran en config (``BOOTSTRAP_COMPANY_CODE``, con
   ``default=''``) y los crea ``kaupamex-bin company_create``. El enlace queda
   BLOQUEADO por ``base.user_root`` — no hay tal fila que enlazar, y fabricar un
   administrador desde una migración contradiría esa decisión.

Lo que esta migración NO siembra, y no por olvido
=================================================

Los grupos que citan los consumidores de otros addons — medidos con
``grep -rnoE "'[a-z_0-9]+\\.group_[a-z_0-9]+'" addons/ src/ --include=*.py``,
**9 identificadores distintos en 4 addons**: ``stock`` (4),
``website`` (3), ``uom`` (1) y ``sales_team`` (1). Ninguno se siembra aquí: su
módulo no es ``base``, y grabar una fila ``module='stock'`` desde la migración
de ``base`` pondría el catálogo de un addon en manos de otro. Cada uno queda
BLOQUEADO por ``addons/<addon>/migrations/`` — la siembra pertenece a quien
declara el grupo, una migración por addon.

Consecuencia mientras tanto, y es la correcta: ``has_group`` devuelve ``False``
para esos nueve. La mayoría son interruptores de ajustes (multi-ubicación,
multi-almacén, multi-sitio, editor restringido) que en la referencia nacen
apagados, así que el fail-closed coincide con el estado inicial de la fuente.
Los dos que **no** son interruptores —``stock.group_stock_manager`` y
``sales_team.group_sale_salesman``— autorizan de menos hasta que su addon
siembre: fail-closed también, pero conviene saber por qué se niega.

Métrica: registros del XML de la referencia sembrados aquí, por modelo —
``ir.module.category`` 1 de 1, ``res.groups.privilege`` 2 de 2, ``res.groups``
12 de 12.
Ciega a: que el grupo *signifique* algo. Esta migración crea las filas y el
grafo de implicación; qué autoriza cada grupo vive en ``ir.model.access`` /
``ir.rule``, y este árbol autoriza por capacidad (DEC-11). Sembrar el grupo no
cambia ninguna decisión de acceso por sí solo.
"""
from django.db import DEFAULT_DB_ALIAS

from addons.base.models.ir_model import IrModelData as _IrModelData
from addons.base.models.ir_module import IrModuleCategory as _IrModuleCategory
from addons.base.models.res_groups import ResGroups as _ResGroups
from addons.base.models.res_groups_privilege import (
    ResGroupsPrivilege as _ResGroupsPrivilege,
)


#: ``(nombre sin módulo, nombre visible, secuencia)`` — la única categoría que
#: ``base_groups.xml`` crea, y de la que cuelgan los dos privilegios.
MODULE_CATEGORY = ('module_category_master_data', 'Master Data', 1)

#: ``(nombre sin módulo, nombre visible)`` — ``base_groups.xml:11-19``.
PRIVILEGES = (
    ('res_groups_privilege_export', 'Export'),
    ('res_groups_privilege_contact', 'Contact'),
)

#: Un dict por grupo, en el orden del XML. ``implies`` lleva las aristas ya
#: normalizadas al sentido ``implied_ids`` (ver decisión 1 del docstring): la
#: clave dice "los miembros de este grupo pertenecen también a estos".
GROUPS = (
    {
        'name': 'group_erp_manager',
        'label': 'Access Rights',
        'implies': ('group_user',),
    },
    {
        'name': 'group_sanitize_override',
        'label': 'Bypass HTML Field Sanitize',
    },
    {
        'name': 'group_system',
        'label': 'Role / Administrator',
        'comment': 'Access to the settings to configure the apps',
        # Las dos primeras son ``implied_ids`` propias; las tres siguientes son
        # los ``implied_by_ids`` de group_no_one / group_allow_export /
        # group_partner_manager, leídos desde este lado.
        'implies': (
            'group_erp_manager',
            'group_sanitize_override',
            'group_no_one',
            'group_allow_export',
            'group_partner_manager',
        ),
    },
    {
        'name': 'group_user',
        'label': 'Role / User',
        'comment': 'Access to the home menu',
        'api_key_duration': 90.0,
        'user_type': 'internal',
        # ``group_no_one.implied_by_ids`` incluye a group_user.
        'implies': ('group_no_one',),
    },
    {'name': 'group_multi_company', 'label': 'Multi Companies'},
    {'name': 'group_multi_currency', 'label': 'Multi Currencies'},
    {'name': 'group_no_one', 'label': 'Technical Features'},
    {
        'name': 'group_allow_export',
        'label': 'Allowed',
        'privilege': 'res_groups_privilege_export',
    },
    {
        'name': 'group_partner_manager',
        'label': 'Creation',
        'privilege': 'res_groups_privilege_contact',
    },
    {
        'name': 'group_portal',
        'label': 'Role / Portal',
        'comment': (
            'Portal members have specific access rights (such as record rules '
            'and restricted menus). They usually do not belong to the usual '
            'Odoo groups.'
        ),
        'user_type': 'portal',
    },
    {
        'name': 'group_public',
        'label': 'Role / Public',
        'comment': (
            'Public users have specific access rights (such as record rules '
            'and restricted menus). They usually do not belong to the usual '
            'Odoo groups.'
        ),
        'user_type': 'public',
    },
    {'name': 'default_user_group', 'label': 'Default access for new users'},
)


def _xmlid_row(IrModelData, alias, name, record):
    """Graba (o repunta) la fila de ``ir.model.data`` de ``record``.

    Réplica del ``set_xmlid`` del modelo vivo, escrita aquí sobre el modelo
    **histórico**: una migración no ejecuta comportamiento de la app, que
    cambia bajo sus pies. ``noupdate=True`` como el XML de la referencia.
    """
    IrModelData.objects.using(alias).update_or_create(
        module='base', name=name,
        defaults={
            'model': type(record)._meta.label,
            'res_id': record.pk,
            'noupdate': True,
        },
    )


def _existing(IrModelData, model, alias, name):
    """El registro que ya designa ``base.<name>``, o ``None``."""
    row = IrModelData.objects.using(alias).filter(
        module='base', name=name).first()
    if row is None:
        return None
    return model.objects.using(alias).filter(pk=row.res_id).first()


def _seed(IrModelData, IrModuleCategory, ResGroupsPrivilege, ResGroups,
          alias):
    """Crea categoría, privilegios y grupos, y luego teje las implicaciones.

    Dos pases a propósito: una arista de implicación necesita sus dos extremos
    ya creados, y el XML de la referencia las declara mezcladas con los
    registros (su cargador resuelve los ``ref()`` al final por la misma razón).

    Idempotente por ``(module, name)`` de ``ir.model.data``, que es la clave
    única de esa tabla: un segundo pase repunta en vez de duplicar.
    """
    # --- Categoría ---
    name, label, sequence = MODULE_CATEGORY
    category = _existing(IrModelData, IrModuleCategory, alias, name)
    if category is None:
        category = IrModuleCategory.objects.using(alias).create(
            name=label, sequence=sequence)
    _xmlid_row(IrModelData, alias, name, category)

    # --- Privilegios ---
    privileges = {}
    for name, label in PRIVILEGES:
        privilege = _existing(IrModelData, ResGroupsPrivilege, alias, name)
        if privilege is None:
            privilege = ResGroupsPrivilege.objects.using(alias).create(
                name=label, category=category)
        privileges[name] = privilege
        _xmlid_row(IrModelData, alias, name, privilege)

    # --- Grupos (pase 1: las filas) ---
    groups = {}
    for spec in GROUPS:
        group = _existing(IrModelData, ResGroups, alias, spec['name'])
        if group is None:
            # ``sequence`` se deja nula: el XML de la referencia no la fija
            # para ninguno de los doce, y numerarlos aquí sería inventar un
            # orden que la fuente no declara.
            group = ResGroups.objects.using(alias).create(
                name=spec['label'],
                comment=spec.get('comment', ''),
                api_key_duration=spec.get('api_key_duration'),
                user_type=spec.get('user_type'),
                privilege=privileges.get(spec.get('privilege')),
            )
        groups[spec['name']] = group
        _xmlid_row(IrModelData, alias, spec['name'], group)

    # --- Grupos (pase 2: las aristas de implicación) ---
    for spec in GROUPS:
        implied = [groups[target] for target in spec.get('implies', ())]
        if implied:
            groups[spec['name']].implied_ids.add(*implied)


def seed(using=DEFAULT_DB_ALIAS):
    """Siembra sobre los modelos vivos — entrada del catálogo de tests.

    Está en ``_SEEDERS`` de ``tests/conftest.py`` por lo mismo que países e
    idiomas: un ``flush`` de un test transaccional borra las filas que sembró la
    migración, y ``django_migrations`` las sigue dando por aplicadas, así que sin
    esta entrada la sesión siguiente arranca sin grupos y ``has_group`` devuelve
    ``False`` para todo — el fallo aparece lejos de su causa (H-API-337).
    """
    return _seed(_IrModelData, _IrModuleCategory, _ResGroupsPrivilege,
                 _ResGroups, using)


def seed_base_groups(apps, alias):
    """Siembra sobre los modelos históricos — entrada de la migración.

    ``apps.get_model`` y no el modelo vivo porque ejecutar comportamiento de la
    app viva desde una migración la ata a un estado del código que cambia bajo
    sus pies. Mismo criterio que ``res_country_data.seed_countries``.
    """
    return _seed(
        apps.get_model('base', 'IrModelData'),
        apps.get_model('base', 'IrModuleCategory'),
        apps.get_model('base', 'ResGroupsPrivilege'),
        apps.get_model('base', 'ResGroups'),
        alias,
    )
