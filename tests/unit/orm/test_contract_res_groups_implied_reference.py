"""Grupos implicados y pertenencia efectiva, contra ``odoo19c``.

Cuatro grupos propios —A implica B, B implica C, D aislado— y un usuario en
A. La referencia corre el mismo escenario en
``tests/fixtures/reference_res_groups_implied.py``: ``all_implied_ids`` y
``all_implied_by_ids`` son clausuras reflexivas (``res_groups.py:71-76,250,
265``), buscables (``:245-251``), y ``all_group_ids`` del usuario es la
clausura de sus grupos (``res_users.py:258,449``).

``res.groups`` y ``res.users`` no derivan aquí de ``BaseModel``: la
búsqueda por dominio se hace con ``orm.domains.to_q``, que traduce el mismo
dominio que ``search`` de la fuente.

*Métrica:* nombres de grupo ordenados por escenario.
*Ciega a:* los grupos de datos de ``base`` (se filtran por nombre) y la
recursión con ciclos.
"""
import pytest
from django.contrib.auth import get_user_model
from django.db import transaction

from orm.domains import to_q
from orm.environments import sudo, user_scope
from orm.registry import MODELS_BY_NAME
from tests.fixtures import reference_process

pytestmark = [pytest.mark.reference, pytest.mark.django_db]

NAMES = ('impl-A', 'impl-B', 'impl-C', 'impl-D')

#: Diferencias abiertas, con su motivo y su sucesor. Cada una debe seguir
#: siendo diferencia: cuando se cierre, la prueba exige retirarla de aquí.
OPEN = {}


def _seed():
    Groups = MODELS_BY_NAME['res.groups']
    c = Groups.objects.create(name='impl-C')
    b = Groups.objects.create(name='impl-B')
    b.implied_ids.set([c])
    a = Groups.objects.create(name='impl-A')
    a.implied_ids.set([b])
    d = Groups.objects.create(name='impl-D')
    user = get_user_model().objects.create_user(
        login='impl-user', password=None, name='impl-user')
    user.group_ids.add(a)
    return {'A': a.pk, 'B': b.pk, 'C': c.pk, 'D': d.pk, 'user': user.pk}


def _names(groups):
    return sorted(g.name for g in groups if g.name in NAMES)


def _scenarios(ids):
    Groups = MODELS_BY_NAME['res.groups']
    Users = MODELS_BY_NAME['res.users']

    def group(key):
        return Groups.objects.get(pk=ids[key])

    def user():
        return Users.objects.get(pk=ids['user'])

    def cut():
        group('B').implied_ids.clear()
        return {'A': _names(group('A').all_implied_ids),
                'user': _names(user().all_group_ids)}

    return [
        ('A all_implied', lambda: _names(group('A').all_implied_ids)),
        ('C all_implied_by', lambda: _names(group('C').all_implied_by_ids)),
        ('D all_implied', lambda: _names(group('D').all_implied_ids)),
        ('user all_group_ids', lambda: _names(user().all_group_ids)),
        ('search groups implying C', lambda: _names(Groups.objects.filter(
            to_q([('all_implied_ids', 'in', [ids['C']])], Groups)))),
        ('search users in C', lambda: Users.objects.filter(
            to_q([('id', '=', ids['user']),
                  ('all_group_ids', 'in', [ids['C']])], Users)).count()),
        ('after cutting B-C', cut),
    ]


class _Rollback(Exception):
    """Deshace el escenario: cada uno parte del mismo estado."""


def _ours():
    actor = get_user_model().objects.create_user(
        login='impl-root', password=None, name='impl-root')
    result = {}
    with user_scope(actor.pk), sudo():
        ids = _seed()
        for label, run in _scenarios(ids):
            try:
                with transaction.atomic():
                    result[label] = repr(run())
                    raise _Rollback
            except _Rollback:
                # silent OK because la excepción sólo deshace el escenario:
                # el resultado ya quedó registrado antes de levantarla.
                pass
            except Exception as error:
                # Cualquier otro rechazo se registra por su tipo.
                result[label] = type(error).__name__
    return result


@pytest.fixture(scope='module')
def reference_result():
    reference_process.require()
    return reference_process.run_script(
        reference_process.FIXTURES / 'reference_res_groups_implied.py')


def test_the_implied_groups_match_the_reference(reference_result):
    ours = _ours()
    assert list(ours) == list(reference_result)
    differences = {label: (reference_result[label], ours[label])
                   for label in ours
                   if label not in OPEN
                   and ours[label] != reference_result[label]}
    assert differences == {}


def test_the_open_differences_are_still_open(reference_result):
    """Una diferencia declarada abierta que ya coincide se retira de
    ``OPEN``: dejarla ahí ocultaría un cierre."""
    ours = _ours()
    for label, expected in OPEN.items():
        assert reference_result[label] == expected
        assert ours[label] != expected, label


def test_the_reference_closes_transitively(reference_result):
    """Control del escenario: sin la arista B-C la clausura sería corta."""
    assert reference_result['A all_implied'] == (
        "['impl-A', 'impl-B', 'impl-C']")
    assert reference_result['D all_implied'] == "['impl-D']"
