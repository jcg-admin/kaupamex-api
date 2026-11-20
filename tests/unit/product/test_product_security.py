"""La seguridad de ``product`` se carga por su manifiesto, como en la fuente.

≙ ``odoo19c: addons/product/security/`` (``product_security.xml``: un
privilegio, tres grupos y seis reglas de empresa; ``ir.model.access.csv``:
38 filas, de las que 33 tienen modelo con XML-ID aquí),
``odoo19c: addons/product/models/product_document.py:9-14`` (la cabecera
de ``product.document``) y ``product_pricelist_item.py:31-32,170-183``
(``company_id`` y ``currency_id``, que la regla de empresa necesita).
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-security-data.md``.

*Métrica:* los grupos, las filas de ACL y las reglas con su XML-ID, y su
aplicación por ``check_access``/``_filtered_access`` sobre consultas de
``product.template``.
*Ciega a:* la aplicación implícita en ``_search``, que llega con la
adopción de ``BaseModel``
(``basemodel-adoption-product-attribute-value-0397``).
"""
import pytest
from django.apps import apps
from django.contrib.auth import get_user_model

from addons.base.models import IrModelData, ResCompany
from addons.product.models import (
    ProductDocument,
    ProductPricelist,
    ProductPricelistItem,
    ProductTemplate,
)
from exceptions import AccessError
from orm.environments import company_scope, sudo

pytestmark = pytest.mark.django_db

RULES = {
    'product_comp_rule', 'product_document_comp_rule',
    'product_pricelist_comp_rule', 'product_pricelist_item_comp_rule',
    'product_supplierinfo_comp_rule', 'product_combo_comp_rule',
}


def _record(module, name):
    data = IrModelData.objects.get(module=module, name=name)
    return apps.get_model(data.model).objects.get(pk=data.res_id)


def _user(login, company, *groups):
    with sudo():
        user = get_user_model().objects.create_user(
            login=login, password=None, name=login)
        user.company_ids.set([company])
        user.company_id = company
        user.save()
    for group in groups:
        user.group_ids.add(group)
    return user


@pytest.fixture
def company():
    return ResCompany.objects.create(code='psec-a', name='Empresa psec')


def test_product_document_declares_the_source_class_header():
    assert vars(ProductDocument)['_name'] == 'product.document'
    assert vars(ProductDocument)['_description'] == 'Product Document'
    assert vars(ProductDocument)['_order'] == 'sequence, name'
    assert vars(ProductDocument)['_inherits'] == {
        'ir.attachment': 'ir_attachment_id'}


def test_a_pricelist_item_stores_the_pricelist_company_and_currency(
        company):
    pricelist = ProductPricelist.objects.create(
        name='Tarifa psec', company_id=company,
        currency_id=company.currency)
    item = ProductPricelistItem.objects.create(pricelist_id=pricelist)
    assert item.company_id == company
    assert item.currency_id == company.currency


def test_a_pricelist_item_without_pricelist_takes_the_template_company(
        company):
    template = ProductTemplate.objects.create(
        name='Plantilla psec3', company_id=company)
    item = ProductPricelistItem.objects.create(
        applied_on='1_product', product_tmpl_id=template)
    assert item.company_id == company
    assert item.currency_id == company.currency


def test_the_manager_group_follows_the_source():
    manager = _record('product', 'group_product_manager')
    privilege = _record('product', 'res_groups_privilege_product')
    assert manager.privilege == privilege
    assert privilege.category_id == _record(
        'base', 'module_category_master_data').pk
    assert _record('base', 'group_system') in manager.implied_by_ids.all()
    assert _record('base', 'user_root') in manager.user_ids.all()
    assert _record('product', 'group_product_pricelist')
    assert _record('product', 'group_product_variant')


def test_the_acl_and_rules_carry_their_external_ids():
    data = IrModelData.objects.filter(module='product')
    assert data.filter(model='base.IrModelAccess').count() == 33
    assert set(data.filter(model='base.IrRule').values_list(
        'name', flat=True)) == RULES
    assert data.filter(model='base.IrModel',
                       name='model_product_document').exists()


def test_an_internal_user_reads_templates_but_does_not_write_them(company):
    user = _user('psec-internal', company, _record('base', 'group_user'))
    templates = ProductTemplate.objects.filter(
        pk=ProductTemplate.objects.create(name='Plantilla psec').pk)
    templates.check_access('read', user=user)
    with pytest.raises(AccessError):
        templates.check_access('write', user=user)


def test_a_product_manager_writes_templates(company):
    user = _user('psec-manager', company, _record('base', 'group_user'),
                 _record('product', 'group_product_manager'))
    templates = ProductTemplate.objects.filter(
        pk=ProductTemplate.objects.create(name='Plantilla psec2').pk)
    templates.check_access('write', user=user)
    templates.check_access('unlink', user=user)


def test_the_company_rule_hides_another_companys_template(company):
    other = ResCompany.objects.create(code='psec-b', name='Otra psec')
    user = _user('psec-reader', company, _record('base', 'group_user'))
    own = ProductTemplate.objects.create(name='Propia', company_id=company)
    shared = ProductTemplate.objects.create(name='Compartida')
    foreign = ProductTemplate.objects.create(name='Ajena', company_id=other)
    with company_scope(company.pk):
        allowed = ProductTemplate.objects.filter(
            pk__in=[own.pk, shared.pk, foreign.pk])._filtered_access(
                'read', user=user)
    assert set(allowed.values_list('pk', flat=True)) == {own.pk, shared.pk}
