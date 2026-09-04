"""Tests de ``Base.onchange`` y ``RecordSnapshot`` — el recálculo de formulario
antes de guardar.

Adaptado de ``odoo19c: addons/web/models/models.py:1973-2195`` (``onchange``) y
``:2252-2360`` (``RecordSnapshot``). Los seis símbolos estaban declinados en la
cabecera de ``addons/web/models/models.py`` citando ``grep -rln
"_update_cache\\|field_computed\\|def modified(\\|_apply_onchange_methods"
src/orm/*.py src/addons/*/models/*.py`` → 0; hoy devuelve 1 y, sobre todo, el
árbol tiene ya ``@api.onchange`` (``orm/decorators.py:37``), ``NewId``,
``OriginMixin._origin`` y ``registry.field_depends``. Lo que faltaba era el
**despachador**, que es lo que estos casos ejercen (tarea #250).

Ningún caso toca la base: ``onchange`` opera sobre una instancia en memoria.
"""
import pytest

import api

from addons.crm.models.crm_stage import CrmStage
from addons.web.models.models import Base, RecordSnapshot
from orm import registry


@pytest.fixture(autouse=True)
def _reset_marked_methods():
    """Vacia el memo de metodo marcado antes y despues de cada caso.

    ``registry.onchange_methods`` memoiza por clase de modelo, igual que la
    fuente memoiza ``_onchange_methods`` en la clase (``odoo19c: odoo/orm/
    models.py:592``: *"optimization: memoize result on cls"*). Tres casos de
    aqui cuelgan un ``@api.onchange`` con ``monkeypatch``, que es una mutacion
    del registro en caliente — alla la haria observable ``_prepare_setup``
    reasignando la property (``model_classes.py:344-346``); aqui la hace
    observable su equivalente, :func:`~orm.registry.clear_marked_methods`.

    Vacia **tambien al salir**: ``monkeypatch`` deshace el ``setattr`` pero no
    el memo, y una entrada con el metodo del caso se filtraria al siguiente.
    """
    registry.clear_marked_methods()
    yield
    registry.clear_marked_methods()

_SPEC = {'name': {}, 'is_won': {}, 'sequence': {}}


def _stage(**kwargs):
    """Una etapa **sin guardar** — el registro virtual del formulario."""
    return CrmStage(**{'name': 'Nueva', 'is_won': False, 'sequence': 10, **kwargs})


# --- RecordSnapshot ---------------------------------------------------------

def test_snapshot_reads_every_field_of_the_spec():
    """El snapshot trae una entrada por campo pedido, y sólo ésas.

    Discrimina "lee la ficha entera" de "lee la especificación": leer de más
    haría que ``diff`` reportase campos que el formulario no muestra.
    """
    snapshot = RecordSnapshot(_stage(), _SPEC)

    assert set(snapshot) == {'name', 'is_won', 'sequence'}
    assert snapshot['sequence'] == 10


def test_snapshot_without_fetch_is_empty():
    """``fetch=False`` deja el snapshot vacío hasta que se le pida un campo.

    Discrimina el parámetro honrado del ignorado: la referencia lo usa en la
    primera llamada para no calcular campos de un registro que aún no existe.
    """
    snapshot = RecordSnapshot(_stage(), _SPEC, fetch=False)

    assert snapshot == {}
    snapshot.fetch('name')
    assert set(snapshot) == {'name'}


def test_has_changed_is_false_until_the_value_moves():
    """Sin tocar el registro no hay cambio; al tocarlo, sí.

    Discrimina comparar contra el registro de comparar contra sí mismo: un
    ``has_changed`` que devolviera siempre ``True`` haría que ``onchange``
    recorriese todos los campos en cada pasada.
    """
    record = _stage()
    snapshot = RecordSnapshot(record, _SPEC)

    assert snapshot.has_changed('name') is False
    record.name = 'Ganada'
    assert snapshot.has_changed('name') is True


def test_has_changed_is_true_for_a_field_never_fetched():
    """Un campo ausente del snapshot cuenta como cambiado.

    Paridad con la referencia (``:2282``). Discrimina "ausente = sin cambio"
    de "ausente = desconocido": con la primera lectura, un campo sembrado por
    un default nunca llegaría al cliente.
    """
    snapshot = RecordSnapshot(_stage(), _SPEC, fetch=False)

    assert snapshot.has_changed('name') is True


