"""Los dos mecanismos que ``extend_model`` gana para portar ``sale/analytic.py``.

``selection_add=`` y ``indexes=`` son lo que un addon necesita para ampliar un
modelo **de otro addon** sin redeclararlo: el vocabulario de un campo y una
entrada del ``Meta``. La referencia los expresa como atributos del campo
(``selection_add=[...]``, ``index='btree_not_null'``); aquí el primero vive en
``choices`` y el segundo en ``Meta.indexes``, que pertenece al addon dueño.

Qué haría fallar cada caso — el criterio del sub-patrón D de
``metrica-decide-la-conclusion.md``:

``test_the_index_survives_model_state``
    Cae si ``add_meta_index`` deja de escribir en ``original_attrs``. Es **la**
    aserción que discrimina: sin ella el autodetector lee una lista vacía y
    propone borrar el índice en cada ``makemigrations``, con ``_meta.indexes``
    perfectamente poblado. Un test que sólo mirara ``_meta.indexes`` seguiría
    verde con el defecto puesto — sería un adorno, no una red.

``test_the_vocabulary_keeps_what_the_first_declarer_put``
    Cae si ``extend_selection_choices`` sustituye en vez de ampliar, que es
    exactamente el defecto que ``selection_add`` existe para impedir.

Los dos controles positivos del final miden el árbol vivo, no un modelo
fabricado: el índice parcial y el valor de vocabulario que ``sale`` cuelga hoy
sobre la familia ``analytic``.
"""
import pytest
from django.apps import apps
from django.db import models
from django.db.migrations.state import ModelState

from orm.model_classes import add_meta_index, extend_selection_choices

#: El modelo sobre el que se ejercitan los dos mecanismos. Es el mismo que
#: ``sale`` extiende de verdad, así que el test mide el camino real.
LINE_LABEL = ('analytic', 'AccountAnalyticLine')
APPLICABILITY_LABEL = ('analytic', 'AccountAnalyticApplicability')


@pytest.fixture
def analytic_line():
    return apps.get_model(*LINE_LABEL)


@pytest.fixture
def applicability():
    return apps.get_model(*APPLICABILITY_LABEL)


@pytest.fixture
def index_state_restored(analytic_line):
    """Devuelve ``_meta`` al estado exacto previo, la clave AUSENTE incluida.

    Restaurar con ``original_attrs['indexes'] = …`` sería la trampa: **crea**
    la clave que la guarda escribe, y con eso un control posterior que lea
    ``ModelState`` pasaría por la limpieza de su hermano en vez de por el
    mecanismo. Medido: con la guarda anulada, esa forma dejaba en pie
    ``test_sale_hangs_its_partial_index_on_the_analytic_line``, que existe
    justamente para caerse.
    """
    meta = analytic_line._meta
    previous_indexes = list(meta.indexes)
    had_the_key = 'indexes' in meta.original_attrs
    previous_value = meta.original_attrs.get('indexes')
    yield
    meta.indexes = previous_indexes
    if had_the_key:
        meta.original_attrs['indexes'] = previous_value
    else:
        meta.original_attrs.pop('indexes', None)


# === add_meta_index ===================================================


def test_the_index_lands_in_meta(analytic_line, index_state_restored):
    """La mitad débil: el índice aparece en ``_meta.indexes``.

    Se mide, pero no discrimina por sí sola — ver el caso siguiente.
    """
    index = models.Index(fields=['id'], name='probe_meta_only_idx')
    assert add_meta_index(analytic_line, index) is True
    assert 'probe_meta_only_idx' in {
        i.name for i in analytic_line._meta.indexes}


