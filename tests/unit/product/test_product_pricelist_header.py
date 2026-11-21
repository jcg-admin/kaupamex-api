"""Cabecera de ``product.pricelist`` y los tres nombres de la fuente.

≙ ``odoo19c: addons/product/models/product_pricelist.py:10-14`` (cabecera),
``:36`` (``currency_id``), ``:43`` (``company_id``) y ``:49-56``
(``country_group_ids``). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-pricelist-header.md``.

*Métrica:* los atributos de clase, el nombre y la columna de cada campo, y
la tabla y las columnas del Many2many leídas en la base.
*Ciega a:* ``currency_id`` obligatorio con su valor por defecto y el hilo de
mensajes, que el diseño declara con su sucesor.
"""
import pytest

from orm.commands import Command
from django.db import connection

from addons.base.models.res_company import ResCompany
from addons.base.models.res_country_group import ResCountryGroup
from addons.product.models import ProductPricelist
from addons.sale.models.sale_order import pricelist_domain
from addons.base.models.res_currency import ResCurrency


def _pricelist_currency():
    """La moneda obligatoria de una tarifa
    (``odoo19c: addons/product/models/product_pricelist.py:36-41``)."""
    currency, _ = ResCurrency.objects.get_or_create(
        name='MXN', defaults={'symbol': '$'})
    return currency


pytestmark = pytest.mark.django_db

HEADER = {
    '_name': 'product.pricelist',
    '_inherit': ['mail.thread', 'mail.activity.mixin'],
    '_description': 'Pricelist',
    '_rec_names_search': ['name', 'currency_id'],
    '_order': 'sequence, id, name',
}


def test_the_header_is_the_reference():
    for name, value in HEADER.items():
        assert ProductPricelist.__dict__[name] == value


@pytest.mark.parametrize('name', ['currency_id', 'company_id'])
def test_the_many2one_keep_the_source_name_and_column(name):
    assert ProductPricelist._meta.get_field(name).column == name


def test_the_country_groups_use_the_source_table_and_columns():
    through = ProductPricelist._meta.get_field(
        'country_group_ids').remote_field.through._meta
    assert through.db_table == 'res_country_group_pricelist_rel'
    assert {f.column for f in through.local_fields} >= {
        'pricelist_id', 'res_country_group_id'}


def test_an_assigned_group_lives_in_the_source_table():
    group = ResCountryGroup.objects.create(name='Grupo pl-hdr')
    pricelist = ProductPricelist.objects.create(
        currency_id=_pricelist_currency(), name='Tarifa pl-hdr')
    pricelist.write({'country_group_ids': [Command.link(group.pk)]})
    with connection.cursor() as cr:
        cr.execute(
            'SELECT res_country_group_id FROM res_country_group_pricelist_rel'
            ' WHERE pricelist_id = %s', [pricelist.pk])
        assert cr.fetchall() == [(group.pk,)]


def test_the_sale_order_domain_admits_own_and_shared_pricelists():
    """≙ ``domain="['|', ('company_id','=',False), ('company_id','=',
    company_id)]"`` de ``pricelist_id`` (``odoo19c: sale/models/
    sale_order.py:189``)."""
    own_company = ResCompany.objects.create(code='pl-hdr-a', name='Propia')
    other_company = ResCompany.objects.create(code='pl-hdr-b', name='Ajena')
    own = ProductPricelist.objects.create(
        currency_id=_pricelist_currency(), name='pl-hdr propia',
        company_id=own_company)
    shared = ProductPricelist.objects.create(
        currency_id=_pricelist_currency(), name='pl-hdr compartida',
        company_id=None)
    ProductPricelist.objects.create(
        currency_id=_pricelist_currency(), name='pl-hdr ajena',
        company_id=other_company)

    class _Order:
        company = own_company

    admitted = ProductPricelist.objects.filter(
        pricelist_domain(_Order()), name__startswith='pl-hdr')
    assert set(admitted) == {own, shared}
