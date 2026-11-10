"""``groups`` en el campo al leer y al escribir, contra ``odoo19c``.

``Field.__get__`` comprueba ``_has_field_access`` en cada lectura
(``odoo19c: odoo/orm/fields.py:1647-1651``), antes de mirar la caché: un
campo con ``groups`` no se lee aunque su valor ya esté cargado. El
escenario usa los modelos de prueba de la fuente
(``test_orm.model.some_access``, ``:1814-1830``) y dos usuarios: uno sin
grupos extra y otro con ``base.group_erp_manager``. La referencia corre el
mismo escenario en ``tests/fixtures/reference_field_groups.py``.

Aquí la lectura «cargada» es la fila que Django trae con todas sus
columnas: es la ruta rápida del descriptor, la que devolvía el valor antes
de comprobar ``groups``.

*Métrica:* el valor o la excepción de cada lectura.
Al escribir, la referencia rechaza igual por ``write`` que por asignación
directa (``Field.__set__`` → ``write``, ``models.py:4377-4382``).

*Ciega a:* los campos sin columna.
"""
import pytest
from django.contrib.auth import get_user_model
from django.db import transaction

from exceptions import AccessError
from orm.environments import env as current_env
from orm.environments import sudo, user_scope
from orm.registry import MODELS_BY_NAME
from tests.fixtures import reference_process

pytestmark = [pytest.mark.reference, pytest.mark.django_db]

FIELDS = ('a', 'd', 'e', 'g', 'h', 'i', 'j', 'k')
MODEL = 'test_orm.model.some_access'


def _group(xmlid):
    module, name = xmlid.split('.')
    data = MODELS_BY_NAME['ir.model.data'].objects.get(
        module=module, name=name)
    return MODELS_BY_NAME['res.groups'].objects.get(pk=data.res_id)


def _seed():
    G, A, IM = (MODELS_BY_NAME[name] for name in (
        'res.groups', 'ir.model.access', 'ir.model'))
    group = G.objects.create(name='field-groups')
    label = MODELS_BY_NAME[MODEL]._meta.label
    model = (IM.objects.filter(model=label).first()
             or IM.objects.create(model=label, name=MODEL))
    A.objects.create(name='some_access', model_id=model, group_id=group,
                     perm_read=True, perm_write=True, perm_create=True,
                     perm_unlink=True)
    users = {}
    for actor, extra in (('plain', ()), ('rich', ('base.group_erp_manager',))):
        user = get_user_model().objects.create_user(
            login=f'groups-{actor}', password=None, name=f'groups-{actor}')
        user.group_ids.add(group, *(_group(xmlid) for xmlid in extra))
        users[actor] = user.pk
    record = current_env()[MODEL].create({'a': 7})
    return {**users, 'record': record.id}


def _scenarios(ids):
    Model = MODELS_BY_NAME[MODEL]

    def loaded(name):
        return Model.objects.filter(pk=ids['record']).first()[name]

    result = []
    for actor in ('plain', 'rich'):
        for name in FIELDS:
            result.append((actor, f'{actor} browse {name}', lambda n=name:
                           current_env()[MODEL].browse(ids['record'])[n]))
            result.append((actor, f'{actor} loaded {name}',
                           lambda n=name: loaded(n)))

    def written(name):
        current_env()[MODEL].browse(ids['record']).write({name: 9})
        current_env().flush_all()
        return 'ok'

    def assigned(name):
        setattr(current_env()[MODEL].browse(ids['record']), name, 9)
        current_env().flush_all()
        return 'ok'

    for actor in ('plain', 'rich'):
        for name in FIELDS:
            result.append((actor, f'{actor} write {name}',
                           lambda n=name: written(n)))
            result.append((actor, f'{actor} assign {name}',
                           lambda n=name: assigned(n)))
    result.append(('plain', 'superuser browse d', lambda: current_env()[
        MODEL].browse(ids['record']).sudo().d))
    return result


class _Rollback(Exception):
    """Deshace el escenario: cada uno parte del mismo estado."""


def _ours():
    actor = get_user_model().objects.create_user(
        login='groups-root', password=None, name='groups-root')
    with user_scope(actor.pk), sudo():
        ids = _seed()
    result = {}
    for actor, label, read in _scenarios(ids):
        with user_scope(ids[actor]):
            current_env().invalidate_all()
            try:
                with transaction.atomic():
                    result[label] = repr(read())
                    raise _Rollback
            except _Rollback:
                # silent OK because la excepción sólo deshace el escenario:
                # el resultado ya quedó registrado antes de levantarla.
                pass
            except AccessError:
                # ``AccessError`` es aquí el alias de ``PermissionDenied``
                # (``src/exceptions.py``): se compara la clase, no el nombre.
                result[label] = 'AccessError'
            except Exception as error:
                # Cualquier otro rechazo se registra por su tipo.
                result[label] = type(error).__name__
    return result


@pytest.fixture(scope='module')
def reference_result():
    reference_process.require()
    return reference_process.run_script(
        reference_process.FIXTURES / 'reference_field_groups.py')


def test_the_reads_match_the_reference(reference_result):
    ours = _ours()
    assert list(ours) == list(reference_result)
    differences = {label: (reference_result[label], ours[label])
                   for label in ours if ours[label] != reference_result[label]}
    assert differences == {}


def test_the_reference_denies_and_grants(reference_result):
    """Control del escenario: sin ``groups`` aplicado, todo sería legible y
    la comparación pasaría vacía de contenido."""
    assert reference_result['plain loaded d'] == 'AccessError'
    assert reference_result['rich loaded d'] == '1'
    assert reference_result['plain browse i'] == '1'


def test_a_grouped_write_is_denied_as_a_write():
    """El tipo de excepción no distingue de dónde sale el rechazo: sin la
    comprobación de ``write``, ``save`` de Django lee la columna en
    ``pre_save`` y la comprobación de **lectura** rechaza igual. La fuente
    rechaza en ``write`` (``models.py:4377-4382``) con la operación
    ``write`` en el mensaje (``_check_field_access``, ``:3384``)."""
    actor = get_user_model().objects.create_user(
        login='groups-write-root', password=None, name='groups-write-root')
    with user_scope(actor.pk), sudo():
        ids = _seed()
    with user_scope(ids['plain']):
        with pytest.raises(AccessError) as error:
            current_env()[MODEL].browse(ids['record']).write({'d': 9})
    assert str(error.value).endswith('Operación: write')


def test_a_grouped_assignment_is_denied_as_a_write():
    """``record.d = 9`` entra en la fuente por ``Field.__set__`` →
    ``records.write`` y rechaza como escritura; aquí la rama de fila real de
    ``FieldDescriptor.__set__`` escribía sin comprobarlo y el rechazo llegaba
    de una lectura lateral."""
    actor = get_user_model().objects.create_user(
        login='groups-assign-root', password=None, name='groups-assign-root')
    with user_scope(actor.pk), sudo():
        ids = _seed()
    with user_scope(ids['plain']):
        with pytest.raises(AccessError) as error:
            setattr(current_env()[MODEL].browse(ids['record']), 'd', 9)
            current_env().flush_all()
    assert str(error.value).endswith('Operación: write')
