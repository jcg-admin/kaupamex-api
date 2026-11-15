"""``_load_records_create`` aplica los comandos x2many de un ``Many2many``.

≙ ``odoo19c: odoo/orm/models.py:5102-5106``: ``_load_records_create`` es
``self.create(vals_list)``, y ``create`` interpreta los triples de ``Command``
del lado directo (``Many2many.write_real``). Aquí ``_load_records_write`` ya
los aplicaba (``_pop_many2many_values``) y ``_load_records_create`` no: el
primer registro ``res.groups`` de ``hr/security/hr_security.xml`` con
``implied_ids`` moría con *Direct assignment to the forward side of a
many-to-many set is prohibited*. Diseño: ``designs/module-install-cycle.md``,
L4c.
"""
import pytest

from addons.base.models import IrModelData, ResGroups
from orm.environments import sudo

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser(db):
    with sudo():
        yield


def _group_user():
    return IrModelData.ref('base.group_user')


def test_set_replaces_the_implied_groups():
    [group] = ResGroups._load_records_create([{
        'name': 'Carga con SET',
        'implied_ids': [(6, 0, [_group_user().pk])],
    }])
    assert list(group.implied_ids.all()) == [_group_user()]


def test_link_adds_an_implied_group():
    [group] = ResGroups._load_records_create([{
        'name': 'Carga con LINK',
        'implied_ids': [(4, _group_user().pk)],
    }])
    assert list(group.implied_ids.all()) == [_group_user()]


def test_a_plain_id_list_is_a_set():
    [group] = ResGroups._load_records_create([{
        'name': 'Carga con lista',
        'implied_ids': [_group_user().pk],
    }])
    assert list(group.implied_ids.all()) == [_group_user()]


def _group_system():
    return IrModelData.ref('base.group_system')


def test_link_on_the_reverse_side_adds_the_implying_group():
    """En la fuente ``implied_by_ids`` es un ``Many2many`` escribible sobre la
    misma tabla con las columnas invertidas (``res_groups.py:197-199``).
    ``account/security/account_security.xml`` lo escribe con
    ``Command.link(ref('base.group_system'))``."""
    [group] = ResGroups._load_records_create([{
        'name': 'Carga con LINK inverso',
        'implied_by_ids': [(4, _group_system().pk, 0)],
    }])
    assert list(group.implied_by_ids.all()) == [_group_system()]
    assert group in _group_system().implied_ids.all()


def test_the_reverse_side_is_written_on_an_existing_record():
    [group] = ResGroups._load_records_create([{'name': 'Inverso existente'}])
    group._load_records_write({
        'implied_by_ids': [(4, _group_system().pk, 0)],
    })
    assert list(group.implied_by_ids.all()) == [_group_system()]
