"""El arbol de disparo del recalculo — ``TriggerTree`` de la fuente.

Los disparadores de un campo F son un **arbol**: contiene los campos que
dependen de F junto con los campos a invertir para saber que registros hay que
recalcular. El docstring de la fuente lo dibuja
(``odoo19c: odoo/orm/registry.py:1201-1221``):

.. code-block:: text

                             [G]
                           X/   \\Y
                         [H]     [J]
                       W/
                     [I]

G depende de F; H de X.F; I de W.X.F; J de Y.F. Cuando F cambia en unos
registros: recalcular G en ellos, H en ``inverse(X, registros)``, I en
``inverse(W, inverse(X, registros))`` y J en ``inverse(Y, registros)``.

**No estaba en el arbol** — medido antes de portar: 0 archivos con
``TriggerTree`` en ``src/``, ``addons/`` y ``tests/``. Es maquinaria real, no
un ayudante: ``models.py`` de la fuente la consume en ``_modified_triggers``,
el camino por donde una escritura marca lo que hay que recalcular.

La clave del arbol es un ``Field``, pero **la anotacion no crea dependencia**:
la clase es un ``dict`` y no invoca nada del campo. Por eso se porta sin
esperar a ``Field``, que es el ciclo duro de siete que #217 midio.
"""
import pytest

from orm.registry import DummyRLock, TriggerTree


class _Field:
    """Un doble minimo: ``TriggerTree`` solo lo usa como clave y en su raiz."""

    def __init__(self, name, keep=True):
        self.name = name
        self.keep = keep

    def __repr__(self):
        return f'<{self.name}>'


class TestTheEmptyTree:
    """``__bool__`` — un arbol vacio es falso; con raiz o con hijos, cierto."""

    def test_a_tree_without_root_or_children_is_false(self):
        assert not TriggerTree()

    def test_a_tree_with_a_root_is_true(self):
        assert TriggerTree([_Field('G')])

    def test_a_tree_with_a_child_but_no_root_is_true(self):
        tree = TriggerTree()
        tree.increase(_Field('X'))
        assert tree

    def test_the_default_root_is_empty(self):
        assert TriggerTree().root == ()


class TestGrowingTheTree:
    """``increase`` — devuelve el subarbol de la clave, creandolo si falta."""

    def test_it_creates_the_subtree_on_first_call(self):
        tree = TriggerTree()
        x = _Field('X')
        subtree = tree.increase(x)
        assert isinstance(subtree, TriggerTree)
        assert tree[x] is subtree

    def test_it_returns_the_same_subtree_on_the_second_call(self):
        tree = TriggerTree()
        x = _Field('X')
        assert tree.increase(x) is tree.increase(x)

    def test_the_created_subtree_starts_empty(self):
        assert not TriggerTree().increase(_Field('X'))


class TestTheTreeOfTheDocstring:
    """El arbol que la fuente dibuja, construido y recorrido."""

    @pytest.fixture
    def tree(self):
        g, h, i, j = (_Field(n) for n in 'GHIJ')
        x, y, w = (_Field(n) for n in 'XYW')
        root = TriggerTree([g])
        root.increase(x).root = [h]
        root[x].increase(w).root = [i]
        root.increase(y).root = [j]
        return root, {'G': g, 'H': h, 'I': i, 'J': j, 'X': x, 'Y': y, 'W': w}

    def test_the_root_holds_the_direct_dependent(self, tree):
        root, f = tree
        assert root.root == [f['G']]

    def test_the_branch_of_x_holds_the_field_that_depends_on_x_f(self, tree):
        root, f = tree
        assert root[f['X']].root == [f['H']]

    def test_the_branch_of_w_under_x_holds_the_two_hop_dependent(self, tree):
        root, f = tree
        assert root[f['X']][f['W']].root == [f['I']]

    def test_depth_first_visits_every_node_once(self, tree):
        root, f = tree
        visited = list(root.depth_first())
        assert len(visited) == 4
        assert visited[0] is root

    def test_depth_first_yields_the_root_before_its_children(self, tree):
        root, f = tree
        visited = list(root.depth_first())
        assert visited.index(root) < visited.index(root[f['X']])
        assert visited.index(root[f['X']]) < visited.index(root[f['X']][f['W']])


class TestMerging:
    """``merge`` — funde arboles y filtra cada nodo con ``select``."""

    def test_two_roots_join_into_one(self):
        g, j = _Field('G'), _Field('J')
        merged = TriggerTree.merge([TriggerTree([g]), TriggerTree([j])])
        assert list(merged.root) == [g, j]

    def test_a_repeated_field_appears_once(self):
        g = _Field('G')
        merged = TriggerTree.merge([TriggerTree([g]), TriggerTree([g])])
        assert list(merged.root) == [g]

    def test_subtrees_under_the_same_key_merge_recursively(self):
        x, h, i = _Field('X'), _Field('H'), _Field('I')
        a, b = TriggerTree(), TriggerTree()
        a.increase(x).root = [h]
        b.increase(x).root = [i]
        merged = TriggerTree.merge([a, b])
        assert list(merged[x].root) == [h, i]

    def test_select_discards_the_fields_it_rejects(self):
        keep, drop = _Field('keep'), _Field('drop', keep=False)
        merged = TriggerTree.merge(
            [TriggerTree([keep, drop])], select=lambda field: field.keep)
        assert list(merged.root) == [keep]

    def test_a_subtree_left_empty_by_select_is_not_kept(self):
        x, drop = _Field('X'), _Field('drop', keep=False)
        tree = TriggerTree()
        tree.increase(x).root = [drop]
        merged = TriggerTree.merge([tree], select=lambda field: field.keep)
        assert x not in merged

    def test_merging_nothing_gives_an_empty_tree(self):
        assert not TriggerTree.merge([])


class TestItsShape:
    """El contrato de clase que la fuente declara."""

    def test_it_is_a_dict(self):
        assert isinstance(TriggerTree(), dict)

    def test_it_declares_its_slots(self):
        assert TriggerTree.__slots__ == ['root']

    def test_its_repr_shows_the_root_and_the_children(self):
        g, x = _Field('G'), _Field('X')
        tree = TriggerTree([g])
        tree.increase(x)
        rendered = repr(tree)
        assert 'TriggerTree' in rendered
        assert 'root=' in rendered
        assert '<G>' in rendered


class TestTheDummyLock:
    """``DummyRLock`` — el cerrojo nulo, para pruebas de RPC y de JS."""

    def test_acquiring_and_releasing_do_nothing(self):
        lock = DummyRLock()
        assert lock.acquire() is None
        assert lock.release() is None

    def test_it_works_as_a_context_manager(self):
        with DummyRLock():
            pass

    def test_it_is_reentrant(self):
        lock = DummyRLock()
        with lock:
            with lock:
                pass

    def test_it_does_not_swallow_an_exception(self):
        """Control discriminante: un cerrojo nulo no es un ``try`` mudo.

        ``__exit__`` devuelve ``None``, asi que la excepcion se propaga. Si
        alguien lo hiciera devolver cierto, este caso cae — y con el se
        perderia en silencio cualquier error dentro del bloque.
        """
        with pytest.raises(ValueError, match='se propaga'):
            with DummyRLock():
                raise ValueError('se propaga')
