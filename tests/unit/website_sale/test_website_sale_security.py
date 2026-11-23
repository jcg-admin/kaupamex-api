"""La seguridad de ``website_sale`` se carga por su manifiesto.

≙ ``odoo19c: addons/website_sale/security/`` (``ir.model.access.csv``: 66
filas, 35 con modelo y grupo en este árbol; ``res_groups.xml``: tres grupos
de función y el enlace de ``base.group_user``). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
website-sale-security-data.md``.

*Métrica:* las filas y los grupos con su XML-ID, y la lectura del catálogo
por un usuario público y uno de portal.
*Ciega a:* ``ir_rules.xml`` (sucesor ``website-sale-ir-rules-0397``): sin la
regla, el público lee también lo no publicado.
"""
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelData
from addons.product.models import ProductProduct, ProductTemplate
from exceptions import AccessError
from orm.environments import sudo
from tools.convert import convert_xml_import
from orm import registry

pytestmark = pytest.mark.django_db

GROUPS_FILE = (Path(__file__).resolve().parents[3]
               / 'addons/website_sale/security/res_groups.xml')
FEATURE_GROUPS = ('group_show_uom_price', 'group_product_price_comparison',
                  'group_product_feed')


@pytest.fixture
def superuser_env():
    """Estas pruebas miden la ACL: no corren como superusuario."""
    yield None


def _record(module, name):
    data = IrModelData.objects.get(module=module, name=name)
    return registry.model_by_key(data.model).objects.get(pk=data.res_id)


def _user(login, group):
    with sudo():
        user = get_user_model().objects.create_user(
            login=login, password=None, name=login)
    user.group_ids.add(group)
    return user


def test_the_acl_rows_and_feature_groups_carry_their_external_ids():
    data = IrModelData.objects.filter(module='website_sale')
    assert data.filter(model='ir.model.access').count() == 35
    assert set(FEATURE_GROUPS) <= set(data.filter(
        model='res.groups').values_list('name', flat=True))


def test_installing_the_groups_file_links_internal_users_to_delivery_address():
    """``base.group_user`` es de ``base`` y el archivo es ``noupdate``: el
    enlace se escribe al instalar (modo ``init``), no al actualizar — como en
    la referencia, que tampoco lo repone en un ``-u`` (``models.py:4112``)."""
    with sudo(), open(GROUPS_FILE, 'rb') as xmlfile:
        convert_xml_import('website_sale', xmlfile, mode='init')
    assert _record('account', 'group_delivery_invoice_address') in (
        _record('base', 'group_user').implied_ids.all())


@pytest.mark.parametrize('group', ['group_public', 'group_portal'])
def test_a_shop_visitor_reads_the_catalogue_but_does_not_write_it(group):
    user = _user(f'wss-{group}', _record('base', group))
    templates = ProductTemplate.objects.filter(
        pk=ProductTemplate.objects.create(name=f'Catálogo {group}').pk)
    templates.check_access('read', user=user)
    ProductProduct.objects.filter(
        product_tmpl_id__in=templates).check_access('read', user=user)
    with pytest.raises(AccessError):
        templates.check_access('write', user=user)
