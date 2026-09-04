"""Tests — los seis simbolos de nivel superior de ``odoo/orm/fields.py``.

Contrato adaptado de ``odoo19c: odoo/orm/fields.py:35-90``. Son los que el
censo de la tarea #209 midio ausentes, con su veredicto TRAE o CONSTRUYE en
``docs: …/analisis-censo-orm-referencia-trae-o-construye.rst``.

Que haria fallar a cada control
--------------------------------

``TestResolveMro.test_it_stops_at_the_first_value_that_fails_the_predicate``
    El eje del contrato, y la parte que una implementacion ingenua se salta:
    la fuente **corta**, no filtra. Lo haria fallar un ``continue`` donde va un
    ``break`` — y con ``continue`` los otros casos de esa clase pasarian igual.

``TestResolveMro.test_a_class_that_declares_none_is_not_confused_with_absence``
    CONTROL del centinela. Sin el, ``dict.get(name)`` devolveria ``None`` para
    los dos casos y nadie lo notaria: el resultado se ve igual de plausible.

``TestIrModels.test_the_seven_are_the_ones_the_reference_names``
    CONTROL POSITIVO contra la fuente: la tupla es data, y una data que nadie
    compara con su origen se desactualiza en silencio.

``TestGlobalSeq.test_it_does_not_start_a_second_numbering``
    CONTROL de la divergencia declarada: el contador es el de Django, no uno
    nuestro. Lo haria fallar declarar un ``itertools.count()`` propio — que
    pasaria el caso de monotonia igual de bien.

``TestDetermine.test_a_needle_that_is_neither_is_refused``
    CONTROL: sin el, un ``determine`` que devolviera ``None`` ante lo
    inesperado pasaria los dos casos felices.
"""
import operator

import pytest
from django.db import models

from orm.fields import (IR_MODELS, PYTHON_INEQUALITY_OPERATOR, T, determine,
                        global_seq, resolve_mro)

pytestmark = pytest.mark.unit


class _Base:
    tag = 'base'
    number = 1
    nothing = None


class _Middle(_Base):
    tag = 'middle'
    number = 'no es un numero'


class _Leaf(_Middle):
    tag = 'leaf'
    number = 3
    nothing = None


class TestT:
    """≙ ``T = typing.TypeVar("T")`` (``:35``) — TRAE, estandar."""

    def test_it_is_a_type_variable_named_t(self):
        assert T.__name__ == 'T'


class TestIrModels:
    """≙ ``IR_MODELS`` (``:37``) — los modelos del registro."""

    def test_the_seven_are_the_ones_the_reference_names(self):
        assert IR_MODELS == (
            'ir.model', 'ir.model.data', 'ir.model.fields',
            'ir.model.fields.selection', 'ir.model.relation',
            'ir.model.constraint', 'ir.module.module',
        )

    def test_it_is_a_tuple_so_nobody_extends_it_by_accident(self):
        """Inmutable, como la fuente: es el contrato de una guarda."""
        assert isinstance(IR_MODELS, tuple)


class TestPythonInequalityOperator:
    """≙ ``PYTHON_INEQUALITY_OPERATOR`` (``:45``) — la comparacion en memoria."""

    def test_the_four_map_to_the_standard_library(self):
        assert PYTHON_INEQUALITY_OPERATOR == {
            '<': operator.lt, '>': operator.gt,
            '<=': operator.le, '>=': operator.ge,
        }

    def test_an_operator_outside_the_four_is_not_there(self):
        """CONTROL: el mapa acota; ``=`` y ``!=`` los resuelve otro camino."""
        assert PYTHON_INEQUALITY_OPERATOR.get('=') is None
        assert PYTHON_INEQUALITY_OPERATOR.get('!=') is None


class TestGlobalSeq:
    """≙ ``_global_seq = itertools.count()`` (``:89``) — TRAE, de Django."""

    def test_each_call_gives_a_greater_number(self):
        assert global_seq() < global_seq() < global_seq()

    def test_it_does_not_start_a_second_numbering(self):
        """La divergencia declarada: el contador ES el de Django.

        Un campo construido entre dos llamadas tiene que caer **entre** ellas.
        Si el modulo declarara su propio contador, el campo quedaria fuera del
        intervalo y las dos numeraciones no se podrian comparar.
        """
        before = global_seq()
        field = models.CharField(max_length=4)
        after = global_seq()
        assert before < field.creation_counter < after


class TestResolveMro:
    """≙ ``resolve_mro`` (``:50-64``) — CONSTRUYE, con ``__mro__``."""

    def test_it_returns_the_overrides_most_derived_first(self):
        assert resolve_mro(_Leaf, 'tag', lambda v: True) == [
            'leaf', 'middle', 'base']

    def test_it_stops_at_the_first_value_that_fails_the_predicate(self):
        """La fuente CORTA, no filtra: la cadena tiene que ser contigua.

        ``_Middle.number`` no es un entero, asi que ``_Base.number`` —que si lo
        es— queda fuera. Con un ``continue`` en vez del ``break`` saldrian dos.
        """
        assert resolve_mro(_Leaf, 'number', lambda v: isinstance(v, int)) == [3]

    def test_a_class_that_declares_none_is_not_confused_with_absence(self):
        """CONTROL del centinela — ``None`` declarado SI cuenta."""
        assert resolve_mro(_Leaf, 'nothing', lambda v: v is None) == [
            None, None]

    def test_an_attribute_nobody_declares_gives_an_empty_list(self):
        assert resolve_mro(_Leaf, 'no_existe', lambda v: True) == []

    def test_an_instance_is_read_by_its_class(self):
        """La fuente recibe un recordset; aqui vale la instancia o la clase."""
        assert resolve_mro(_Leaf(), 'tag', lambda v: True) == [
            'leaf', 'middle', 'base']

    def test_object_is_not_walked(self):
        """≙ *"Model registry classes are ignored"*: lo que no escribio nadie
        del arbol no entra. ``__init__`` lo declara ``object``, y aun asi el
        recorrido no lo ve."""
        assert resolve_mro(_Leaf, '__init__', lambda v: True) == []


class _Subject:
    def __init__(self):
        self.seen = []

    def greet(self, *args):
        self.seen.append(args)
        return 'saludado'


class TestDetermine:
    """≙ ``determine`` (``:66-87``) — CONSTRUYE, con ``getattr``."""

    def test_a_method_name_is_called_on_the_subject(self):
        subject = _Subject()
        assert determine('greet', subject, 1, 2) == 'saludado'
        assert subject.seen == [(1, 2)]

    def test_a_callable_receives_the_subject_first(self):
        seen = {}

        def probe(records, *args):
            seen['records'] = records
            return args

        subject = _Subject()
        assert determine(probe, subject, 'x') == ('x',)
        assert seen['records'] is subject

    def test_a_name_the_subject_does_not_declare_is_refused(self):
        with pytest.raises(TypeError, match='no declara el método'):
            determine('no_existe', _Subject())

    def test_a_needle_that_is_neither_is_refused(self):
        with pytest.raises(TypeError, match='invocable o el nombre'):
            determine(42, _Subject())

    def test_a_subject_that_is_none_is_refused(self):
        with pytest.raises(TypeError, match='sujeto'):
            determine('greet', None)
