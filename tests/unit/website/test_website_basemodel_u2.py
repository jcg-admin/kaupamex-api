"""``settings.static.page`` sobre ``BaseModel``.

Modelo propio del L0 sin contraparte; su acceso sigue al de su análogo
``website.page``: ``odoo19c: addons/website/security/ir.model.access.csv:12``.
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
website-basemodel-u2.md``.

*Métrica:* la base de la clase, las filas de ACL de su modelo y la respuesta
del controlador público a un cliente sin usuario.
*Ciega a:* el efecto de la ACL en los controladores, que consultan por el
gestor de Django y no por el ORM (ver el diseño); y a los consumidores que
llegan por ``Website._search_with_fuzzy``, que mide el subconjunto derivado.
"""
from types import SimpleNamespace

import pytest
from django.db import DEFAULT_DB_ALIAS

from addons.base.models import IrModelAccess
from addons.website.models import StaticPage, StaticPageVersion
from modules.loading import load_data
from modules.module import get_manifest
from orm.environments import env, sudo
from orm.models import BaseModel

pytestmark = pytest.mark.django_db


def test_static_page_is_a_base_model():
    assert issubclass(StaticPage, BaseModel)


def test_only_the_designer_group_has_access():
    """La fila viene del CSV del manifiesto: se borra la que dejó una carga
    anterior y una instalación nueva la vuelve a crear."""
    with sudo():
        model = env().ref('website.model_settings_static_page')
        IrModelAccess.objects.filter(model_id_id=model.pk).delete()
        package = SimpleNamespace(name='website',
                                  manifest=get_manifest('website'))
        load_data({}, 'init', 'data', package, using=DEFAULT_DB_ALIAS)
        designer = env().ref('website.group_website_designer')
        rows = IrModelAccess.objects.filter(model_id_id=model.pk)
        assert [(row.group_id_id, row.perm_read, row.perm_write,
                 row.perm_create, row.perm_unlink) for row in rows] == [
            (designer.pk, True, True, True, True)]


def test_the_public_page_still_serves(api_client):
    with sudo():
        page = StaticPage.objects.create(slug='about', title='Acerca')
        StaticPageVersion.objects.create(
            page=page, version=1, content='<p>hola</p>',
            status=StaticPageVersion.STATUS_PUBLISHED,
        )
    response = api_client.get('/api/v2/config/pages/about/')
    assert response.status_code == 200
    assert response.data['slug'] == 'about'