def test_the_index_survives_model_state(analytic_line,
                                       index_state_restored):
    """La mitad que discrimina: el autodetector tiene que verlo.

    ``ModelState.from_model`` sólo copia ``_meta.indexes`` cuando el nombre
    figura en ``_meta.original_attrs`` (``django/db/migrations/state.py:839``).
    Retirar esa escritura de ``add_meta_index`` hace caer **este** caso y
    ninguno de los otros.
    """
    index = models.Index(fields=['id'], name='probe_model_state_idx')
    add_meta_index(analytic_line, index)
    seen = ModelState.from_model(analytic_line).options.get('indexes', [])
    assert 'probe_model_state_idx' in {i.name for i in seen}, (
        'el autodetector no ve el índice: sin la escritura en '
        'original_attrs propondría borrarlo en cada makemigrations'
    )


def test_the_index_is_added_once_per_name(analytic_line,
                                         index_state_restored):
    """Idempotente por nombre: ``ready()`` puede correr dos veces."""
    index = models.Index(fields=['id'], name='probe_idempotent_idx')
    twin = models.Index(fields=['id'], name='probe_idempotent_idx')
    assert add_meta_index(analytic_line, index) is True
    assert add_meta_index(analytic_line, twin) is False
    how_many = sum(1 for i in analytic_line._meta.indexes
                  if i.name == 'probe_idempotent_idx')
    assert how_many == 1


# === extend_selection_choices =========================================


def test_the_vocabulary_keeps_what_the_first_declarer_put(applicability):
    """Amplía, no sustituye — es la promesa entera de ``selection_add``."""
    field = applicability._meta.get_field('business_domain')
    previous = list(field.choices)
    try:
        extend_selection_choices(
            applicability, 'business_domain', [('probe_value', 'Sonda')])
        values = {v for v, _ in field.choices}
        assert 'probe_value' in values
        for value, _label in previous:
            assert value in values, (
                f'{value} desapareció: ampliar no puede perder el vocabulario '
                'que declaró el addon dueño'
            )
    finally:
        field.choices = previous


def test_the_same_value_is_not_added_twice(applicability):
    """Idempotente por valor, y lo devuelto lo declara."""
    field = applicability._meta.get_field('business_domain')
    previous = list(field.choices)
    try:
        primera = extend_selection_choices(
            applicability, 'business_domain', [('probe_twice', 'Sonda')])
        segunda = extend_selection_choices(
            applicability, 'business_domain', [('probe_twice', 'Sonda')])
        assert primera == ['probe_twice']
        assert segunda == [], 'la segunda pasada no agrega nada'
        how_many = sum(1 for v, _ in field.choices if v == 'probe_twice')
        assert how_many == 1
    finally:
        field.choices = previous


def test_it_returns_only_what_it_actually_added(applicability):
    """Con un valor ya presente y uno nuevo, devuelve sólo el nuevo."""
    field = applicability._meta.get_field('business_domain')
    previous = list(field.choices)
    already_there = previous[0][0]
    try:
        added = extend_selection_choices(
            applicability, 'business_domain',
            [(already_there, 'Etiqueta ignorada'), ('probe_new', 'Sonda')])
        assert added == ['probe_new']
    finally:
        field.choices = previous


# === controles positivos del árbol vivo ===============================


def test_sale_hangs_its_partial_index_on_the_analytic_line(analytic_line):
    """El índice real que ``sale/models/analytic.py`` cuelga hoy.

    ≙ ``index='btree_not_null'`` del ``so_line`` de la fuente. Se mide por
    ``ModelState`` y no por ``_meta``, por la razón del caso que discrimina.
    """
    seen = ModelState.from_model(analytic_line).options.get('indexes', [])
    assert 'analytic_line_so_line_nn' in {i.name for i in seen}


def test_sale_adds_its_value_to_the_business_domain(applicability):
    """El valor real que ``sale`` suma hoy, junto a los del addon dueño."""
    field = applicability._meta.get_field('business_domain')
    values = {v for v, _ in field.choices}
    assert 'sale_order' in values
    assert {'general', 'invoice', 'bill'} <= values, (
        'los values que declaró analytic siguen ahí'
    )
