"""``mass_mailing`` sobre ``BaseModel``, con sus cabeceras y su seguridad.

≙ los cinco modelos de ``odoo19c: addons/mass_mailing/models/`` que tienen
puerto y los archivos de seguridad de su manifiesto. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
basemodel-adoption-mass-mailing.md``.

*Métrica:* el tipo y la cabecera de cada modelo, las filas cargadas con el
identificador externo del módulo y la ACL de un usuario interno.
*Ciega a:* los registros de los modelos sin puerto (asistentes, informe,
filtros, ``link.tracker``, ``mail.blacklist``) y la regla sobre
``mailing.contact.properties``, que el manifiesto declara.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelData
from addons.mass_mailing.models import (
    MailingContact, MailingList, MailingSubscription)
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope
from orm.models import BaseModel
from orm.registry import MODELS_BY_NAME
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.django_db

HEADERS = {
    'mailing.contact': ('Mailing Contact', 'name ASC, id DESC'),
    'mailing.list': ('Mailing List', 'create_date DESC'),
    'mailing.subscription': (
        'Mailing List Subscription', 'list_id DESC, contact_id DESC'),
    'mailing.trace': ('Mailing Statistics', 'create_date DESC'),
}


@pytest.mark.parametrize('name', sorted(HEADERS) + ['mailing.mailing'])
def test_each_model_is_a_base_model(name):
    assert issubclass(MODELS_BY_NAME[name], BaseModel)


@pytest.mark.parametrize('name', sorted(HEADERS))
def test_each_header_is_the_reference(name):
    model = MODELS_BY_NAME[name]
    description, order = HEADERS[name]
    assert model.__dict__['_description'] == description
    assert model.__dict__['_order'] == order


def test_the_groups_load():
    names = set(IrModelData.objects.filter(
        module='mass_mailing').values_list('name', flat=True))
    assert {'res_groups_privilege_email_marketing',
            'group_mass_mailing_user',
            'group_mass_mailing_campaign'} <= names


def test_the_acl_rows_that_resolve_load():
    """Las 25 de la fuente menos las 11 de modelos sin puerto."""
    assert IrModelData.objects.filter(
        module='mass_mailing', model='ir.model.access').count() == 14


def _subscriptions_by_list_age(older_first):
    """Dos listas con fechas distintas y un contacto en las dos; devuelve
    los ids de lista de ``search`` y los de las listas (vieja, nueva)."""
    with Environment(None, SUPERUSER_ID, {}) as environment:
        old = MailingList.objects.create(name='Vieja')
        new = MailingList.objects.create(name='Nueva')
        dates = ['2026-01-01T00:00:00Z', '2026-06-01T00:00:00Z']
        if not older_first:
            dates.reverse()
        MailingList.objects.filter(pk=old.pk).update(create_date=dates[0])
        MailingList.objects.filter(pk=new.pk).update(create_date=dates[1])
        contact = MailingContact.objects.create(email='o@x.com', name='O')
        MailingSubscription.objects.create(contact_id=contact, list_id=new)
        MailingSubscription.objects.create(contact_id=contact, list_id=old)
        found = environment['mailing.subscription'].search(
            [('contact_id', '=', contact.pk)])
        return [s.list_id.id for s in found], (old.pk, new.pk)


def test_the_subscription_order_reaches_its_list():
    """``_order`` nombra ``list_id`` y el campo lleva ese nombre.

    ≙ ``_order_field_to_sql`` (``odoo19c: odoo/orm/models.py:5296-5310``):
    un Many2one ordena por el ``_order`` del comodelo, invertido con
    ``DESC``. ``mailing.list`` ordena por ``create_date DESC``, así que
    ``list_id DESC`` pone primero la lista más vieja. El control cambia las
    fechas y el orden se invierte."""
    found, (old, new) = _subscriptions_by_list_age(older_first=True)
    assert found == [old, new]


def test_control_swapping_the_list_dates_swaps_the_order():
    found, (old, new) = _subscriptions_by_list_age(older_first=False)
    assert found == [new, old]


def test_an_internal_user_without_mailing_rights_cannot_read():
    group = MODELS_BY_NAME['res.groups'].objects.get(
        pk=IrModelData.objects.get(module='base', name='group_user').res_id)
    with sudo():
        user = get_user_model().objects.create_user(
            login='mailing-acl-internal', password=None, name='interno')
    user.group_ids.add(group)
    with user_scope(user.pk):
        lists = Environment(uid=user.pk)['mailing.list']
        with pytest.raises(AccessError):
            lists.check_access('read')
