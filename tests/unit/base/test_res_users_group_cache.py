"""La memorización de ``_get_group_ids`` y su invalidador.

Porta ``odoo19c: odoo/addons/base/models/res_users.py`` (LGPL-3): allá
``_get_group_ids`` lleva ``@tools.ormcache('self.id')`` y su invalidador es
``_get_invalidation_fields`` (``:735-740``), que el ``write`` cruza contra las
claves escritas para decidir si purgar (``:641-643``).

Por qué la caché aquí NO es cosmética
--------------------------------------

Medido antes de construirla, sobre una cadena de implicación de cinco grupos:
``_has_group`` costaba **9 consultas** por llamada y **no amortizaba** — tres
llamadas, 27 consultas. La clausura se recorría entera cada vez, con una
consulta por nodo visitado. Y ``has_group`` lo llaman los addons de producto
(``hr``, ``account``, ``hr_recruitment``, ``auto_backup``, ``utm``…), así que
el camino es caliente.

*Métrica:* consultas capturadas con ``CaptureQueriesContext`` sobre una cadena
de 5 grupos, con ``LocMemCache`` (el backend de ``config.settings.testing``).
*Ciega a:* el costo en producción, donde el backend es ``DatabaseCache``: ahí
un acierto de caché cuesta **1 consulta**, no 0. La ganancia sigue siendo real
—de 9 a 1— pero este archivo no la mide.

El control que puede fallar
---------------------------

Anulando el invalidador —``_invalidate_group_ids`` con un ``return`` al
entrar— la suite pasa de **11 passed** a **5 failed, 6 passed**. Caen
exactamente los cinco que afirman que la pertenencia **cambia**: añadir un
grupo, quitarlo, reescribir el grafo de implicación, borrar un grupo y guardar
al usuario. Sobreviven los seis que miden otra cosa a propósito — el conjunto
de campos del invalidador, la memorización en sí, el usuario sin PK, la
identidad con ``all_group_ids``, la ruta de ``_has_group`` y el control
positivo de pertenencia.

Sin ese control, un verde no distinguiría «la caché se invalida» de «el test
no pregunta» — el sub-patrón D de ``metrica-decide-la-conclusion.md``.
"""

import pytest
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext

from addons.base.models.ir_model import IrModelData
from addons.base.models.res_groups import ResGroups
from addons.base.models.res_partner import ResPartner
from addons.base.models.res_users import ResUsers

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


def _make_user(login):
    partner = ResPartner.objects.create(name=login, email='')
    return ResUsers.objects.create(login=login, partner=partner)


def _make_chain(length, prefix):
    """Cadena de implicación: el último implica al penúltimo, y así hasta el
    primero. Devuelve ``(base, tip)``."""
    previous = None
    first = None
    for index in range(length):
        group = ResGroups.objects.create(name=f'{prefix}{index}')
        first = first or group
        if previous is not None:
            group.implied_ids.add(previous)
        previous = group
    return first, previous


def _xmlid(group, name):
    IrModelData.objects.update_or_create(
        module='pruebas', name=name,
        defaults={'model': type(group)._meta.label, 'res_id': group.pk},
    )
    return f'pruebas.{name}'


# --- el invariante del invalidador ------------------------------------------

def test_the_invalidation_fields_are_the_ones_the_reference_declares(db):
    """≙ ``_get_invalidation_fields`` (``odoo19c: :735-740``)."""
    fields = ResUsers._get_invalidation_fields()
    assert {'group_ids', 'active', 'lang', 'tz',
            'company_id', 'company_ids'} <= fields
    assert ResUsers._get_session_token_fields() <= fields


# --- la memorización --------------------------------------------------------

def test_the_second_call_does_not_touch_the_database(db):
    user = _make_user('memo@ejemplo.mx')
    _, tip = _make_chain(5, 'M')
    user.group_ids.add(tip)

    user._get_group_ids()
    with CaptureQueriesContext(connection) as queries:
        user._get_group_ids()
    assert len(queries) == 0


