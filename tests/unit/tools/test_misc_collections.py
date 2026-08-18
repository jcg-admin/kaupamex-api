"""``tools.misc`` — las tres colecciones que el stdlib no cubre.

Fiel a ``odoo19c: odoo/tools/misc.py`` (``odoo-tools@622ddc2a``, LGPL-3).

Cada caso fija la propiedad **por la que el símbolo se portó** en vez de
resolverse con stdlib. No son tests de completitud: son la evidencia de que la
sustitución obvia no sirve, que es lo que ``porte-completo-no-parcial.md`` pide
declarar cuando se construye un mecanismo.
"""
import itertools

import pytest

from tools.misc import LastOrderedSet, OrderedSet, groupby

pytestmark = pytest.mark.unit


# -- OrderedSet (``odoo19c: :1057-1096``) ------------------------------------

def test_ordered_set_remembers_first_insertion_order():
    """«remembers the elements first insertion order» — y el `set` no.

    Es la propiedad que hace inviable la sustitución: ``_action_assign``
    acumula ahí los movimientos asignados y luego los escribe en bloque; con
    un `set` el orden de escritura cambiaría entre ejecuciones.
    """
    assert list(OrderedSet([3, 1, 2, 1])) == [3, 1, 2]


def test_ordered_set_keeps_the_first_position_on_reinsertion():
    """Re-insertar NO mueve: es lo que separa a ``OrderedSet`` de su hermano."""
    conjunto = OrderedSet([1, 2, 3])
    conjunto.add(1)
    assert list(conjunto) == [1, 2, 3]


def test_ordered_set_derives_the_set_operators_from_the_abc():
    """``MutableSet`` deriva ``|`` ``&`` ``-`` de los tres métodos abstractos.

    La fuente no los escribe, y por eso este caso los ejerce: si la clase base
    cambiara, el porte perdería operadores sin que nada más lo note.
    """
    a, b = OrderedSet([1, 2, 3]), OrderedSet([2, 3, 4])
    assert sorted(a & b) == [2, 3]
    assert sorted(a | b) == [1, 2, 3, 4]
    assert sorted(a - b) == [1]


def test_ordered_set_intersection_takes_several_operands():
    """``intersection`` es el único operador que la fuente sí escribe (``:1090``)."""
    conjunto = OrderedSet([1, 2, 3, 4])
    assert sorted(conjunto.intersection(OrderedSet([2, 3, 4]), OrderedSet([3, 4]))) == [3, 4]


def test_ordered_set_copy_does_not_share_the_underlying_map():
    """``copy`` clona el dict (``:1093-1096``); si lo compartiera, mutar una
    copia contaminaría el original."""
    original = OrderedSet([1, 2])
    copia = original.copy()
    copia.add(3)
    assert list(original) == [1, 2]
    assert list(copia) == [1, 2, 3]


def test_ordered_set_difference_update_removes_in_place():
    conjunto = OrderedSet([1, 2, 3, 4])
    conjunto.difference_update([2, 4, 99])          # el ausente no molesta
    assert list(conjunto) == [1, 3]


# -- LastOrderedSet (``odoo19c: :1098-1102``) --------------------------------

def test_last_ordered_set_moves_the_element_to_the_end_on_reinsertion():
    """Su única diferencia con el padre, y la razón de que sea una clase aparte."""
    conjunto = LastOrderedSet([1, 2, 3])
    conjunto.add(1)
    assert list(conjunto) == [2, 3, 1]


# -- groupby (``odoo19c: :1201-1210``) ---------------------------------------

def test_groupby_aggregates_elements_that_are_not_consecutive():
    """«aggregates all elements under the same key, not only consecutive ones».

    Ésta es la frase del docstring de la fuente, y es literalmente el motivo
    del porte.
    """
    assert dict(groupby([1, 2, 1, 2])) == {1: [1, 1], 2: [2, 2]}


def test_itertools_groupby_would_give_a_different_answer():
    """El control negativo: la sustitución obvia NO es equivalente.

    Sin este caso, el porte parecería redundante con el stdlib — y quien lo
    leyera en seis meses tendría razón en dudarlo.
    """
    del_stdlib = [(k, list(g)) for k, g in itertools.groupby([1, 2, 1, 2])]
    assert len(del_stdlib) == 4                     # corta en cada cambio
    assert len(list(groupby([1, 2, 1, 2]))) == 2    # agrupa por clave


def test_groupby_applies_the_key_function():
    """La clave sale de ``key``; sus consumidores le pasan tuplas de registros
    (ubicación, lote, paquete, dueño), que no tienen orden natural — por eso
    ordenar antes, como exigiría el stdlib, no es una opción."""
    agrupado = dict(groupby(['ab', 'ac', 'bd'], key=lambda s: s[0]))
    assert agrupado == {'a': ['ab', 'ac'], 'b': ['bd']}


def test_groupby_on_an_empty_iterable_is_empty():
    assert dict(groupby([])) == {}
