"""``Registry`` como clase — el Mapping y el ciclo de vida por base.

La referencia declara ``class Registry(Mapping[str, type[BaseModel]])`` con 43
metodos (``odoo19c: odoo/orm/registry.py:84-1186``). El archivo de aqui llevaba
el registro como funciones de modulo y su docstring lo justificaba: *"por eso
este archivo es un stub delgado documentado, no una reimplementacion"*. Eso es
declarar divergencia en vez de portar, que ``porte-completo-no-parcial.md``
prohibe.

Este es el tramo 1: lo que hace de ``Registry`` una clase — el singleton por
nombre de base, el ciclo de vida, y la mitad Mapping. Los casos se escribieron
antes del porte.

**El control que discrimina** es ``test_the_lock_is_reentrant``: ``new`` esta
decorado con ``@locked`` y llama a ``delete``, que tambien lo esta. Con un
``threading.Lock`` en vez de un ``RLock`` la segunda toma se bloquea y el caso
cuelga; con el ``RLock`` de la fuente pasa. Sin ese caso, un cerrojo mal
elegido no lo delataria ninguno de los otros.
"""
import threading
from collections.abc import Mapping

import pytest

from orm.registry import DummyRLock, Registry


class _Model:
    """Un doble de clase de modelo: lo que ``descendants`` mira, y nada mas."""

    def __init__(self, name, inherit_children=(), inherits_children=()):
        self._name = name
        self._inherit_children = set(inherit_children)
        self._inherits_children = set(inherits_children)


@pytest.fixture(autouse=True)
def clean_registries():
    """Cada caso arranca con el mapa vacio y lo deja vacio."""
    Registry.delete_all()
    yield
    Registry.delete_all()


class TestSingletonPerDatabase:
    """``Registry(db)`` devuelve el mismo objeto para el mismo nombre."""

    def test_the_same_name_yields_the_same_instance(self):
        assert Registry('alfa') is Registry('alfa')

    def test_two_names_yield_two_instances(self):
        assert Registry('alfa') is not Registry('beta')

    def test_the_empty_name_is_refused(self):
        with pytest.raises(AssertionError, match='Missing database name'):
            Registry('')

    def test_it_lands_in_the_shared_map(self):
        registry = Registry('alfa')
        assert Registry.registries['alfa'] is registry

    def test_the_map_is_capped_at_the_declared_size(self):
        """``registries`` es un LRU de 42, no un dict que crece sin freno."""
        for i in range(50):
            Registry(f'db{i}')
        assert len(Registry.registries) <= 42
        assert 'db49' in Registry.registries


class TestLifecycle:
    """``new``, ``delete`` y ``delete_all``."""

    def test_new_replaces_the_standing_instance(self):
        first = Registry('alfa')
        second = Registry.new('alfa')
        assert second is not first
        assert Registry('alfa') is second

    def test_delete_drops_only_its_own_name(self):
        alfa, beta = Registry('alfa'), Registry('beta')
        Registry.delete('alfa')
        assert 'alfa' not in Registry.registries
        assert Registry.registries['beta'] is beta
        assert Registry('alfa') is not alfa

    def test_deleting_an_absent_name_is_a_no_op(self):
        """La fuente pregunta antes de borrar: no levanta KeyError."""
        Registry.delete('nunca-existio')

    def test_delete_all_empties_the_map(self):
        Registry('alfa')
        Registry('beta')
        Registry.delete_all()
        assert len(Registry.registries) == 0

    def test_the_instance_loses_the_three_class_entry_points(self):
        """La fuente los anula en la instancia: ``new``, ``init``, ``registries``.

        No es limpieza — es que llamarlos desde la instancia ya construida es
        siempre un error, y quedan en ``None`` para que reviente ahi.
        """
        registry = Registry('alfa')
        assert registry.new is None
        assert registry.init is None
        assert registry.registries is None

    def test_a_built_registry_declares_itself_ready(self):
        """Lo que la fuente garantiza al SALIR de ``new`` (``:209-211``).

        El estado intermedio —``_init`` cierto, ``ready`` falso— no es
        observable desde ``Registry(db)``: para cuando la llamada vuelve,
        ``new`` ya lo cerro. ``loaded`` sigue en falso a proposito: lo enciende
        la carga del grafo de modulos, que es el tramo 3 de la tarea #342.
        """
        registry = Registry('alfa')
        assert registry.db_name == 'alfa'
        assert registry._init is False
        assert registry.ready is True
        assert registry.loaded is False

    def test_the_lock_is_reentrant(self):
        """El control: ``new`` toma el cerrojo y llama a ``delete``, que lo toma otra vez.

        Con ``threading.Lock`` esto cuelga. Que pase mide el ``RLock`` de la
        fuente, no la existencia de los metodos.
        """
        assert isinstance(Registry._lock, (threading.RLock().__class__, DummyRLock))
        terminado = []

        def work():
            Registry.new('alfa')
            terminado.append(True)

        hilo = threading.Thread(target=work)
        hilo.start()
        hilo.join(timeout=5)
        assert terminado == [True], 'new() se quedo esperando su propio cerrojo'