def test_a_user_without_pk_does_not_poison_the_cache(db):
    """Sin PK no hay clave por usuario: la fuente tampoco llena su ormcache
    para un registro nuevo (``:1096``, *"for new record don't fill the
    ormcache"*)."""
    assert ResUsers(login='sin-pk@ejemplo.mx')._get_group_ids() == []


def test_it_returns_the_same_set_as_all_group_ids(db):
    user = _make_user('identidad@ejemplo.mx')
    _, tip = _make_chain(4, 'I')
    user.group_ids.add(tip)
    esperado = set(user.all_group_ids.values_list('pk', flat=True))
    assert set(user._get_group_ids()) == esperado


# --- la invalidación, por cada disparador ----------------------------------

def test_adding_a_group_invalidates(db):
    user = _make_user('anade@ejemplo.mx')
    assert user._get_group_ids() == []
    grupo = ResGroups.objects.create(name='Contabilidad')
    user.group_ids.add(grupo)
    assert grupo.pk in user._get_group_ids()


def test_removing_a_group_invalidates(db):
    user = _make_user('quita@ejemplo.mx')
    grupo = ResGroups.objects.create(name='Almacen')
    user.group_ids.add(grupo)
    assert grupo.pk in user._get_group_ids()
    user.group_ids.remove(grupo)
    assert grupo.pk not in user._get_group_ids()


def test_rewriting_the_implication_graph_invalidates(db):
    """El grafo es compartido: su cambio invalida a TODOS los usuarios, no
    sólo al que se toca. Por eso el invalidador de grafo es un contador de
    generación y no una purga por usuario."""
    user = _make_user('grafo@ejemplo.mx')
    base_group = ResGroups.objects.create(name='Base')
    puente = ResGroups.objects.create(name='Puente')
    user.group_ids.add(puente)
    assert base_group.pk not in user._get_group_ids()

    puente.implied_ids.add(base_group)
    assert base_group.pk in user._get_group_ids()


def test_deleting_a_group_invalidates(db):
    user = _make_user('borra@ejemplo.mx')
    grupo = ResGroups.objects.create(name='Efimero')
    user.group_ids.add(grupo)
    assert grupo.pk in user._get_group_ids()
    grupo.delete()
    assert user._get_group_ids() == []


def test_saving_the_user_invalidates(db):
    """``active`` está en el conjunto del invalidador."""
    user = _make_user('guarda@ejemplo.mx')
    grupo = ResGroups.objects.create(name='Ventas')
    user.group_ids.add(grupo)
    user._get_group_ids()
    ResGroups.objects.filter(pk=grupo.pk).update(name='Ventas MX')
    user.active = False
    user.save(update_fields=['active', 'updated_at'])
    with CaptureQueriesContext(connection) as queries:
        user._get_group_ids()
    assert len(queries) > 0


# --- la ruta de _has_group --------------------------------------------------

def test_has_group_goes_through_the_memo(db):
    """≙ ``has_group`` (``:1096``): la fuente pregunta
    ``group_id in self._get_group_ids()``. Aquí igual — sólo queda la
    resolución del xmlid, que no es del conjunto de grupos."""
    user = _make_user('ruta@ejemplo.mx')
    base_group, tip = _make_chain(5, 'R')
    user.group_ids.add(tip)
    ext_id = _xmlid(base_group, 'grupo_base')

    assert user._has_group(ext_id) is True
    with CaptureQueriesContext(connection) as queries:
        user._has_group(ext_id)
    assert len(queries) <= 2


def test_a_group_that_does_not_imply_is_not_membership(db):
    """Control positivo: el memo no concede de más."""
    user = _make_user('ajeno@ejemplo.mx')
    _, tip = _make_chain(3, 'A')
    user.group_ids.add(tip)
    ajeno = ResGroups.objects.create(name='Ajeno')
    assert user._has_group(_xmlid(ajeno, 'grupo_ajeno')) is False