def test_diff_reports_only_the_field_that_moved():
    """El diff trae el campo cambiado y no los quietos.

    Discrimina diff de volcado: devolver la ficha entera obligaría al cliente
    a repintar campos que el usuario está editando.
    """
    record = _stage()
    before = RecordSnapshot(record, _SPEC)
    record.sequence = 99
    after = RecordSnapshot(record, _SPEC)

    assert after.diff(before) == {'sequence': 99}


def test_diff_with_force_reports_every_field():
    """Con ``force`` salen todos, hayan cambiado o no.

    Es el camino de la primera llamada (alta desde cero). Discrimina la
    bandera honrada de la ignorada: sin ella un alta llegaría vacía al
    cliente.
    """
    record = _stage()
    snapshot = RecordSnapshot(record, _SPEC)

    assert snapshot.diff(snapshot, force=True) == {
        'name': 'Nueva', 'is_won': False, 'sequence': 10}


def test_two_snapshots_of_different_records_are_not_equal():
    """La igualdad incluye el registro, no sólo los valores.

    Paridad con la referencia (``:2265-2266``), que mete el registro en la
    comparación a propósito. Discrimina comparar identidad de comparar
    contenido: dos etapas distintas con los mismos valores no son la misma.
    """
    spec = {'name': {}}
    one, other = _stage(), _stage()

    assert RecordSnapshot(one, spec) != RecordSnapshot(other, spec)
    assert RecordSnapshot(one, spec) == RecordSnapshot(one, spec)


# --- onchange ---------------------------------------------------------------

def test_onchange_with_an_unknown_field_returns_nothing():
    """Un campo que el modelo no declara aborta la llamada.

    Paridad con la referencia (``:2017-2018``). Discrimina el aborto del
    ``AttributeError``: el cliente puede mandar un nombre viejo tras un
    rename y eso no debe ser un 500.
    """
    assert Base.onchange(_stage(), {'no_existe': 1}, ['no_existe'], _SPEC) == {}


def test_onchange_collects_the_warning_of_the_registered_method():
    """``CrmStage._onchange_is_won`` está registrado y su aviso llega.

    Es el único caso que NO fabrica su propio método: prueba que el
    despachador encuentra los ``@api.onchange`` ya declarados en el árbol.
    Discrimina "despacha" de "no despacha" — sin el bucle, no hay aviso.
    """
    result = Base.onchange(_stage(), {'is_won': True}, ['is_won'], _SPEC)

    assert 'warning' in result
    assert result['warning']['type'] == 'dialog'
    assert 'etapa' in result['warning']['message'].lower()


def test_onchange_does_not_fire_a_method_of_another_field():
    """Cambiar ``sequence`` no dispara el ``@api.onchange('is_won')``.

    Discrimina el despacho por campo del despacho a ciegas: correr todos los
    métodos en cada tecla es exactamente lo que el decorador existe para
    evitar.
    """
    result = Base.onchange(_stage(), {'sequence': 3}, ['sequence'], _SPEC)

    assert 'warning' not in result


def test_onchange_returns_the_value_the_method_assigned(monkeypatch):
    """Un ``@api.onchange`` que escribe otro campo lo devuelve en ``value``.

    Discrimina "recoge el efecto" de "sólo recoge el retorno": la referencia
    aplica las asignaciones sobre el registro virtual y las saca por el diff
    de snapshots, no por lo que el método retorna.
    """
    @api.onchange('is_won')
    def _rename_when_won(self):
        if self.is_won:
            self.name = 'Ganada'

    monkeypatch.setattr(CrmStage, '_onchange_rename_when_won', _rename_when_won,
                        raising=False)
    registry.clear_marked_methods()

    result = Base.onchange(_stage(), {'is_won': True}, ['is_won'], _SPEC)

    assert result['value']['name'] == 'Ganada'
    assert 'sequence' not in result['value']


def test_onchange_does_not_echo_back_the_field_the_user_typed():
    """El campo que el cliente mandó no vuelve en ``value``.

    Paridad con la referencia: ``snapshot0`` se re-lee tras aplicar los
    cambios (``:2129-2130``). Discrimina el eco del diff real — un eco haría
    que el cliente repintase el campo bajo el cursor.
    """
    result = Base.onchange(_stage(), {'sequence': 42}, ['sequence'], _SPEC)

    assert result['value'] == {}


def test_first_call_returns_every_field_of_the_spec():
    """Con ``field_names`` vacío (alta desde cero) salen todos los campos.

    Discrimina la primera llamada de una normal: la normal devuelve sólo lo
    que cambió, y un alta con eso llegaría vacía.
    """
    result = Base.onchange(_stage(), {}, [], _SPEC)

    assert set(result['value']) == {'name', 'is_won', 'sequence'}


