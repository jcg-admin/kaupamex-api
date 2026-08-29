r"""Sonda: qué da lo que QWeb da, sin traer QWeb.

Pregunta del ejecutor 2026-08-29: *"si no queremos ``lxml + QWeb`` … pero si
queremos lo que hace, ¿qué podemos usar?"*.

Lo que el compilador de QWeb aporta son **tres cosas separables**, y sólo una
es propia del motor de plantillas:

1. **contención de la expresión** — el allowlist de opcodes y el veto de
   ``__dunder__``. **No es de QWeb**: lo importa de ``tools.safe_eval``
   (``odoo19c: ir_qweb.py:401``), que está portado entero y tiene 10 consumidores;
2. **resolución de nombres** — de dónde sale ``a`` al evaluar ``a + 1``;
3. **compilación de la plantilla a código Python** — el ``_compile_node`` /
   ``_generate_code``. **Esto es lo que no se quiere**, y es justo lo que
   ``report_template.interpret_descriptor`` ya reemplaza.

La sonda mide los dos candidatos que quedan al retirar el tercero, contra el
mismo juego de expresiones y los mismos ataques.

*Métrica:* la conducta de ``tools.safe_eval`` y de ``django.template.Variable``
sobre objetos de Python.
*Ciega a:* el coste por evaluación de cada uno, que no se mide aquí; y a la
ergonomía de escribir la expresión, que no es medible por una prueba.
"""
import pytest
from django.template import Context, TemplateSyntaxError, Variable
from django.template.base import VariableDoesNotExist

from tools.safe_eval import expr_eval, safe_eval


class Line:
    """Una hoja del contexto, con un atributo privado que sirve de sonda."""
    price = 10.5
    qty = 2
    _internal = 'no deberia salir en un documento'


def _no_args():
    """Control positivo del auto-call de DTL: no exige argumentos."""
    return 'CALLED'


CONTEXT = {'a': 1, 'line': Line(), 'rows': [10, 20],
           'triple': lambda x: x * 3, 'no_args': _no_args}


class TestSafeEvalDoesWhatTheQwebCompilerDoes:
    """El poder expresivo, sin el compilador de plantillas."""

    @pytest.mark.parametrize('expression, expected', [
        ('a + 1',                    2),
        ('line.price * line.qty',    21.0),
        ('rows[0]',                  10),
        ('triple(2)',                6),
        ('[x * 2 for x in rows]',    [20, 40]),
        ('sum(x for x in rows)',     30),
    ])
    def test_it_evaluates_real_python_over_python_objects(self, expression, expected):
        assert safe_eval(expression, CONTEXT) == expected


class TestItIsTheSameContainmentNotAWeakerOne:
    """Los tres rechazos son los mismos que el compilador de QWeb produce."""

    def test_the_opcode_allowlist_rejects_a_nested_closure(self):
        with pytest.raises(ValueError, match='forbidden opcode'):
            safe_eval('lambda a: (lambda: a)', CONTEXT)

    def test_the_dunder_guard_rejects_the_import_builtin(self):
        with pytest.raises(NameError, match="Access to forbidden name '__import__'"):
            safe_eval('__import__("os")', CONTEXT)

    def test_it_rejects_reaching_the_class_through_an_object(self):
        with pytest.raises(NameError, match="Access to forbidden name '__class__'"):
            safe_eval('line.__class__', CONTEXT)

    def test_the_builtins_are_an_allowlist_so_open_is_not_there(self):
        with pytest.raises(ValueError, match="name 'open' is not defined"):
            safe_eval('open("/etc/passwd")', CONTEXT)


class TestTheStricterMiddleGroundIsDjangoVariable:
    """DTL sin motor de plantillas: su resolutor se usa suelto."""

    def test_it_resolves_by_dot_over_python_objects(self):
        assert Variable('line.price').resolve(Context(CONTEXT)) == 10.5
        assert Variable('rows.0').resolve(Context(CONTEXT)) == 10

    def test_it_refuses_every_underscore_not_only_dunders(self):
        # Más estricto que safe_eval: `_internal` es un atributo perfectamente
        # legal en Python y aquí no se alcanza.
        with pytest.raises(TemplateSyntaxError, match='may not begin with underscores'):
            Variable('line._internal')

    def test_only_plus_and_minus_are_rejected_when_building(self):
        # Y el motivo NO es vetar la aritmética: son los dos caracteres que
        # también aparecen dentro de un número, así que el constructor los
        # rechaza para no confundir `1-2` con una resta
        # (``django/template/base.py:917-921``).
        for expression in ('a + 1', 'a - 1'):
            with pytest.raises(TemplateSyntaxError, match='Invalid character'):
                Variable(expression)

    def test_the_other_operators_pass_and_break_at_resolve(self):
        # `*`, `/` y `%` no están en esa lista de dos. El constructor los
        # acepta y la resolución parte por el punto, así que `price * line`
        # queda como un nombre de atributo que no existe. El importe de línea
        # sigue sin expresarse — pero el fallo llega más tarde y con otro
        # nombre, que es lo que hay que saber al elegir este resolutor.
        variable = Variable('line.price * line.qty')
        with pytest.raises(VariableDoesNotExist, match=r'price \* line'):
            variable.resolve(Context(CONTEXT))


class TestWhereTheTwoDisagree:
    """El eje que decide entre ellos, medido en los dos sentidos."""

    def test_safe_eval_reaches_a_single_underscore_attribute(self):
        # No es un fallo de safe_eval: su veto cubre `__dunder__`, no el guion
        # bajo simple. Es una diferencia de política que hay que conocer.
        assert safe_eval('line._internal', CONTEXT) == Line._internal

    def test_variable_does_not(self):
        with pytest.raises(TemplateSyntaxError):
            Variable('line._internal')

    def test_safe_eval_hands_back_the_callable_untouched(self):
        # `safe_eval` devuelve el objeto; los paréntesis los escribe el autor.
        assert callable(safe_eval('triple', CONTEXT))

    def test_variable_calls_it_by_itself_when_it_takes_no_arguments(self):
        # DTL llama al callable por su cuenta (``base.py:993``). Es la
        # diferencia de política más grande entre los dos.
        assert Variable('no_args').resolve(Context(CONTEXT)) == 'CALLED'

    def test_and_needs_an_engine_to_degrade_when_it_takes_one(self):
        # Si el callable exige un argumento, DTL quiere degradar a
        # `string_if_invalid` (``base.py:1009-1011``) — y ése vive en el
        # motor, que un ``Context`` suelto no tiene. El resultado es un
        # `AttributeError` opaco en vez del `VariableDoesNotExist` que un
        # consumidor esperaría atrapar.
        with pytest.raises(AttributeError, match="has no attribute 'engine'"):
            Variable('triple').resolve(Context(CONTEXT))


class TestExprEvalIsTheNarrowestOfAll:
    """Y el tercero, para cuando la expresión no debe ver el contexto."""

    def test_it_evaluates_constants(self):
        assert expr_eval('1 + 1') == 2

    def test_and_refuses_any_name_at_all(self):
        with pytest.raises(ValueError, match='forbidden opcode.*LOAD_NAME'):
            expr_eval('a + 1')
