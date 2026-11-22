"""Los grupos y la ACL de ``website``, cargados del manifiesto.

≙ ``odoo19c: addons/website/security/website_security.xml:3-24``,
``:94-104`` y ``odoo19c: addons/website/security/ir.model.access.csv``.
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
website-security-groups.md``.

*Métrica:* los registros que ``ir.model.data`` nombra tras la instalación y
sus aristas de implicación.
*Ciega a:* el efecto de la ACL sobre los modelos de ``website``, que aún no
son ``BaseModel`` (unidad U1).
"""
from types import SimpleNamespace

import pytest
from django.db import DEFAULT_DB_ALIAS

from addons.base.models import IrModelAccess, IrModelData
from modules.loading import load_data
from modules.module import get_manifest
from orm.environments import env, sudo

pytestmark = pytest.mark.django_db

#: Las 16 filas del CSV de la fuente cuyos modelos existen aquí.
PORTED_ROWS = {
    'access_website_public_public', 'access_website_public_portal',
    'access_website_public_employee', 'access_website_designer',
    'access_website_menu_public', 'access_website_menu_portal',
    'access_website_menu_employee', 'access_website_menu_designer',
    'access_website_rewrite', 'access_website_rewrite_designer',
    'access_website_page_designer',
    'access_website_ir_ui_view_restricted_editor',
    'access_website_ir_ui_view_designer',
    'access_website_ir_asset_designer', 'access_website_route_designer',
    'access_website_configurator_feature_designer',
}


#: Filas propias del L0, sin contraparte en el CSV de la fuente: la de
#: ``settings.static.page`` sigue a su análogo ``website.page`` (U2,
#: ``designs/website-basemodel-u2.md``).
OWN_ROWS = {'access_settings_static_page_designer'}


@pytest.fixture
def installed_data():
    """Los datos del manifiesto como los deja una instalación nueva.

    ``load_data`` en ``mode='init'`` es el paso del ciclo de instalación.
    ``base.group_public`` y ``base.group_portal`` son ``noupdate``, y en modo
    de actualización su ``implied_ids`` no se reescribe, como en la fuente
    (``odoo19c: odoo/orm/models.py`` ``_load_records``: ``if not (update and
    d_noupdate)``). La base reutilizada ya instaló ``website``; la prueba
    mide la instalación, no la actualización.
    """
    package = SimpleNamespace(name='website',
                              manifest=get_manifest('website'))
    load_data({}, 'init', 'data', package, using=DEFAULT_DB_ALIAS)


def _group(xml_id):
    with sudo():
        return env().ref(xml_id)


def _implied(group):
    """Los ids que ``group`` implica: ``res.groups`` aún no es
    ``BaseModel`` y su ``implied_ids`` es un gestor de Django."""
    return set(group.implied_ids.values_list('pk', flat=True))


def test_the_designer_group_implies_the_restricted_editor():
    designer = _group('website.group_website_designer')
    implied = _implied(designer)
    assert _group('website.group_website_restricted_editor').pk in implied
    assert _group('base.group_sanitize_override').pk in implied
    assert designer.privilege_id == _group(
        'website.res_groups_privilege_website').pk


def test_system_implies_the_designer():
    system = _group('base.group_system')
    assert _group('website.group_website_designer').pk in _implied(system)


def test_public_implies_the_controller_expose_group(installed_data):
    expose = _group('website.website_page_controller_expose')
    for xml_id in ('base.group_public', 'base.group_portal'):
        assert expose.pk in _implied(_group(xml_id))


def test_the_acl_rows_of_the_ported_models_are_loaded():
    names = set(IrModelData.objects.filter(
        module='website', model='base.IrModelAccess').values_list(
            'name', flat=True))
    assert names == PORTED_ROWS | OWN_ROWS
    designer = IrModelAccess.objects.get(pk=IrModelData.objects.get(
        module='website', name='access_website_designer').res_id)
    assert designer.group_id.pk == _group('website.group_website_designer').pk