class TestMapping:
    """La mitad ``Mapping``: la interfaz de diccionario sobre ``models``."""

    def test_it_is_a_mapping(self):
        assert isinstance(Registry('alfa'), Mapping)

    def test_length_and_iteration_read_the_models(self):
        registry = Registry('alfa')
        registry.models.clear()
        registry['res.partner'] = _Model('res.partner')
        registry['res.users'] = _Model('res.users')
        assert len(registry) == 2
        assert sorted(registry) == ['res.partner', 'res.users']

    def test_getitem_returns_the_model(self):
        registry = Registry('alfa')
        model = _Model('res.partner')
        registry['res.partner'] = model
        assert registry['res.partner'] is model

    def test_getitem_raises_for_an_unknown_name(self):
        with pytest.raises(KeyError):
            Registry('alfa')['no.existe']

    def test_setitem_replaces(self):
        registry = Registry('alfa')
        registry['res.partner'] = _Model('res.partner')
        second = _Model('res.partner')
        registry['res.partner'] = second
        assert registry['res.partner'] is second

    def test_the_mixin_gives_get_keys_items_and_values(self):
        """No se declaran: los aporta ``Mapping`` sobre los cinco abstractos."""
        registry = Registry('alfa')
        registry.models.clear()
        model = _Model('res.partner')
        registry['res.partner'] = model
        assert registry.get('res.partner') is model
        assert registry.get('no.existe') is None
        assert list(registry.keys()) == ['res.partner']
        assert list(registry.values()) == [model]
        assert list(registry.items()) == [('res.partner', model)]

    def test_delitem_removes_the_model(self):
        registry = Registry('alfa')
        registry['x.custom'] = _Model('x.custom')
        del registry['x.custom']
        assert 'x.custom' not in registry

    def test_delitem_also_forgets_the_child_in_its_parents(self):
        """La fuente lo hace porque un modelo a medida puede heredar de mixins."""
        registry = Registry('alfa')
        registry.models.clear()
        parent = _Model('mail.thread', inherit_children={'x.custom'})
        registry['mail.thread'] = parent
        registry['x.custom'] = _Model('x.custom')
        del registry['x.custom']
        assert 'x.custom' not in parent._inherit_children

    def test_two_registries_do_not_share_their_models(self):
        alfa, beta = Registry('alfa'), Registry('beta')
        alfa.models.clear()
        beta.models.clear()
        alfa['solo.en.alfa'] = _Model('solo.en.alfa')
        assert 'solo.en.alfa' not in beta


class TestDescendants:
    """``descendants`` recorre los hijos por el eje que se le pida."""

    @pytest.fixture
    def registry(self):
        built = Registry('alfa')
        built.models.clear()
        built['base.mixin'] = _Model('base.mixin', inherit_children={'medio'})
        built['medio'] = _Model('medio', inherit_children={'hoja'})
        built['hoja'] = _Model('hoja')
        built['delegante'] = _Model('delegante', inherits_children={'delegado'})
        built['delegado'] = _Model('delegado')
        return built

    def test_it_includes_the_asked_model_itself(self, registry):
        assert 'hoja' in registry.descendants(['hoja'], '_inherit')

    def test_it_walks_the_inherit_axis_transitively(self, registry):
        assert set(registry.descendants(['base.mixin'], '_inherit')) == {
            'base.mixin', 'medio', 'hoja',
        }

    def test_it_walks_the_inherits_axis(self, registry):
        assert set(registry.descendants(['delegante'], '_inherits')) == {
            'delegante', 'delegado',
        }

    def test_one_axis_does_not_see_the_other(self, registry):
        """El control: pedir ``_inherit`` no arrastra a los delegados."""
        assert set(registry.descendants(['delegante'], '_inherit')) == {'delegante'}

    def test_both_axes_at_once(self, registry):
        registry['medio']._inherits_children.add('delegado')
        assert set(registry.descendants(['base.mixin'], '_inherit', '_inherits')) == {
            'base.mixin', 'medio', 'hoja', 'delegado',
        }

    def test_an_unknown_name_is_skipped_not_an_error(self, registry):
        assert set(registry.descendants(['no.existe', 'hoja'], '_inherit')) == {'hoja'}

    def test_it_does_not_repeat_a_model_reachable_twice(self, registry):
        registry['medio']._inherit_children.add('hoja')
        output = list(registry.descendants(['base.mixin'], '_inherit'))
        assert len(output) == len(set(output))

    def test_an_unknown_axis_is_refused(self, registry):
        with pytest.raises(AssertionError):
            registry.descendants(['hoja'], '_no_es_un_eje')