def test_the_source_record_is_not_mutated():
    """El onchange trabaja sobre un registro virtual, no sobre ``self``.

    Discrimina la copia de la escritura en sitio: mutar ``self`` dejaría el
    formulario con valores que el usuario no aceptó, y sin guardar.
    """
    record = _stage()

    Base.onchange(record, {'sequence': 42, 'name': 'Otra'}, ['sequence', 'name'], _SPEC)

    assert record.sequence == 10
    assert record.name == 'Nueva'


def test_two_warnings_are_merged_into_one_dialog(monkeypatch):
    """Dos avisos se concatenan bajo un título único.

    Paridad con la referencia (``:2189-2193``). Discrimina la fusión de
    quedarse con el último: perder un aviso es perder información que alguien
    escribió a propósito.
    """
    @api.onchange('is_won')
    def _second_warning(self):
        return {'warning': {'title': 'Otro', 'message': 'Segundo aviso'}}

    monkeypatch.setattr(CrmStage, '_onchange_second_warning', _second_warning,
                        raising=False)
    registry.clear_marked_methods()

    result = Base.onchange(_stage(), {'is_won': True}, ['is_won'], _SPEC)

    assert result['warning']['type'] == 'dialog'
    assert 'Segundo aviso' in result['warning']['message']
    assert result['warning']['message'].count('\n\n') >= 2


def test_recursive_pass_reaches_a_second_method(monkeypatch):
    """Un método que cambia ``name`` dispara el ``@api.onchange('name')``.

    Es el bucle ``while todo`` de la referencia (``:2157-2170``). Discrimina
    una pasada de varias: con una sola, el segundo método nunca corre.
    """
    @api.onchange('is_won')
    def _first(self):
        self.name = 'Intermedia'

    @api.onchange('name')
    def _second(self):
        if self.name == 'Intermedia':
            self.sequence = 77

    monkeypatch.setattr(CrmStage, '_onchange_first', _first, raising=False)
    monkeypatch.setattr(CrmStage, '_onchange_second', _second, raising=False)
    registry.clear_marked_methods()

    result = Base.onchange(_stage(), {'is_won': True}, ['is_won'], _SPEC)

    assert result['value']['sequence'] == 77


# --- el x2many del diff -----------------------------------------------------

def _line_snapshot(name):
    """Una línea de un x2many, fotografiada por su ``name``."""
    return RecordSnapshot(CrmStage(name=name), {'name': {}})


def test_x2many_diff_reports_the_remaining_ids_when_a_line_leaves():
    """Quitar una línea viaja como ``set`` con los ids que quedan.

    Discrimina la baja por omisión del silencio: sin el ``set``, el cliente
    no tendría cómo saber que la línea se fue.
    """
    spec = {'team_ids': {'fields': {'name': {}}}}
    record = _stage()
    before = RecordSnapshot(record, spec)
    before['team_ids'] = {1: _line_snapshot('Uno'), 2: _line_snapshot('Dos')}
    after = RecordSnapshot(record, spec)
    after['team_ids'] = {1: _line_snapshot('Uno')}

    assert after.diff(before) == {'team_ids': {'set': [1]}}


def test_x2many_diff_reports_the_inner_change_of_a_line_that_stays():
    """Cambiar el valor de una línea viaja como ``update`` por id.

    Discrimina el diff por línea del volcado del conjunto: reenviar los ids
    no diría qué cambió dentro de la línea que sigue ahí.
    """
    spec = {'team_ids': {'fields': {'name': {}}}}
    record = _stage()
    before = RecordSnapshot(record, spec)
    before['team_ids'] = {1: _line_snapshot('Uno')}
    after = RecordSnapshot(record, spec)
    after['team_ids'] = {1: _line_snapshot('Otro')}

    assert after.diff(before) == {'team_ids': {'update': {1: {'name': 'Otro'}}}}


def test_x2many_without_changes_is_not_reported():
    """Un x2many quieto no aparece en el diff.

    Discrimina el diff del volcado: la especificación lo pide, pero pedirlo
    no es haberlo cambiado.
    """
    spec = {'team_ids': {'fields': {'name': {}}}, 'name': {}}
    record = _stage()
    before = RecordSnapshot(record, spec)
    after = RecordSnapshot(record, spec)

    assert 'team_ids' not in after.diff(before)
