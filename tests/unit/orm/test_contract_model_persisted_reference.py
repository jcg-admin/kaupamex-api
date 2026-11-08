"""Búsqueda de ``BaseModel`` con registros persistidos, contra ``odoo19c``.

La rejilla (``tests/fixtures/model_persisted_grid.py``) crea sus registros en
las dos bases: en la referencia con ``env['test_orm.category']`` en modo
``su``, sobre ``orm_refproc_test_orm``, y aquí con la clase del mismo
``_name`` bajo :func:`orm.environments.sudo`. Los dos lados corren como
superusuario para medir la búsqueda y no las reglas de acceso, que difieren
por construcción (DEC-11). Con la base de referencia que sólo trae ``base``
la referencia no conoce el modelo y la prueba falla, no se omite.

*Métrica:* el ``repr`` de cada paso, con los ids traducidos al nombre.
*Ciega a:* las reglas de acceso y de fila, que el modo superusuario salta; y
al orden sobre campos que no sean ``name``.
"""
import pathlib

import pytest
from django.apps import apps

from django.contrib.auth import get_user_model
from orm.domains import Domain
from orm.environments import sudo, user_scope
from tests.fixtures import model_persisted_grid, reference_process

pytestmark = [pytest.mark.reference, pytest.mark.django_db]

GRID = pathlib.Path(model_persisted_grid.__file__)
MODEL = 'test_orm.category'


@pytest.fixture(scope='module')
def reference_trace():
    reference_process.require()
    return reference_process.trace(GRID, MODEL, 'su')


def _ours():
    """La referencia ejecuta la traza como ``SUPERUSER_ID`` en modo ``su``
    (``reference_model_trace.py:67``), y su base trae ese usuario de los
    datos de ``base``. Este árbol no siembra usuarios (decisión registrada en
    ``res_groups_data.py``), así que la prueba crea su actor dentro de su
    transacción: sin él ``env.user`` es ``None`` y el autor por defecto de un
    mensaje queda vacío donde en la referencia no lo está."""
    model = next(model for model in apps.get_models()
                 if getattr(model, '_name', None) == MODEL)
    actor = get_user_model().objects.create_user(
        login='grid-root', password=None, name='Grid Root')
    # La migración ``test_orm/0034`` siembra ``ORM Precision``, pero una
    # prueba con ``transaction=True`` vacía las tablas al terminar y la
    # caché ``stable`` de ``precision_get`` sobrevive al rollback. Se
    # garantiza aquí, por ``save()``, que además vacía esa caché.
    apps.get_model('base', 'DecimalPrecision').objects.update_or_create(
        name='ORM Precision', defaults={'digits': 3})
    with user_scope(actor.pk), sudo():
        return model_persisted_grid.trace(Domain, model, MODEL)


def test_the_trace_matches_the_reference(reference_trace):
    ours = _ours()
    assert len(ours) == len(reference_trace)
    differences = [(theirs, mine) for theirs, mine
                   in zip(reference_trace, ours) if theirs != mine]
    assert differences == []


def test_the_grid_reads_its_own_rows(reference_trace):
    """La referencia devuelve las tres filas sembradas, en el orden pedido:
    un dominio que no las alcanzara haría pasar la comparación vacía."""
    ordered = next(line for line in reference_trace
                   if line.startswith('search_fetch ordered'))
    assert 'c-grandchild' in ordered and 'a-root' in ordered
    assert ordered.index('c-grandchild') < ordered.index('a-root')


def test_the_cycle_is_seen_by_the_reference(reference_trace):
    """Cerrado el ciclo, la referencia lo detecta: un ``False`` igual en los
    dos lados no probaría nada si el ``UPDATE`` no hubiera llegado."""
    assert 'has_cycle after True' in reference_trace
    assert 'has_cycle chain False' in reference_trace
