"""``ir.filters`` portado a 19 sobre ``BaseModel``.

≙ ``odoo19c: odoo/addons/base/models/ir_filters.py:7-109``, con la ACL
(``ir.model.access.csv:114-117``) y las tres reglas
(``base_security.xml:74-104``). Diseño: ``designs/ir-filters-port-19.md``.
"""

from types import SimpleNamespace

import models
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrFilters, IrModelData, ResPartner
from addons.web.controllers.json import get_default_domain
from osv.expression import to_q
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope
from orm.registry import MODELS_BY_NAME

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

MODEL = 'res.partner'


def _user(login, *xmlids):
    with sudo():
        user = get_user_model().objects.create_user(
            login=login, password=None, name=login)
    for xmlid in xmlids:
        user.group_ids.add(MODELS_BY_NAME['res.groups'].objects.get(
            pk=IrModelData._xmlid_to_res_id(xmlid, raise_if_not_found=True)))
    return user


def _filter(name, users=(), **values):
    with sudo():
        record = Environment(uid=1)['ir.filters'].create({
            'name': name, 'model_id': MODEL, 'domain': '[]',
            'user_ids': [(6, 0, [u.pk for u in users])], **values})
    return record


def test_header_and_base():
    assert issubclass(IrFilters, models.BaseModel)
    assert IrFilters._name == 'ir.filters'
    assert IrFilters._description == 'Filters'
    assert IrFilters._order == 'model_id, name, id desc'


def test_an_employee_sees_their_own_and_the_shared_ones():
    me, other = (_user('flt-me', 'base.group_user'),
                 _user('flt-other', 'base.group_user'))
    mine = _filter('mine', [me])
    shared = _filter('shared')
    _filter('theirs', [other])
    with user_scope(me.pk):
        found = Environment(uid=me.pk)['ir.filters'].search([])
    assert set(found.ids) == {mine.id, shared.id}


def test_get_filters_respects_the_action_and_the_model():
    me = _user('flt-get', 'base.group_user')
    _filter('global')
    with user_scope(me.pk):
        rows = Environment(uid=me.pk)['ir.filters'].get_filters(MODEL)
    assert [row['name'] for row in rows] == ['global']
    assert {'name', 'is_default', 'domain', 'context', 'user_ids', 'sort',
            'embedded_action_id', 'embedded_parent_res_id'} <= set(rows[0])


def test_create_filter_drops_the_parent_res_id_without_embedded_action():
    with sudo():
        record = Environment(uid=1)['ir.filters'].create_filter({
            'name': 'no-embed', 'model_id': MODEL,
            'embedded_parent_res_id': 7})
    assert not record.embedded_parent_res_id


def test_copy_data_suffixes_the_name():
    record = _filter('original')
    with sudo():
        assert record.copy_data()[0]['name'] == 'original (copy)'


def test_an_invalid_domain_raises_value_error():
    record = _filter('bad', domain="[('name', '=', unknown_name)]")
    with pytest.raises(ValueError):
        record._get_eval_domain()


def test_write_on_a_foreign_filter_is_denied():
    me, other = (_user('flt-w-me', 'base.group_user'),
                 _user('flt-w-other', 'base.group_user'))
    theirs = _filter('theirs-w', [other])
    with user_scope(me.pk), pytest.raises(AccessError):
        theirs.with_user(me.pk).write({'name': 'hijacked'})


def test_the_web_default_domain_reads_get_filters():
    """≙ ``get_default_domain`` (``odoo19c: addons/web/controllers/
    json.py:270-277``): el primer filtro por defecto de ``get_filters``, con
    ``uid`` sustituido."""
    me = _user('flt-web', 'base.group_user')
    _filter('web-default', [me], is_default=True,
            domain="[('user_id', '=', uid)]")
    domain = get_default_domain(ResPartner, SimpleNamespace(pk=None), me)
    assert str(domain) == str(to_q([('user_id', '=', me.pk)]))


def test_a_portal_user_sees_only_their_own_filters():
    """``ir.filter: portal/public`` evalúa ``[('user_ids', 'in', user.ids)]``
    (``odoo19c: odoo/addons/base/security/base_security.xml:97-101``): un
    filtro compartido no es suyo."""
    portal = _user('flt-portal')
    with sudo():
        # Un usuario de portal no es interno: sólo su grupo, sin los de
        # ``_default_groups``, como ``base.template_portal_user_id``.
        portal.group_ids.set([MODELS_BY_NAME['res.groups'].objects.get(
            pk=IrModelData._xmlid_to_res_id('base.group_portal',
                                            raise_if_not_found=True))])
    mine = _filter('portal-mine', [portal])
    _filter('portal-shared')
    with user_scope(portal.pk):
        found = Environment(uid=portal.pk)['ir.filters'].search([])
    assert found.ids == [mine.id]
