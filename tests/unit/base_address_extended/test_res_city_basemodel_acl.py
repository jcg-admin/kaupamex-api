"""``res.city`` sobre ``BaseModel`` y con la ACL de la referencia.

≙ ``odoo19c: addons/base_address_extended/models/res_city.py:6`` (el modelo
es ``BaseModel``) y ``odoo19c: addons/base_address_extended/security/
ir.model.access.csv`` (dos filas: todo para ``base.group_partner_manager``,
lectura para ``base.group_user``). El CSV es copia fiel y lo carga el ciclo
de instalación desde el manifiesto. Diseño en ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/
basemodel-adoption-res-city.md``.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelAccess, IrModelData, ResCountry
from addons.base_address_extended.models.res_city import ResCity
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope
from orm.models import BaseModel
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db


def _user(login, *groups):
    with sudo():
        user = get_user_model().objects.create_user(
            login=login, password=None, name=login)
    for name in groups:
        user.group_ids.add(MODELS_BY_NAME['res.groups'].objects.get(
            pk=IrModelData.objects.get(module='base', name=name).res_id))
    return user


def _country():
    country, _ = ResCountry.objects.get_or_create(
        code='MX', defaults={'name': 'México'})
    return country


def test_res_city_is_a_base_model():
    assert issubclass(ResCity, BaseModel)


def test_the_acl_is_the_reference_csv_with_its_external_ids():
    xmlids = IrModelData.objects.filter(module='base_address_extended',
                                        model='base.IrModelAccess')
    assert sorted(xmlids.values_list('name', flat=True)) == [
        'access_res_city_group_all', 'access_res_city_group_user']
    row = IrModelAccess.objects.get(
        pk=xmlids.get(name='access_res_city_group_all').res_id)
    perms = (row.perm_read, row.perm_write, row.perm_create, row.perm_unlink)
    assert perms == (True, False, False, False)


def test_an_internal_user_reads_a_city_but_cannot_create_one():
    user = _user('city-acl-internal', 'group_user')
    country = _country()
    with sudo():
        city = ResCity.objects.create(name='Puebla', country_id=country)
    with user_scope(user.pk):
        cities = Environment(uid=user.pk)['res.city']
        assert cities.browse(city.pk).name == 'Puebla'
        with pytest.raises(AccessError):
            cities.create({'name': 'Tlaxcala', 'country_id': country.pk})


def test_a_contact_manager_creates_a_city():
    user = _user('city-acl-manager', 'group_user', 'group_partner_manager')
    country = _country()
    with user_scope(user.pk):
        cities = Environment(uid=user.pk)['res.city']
        city = cities.create({'name': 'Tlaxcala', 'country_id': country.pk})
        assert city.display_name == 'Tlaxcala'
