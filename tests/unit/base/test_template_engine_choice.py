r"""Sonda comparativa: los dos motores de expresión que el descriptor puede usar.

Directiva del ejecutor 2026-08-29: *"vamos a crear analisis del como lo hariamos
con nuestro stack, uno por uno"* + *"vas a analizar los binarios y crear
pruebas"*.

El :doc:`Flujo B <docs: analisis-flujo-b-el-documento-sin-navegador-en-odoo-tools>`
midió que la referencia particiona su motor: el modo sin base de datos
(``odoo19c: odoo/addons/base/models/ir_qweb.py:2975``) cierra las directivas de
**formato** y deja en pie las de **estructura**. Ésa es la superficie que el
descriptor de reportes necesita.

Con esa partición sobre la mesa quedan dos candidatos para evaluar el valor de
un campo del descriptor, y la tarea **#181** es elegir:

- **DTL** — ``django.template``, ya en uso en ``report_template._render_text``.
- **El compilador de QWeb portado** — ``IrQweb._compile_expr`` (``api@c77bc566``),
  con su allowlist de opcodes.

Esta sonda no elige: **mide**, caso por caso, para que la decisión se tome
sobre conducta observada y no sobre reputación. Cada caso ejercita los dos
motores con la misma expresión.

*Métrica:* la conducta de ``django.template.Engine(autoescape=False)`` y de
``IrQweb._compile_expr`` sobre el mismo juego de expresiones.
*Ciega a:* el coste de ejecución de cada motor, que no se mide aquí; y a la
legibilidad de la plantilla resultante, que no es una propiedad medible por
una prueba.
"""
import pytest
from django.template import Context, Engine, TemplateSyntaxError

from addons.base.models.ir_qweb import IrQweb

#: El motor del descriptor: autoescape apagado, como declara
#: ``report_template._ENGINE`` — el texto va a un dict y ``json.dumps`` hace el
#: quoting.
DTL = Engine(autoescape=False)


def render_with_dtl(source, context):
    return DTL.from_string(source).render(Context(context, autoescape=False))


@pytest.fixture
def engine():
    return IrQweb()


class TestDtlRefusesWhatItCannotParse:
    """DTL restringe por GRAMÁTICA: lo que no cabe en su sintaxis, no compila."""

    def test_a_call_with_arguments_does_not_parse(self):
        with pytest.raises(TemplateSyntaxError, match=r"Could not parse the remainder: '\(1\)'"):
            render_with_dtl('{{ f(1) }}', {'f': lambda x: x})

    def test_arithmetic_does_not_parse(self):
        with pytest.raises(TemplateSyntaxError, match=r"Could not parse the remainder: ' \+ 1'"):
            render_with_dtl('{{ a + 1 }}', {'a': 1})

    def test_what_it_does_allow_is_lookup_by_dot_and_by_index(self):
        assert render_with_dtl('{{ b.c }}', {'b': type('X', (), {'c': 2})()}) == '2'
        # El índice de lista se escribe con punto, no con corchete.
        assert render_with_dtl('{{ xs.0 }}', {'xs': [10, 20]}) == '10'


class TestTheQwebCompilerAcceptsRealPython:
    """QWeb restringe por OPCODE: compila Python y valida el bytecode."""

    @pytest.mark.parametrize('expression, compiled', [
        ('a',               "((values.get('a')))"),
        ('b.c',             "((values['b'].c))"),
        ('f(1)',            "((values['f'](1)))"),
        ('a + 1',           "((values.get('a') + 1))"),
        ('xs[0]',           "((values['xs'][0]))"),
    ])
    def test_it_compiles_what_dtl_refuses(self, engine, expression, compiled):
        assert engine._compile_expr(expression) == compiled

    def test_the_opcode_allowlist_is_the_guard_not_the_grammar(self, engine):
        # Un cierre anidado es Python válido y la gramática lo acepta; lo que
        # lo rechaza es el allowlist, al mirar el bytecode.
        with pytest.raises(ValueError, match='forbidden opcode'):
            engine._compile_expr('lambda a: (lambda: a)')

    def test_the_double_underscore_guard_is_a_second_and_distinct_barrier(self, engine):
        # Cae ANTES del allowlist, en el recorrido de tokens.
        with pytest.raises(SyntaxError, match="Using variable names with '__' is not allowed"):
            engine._compile_expr('__import__')


class TestDtlCallsCallablesOnItsOwn:
    """La asimetría que ningún catálogo de sintaxis muestra."""

    def test_dtl_invokes_a_callable_found_in_the_context(self):
        # `{{ f }}` NO imprime el objeto: lo llama. Es conducta de
        # `django/template/base.py:993` — `if callable(current): current()`.
        assert render_with_dtl('{{ f }}', {'f': lambda: 'llamada'}) == 'llamada'

    def test_its_guard_against_that_is_alters_data(self):
        class Risky:
            def wipe(self):
                return 'WIPED'

            def safe(self):
                return 'ok'
        Risky.wipe.alters_data = True

        # El marcado no se llama: DTL devuelve `string_if_invalid` (por
        # defecto, la cadena vacía). El otro sí.
        assert render_with_dtl('{{ r.wipe }}|{{ r.safe }}', {'r': Risky()}) == '|ok'

    def test_the_qweb_compiler_does_not_invoke_anything_by_itself(self, engine):
        # Compilar `f` produce un lookup, no una llamada: los paréntesis los
        # tiene que escribir el autor de la plantilla.
        assert engine._compile_expr('f') == "((values.get('f')))"


class TestBothEnginesLeaveTheAmpersandAlone:
    """La propiedad que el descriptor exige: el texto va a un dict, no a HTML."""

    def test_dtl_with_autoescape_off_emits_the_raw_ampersand(self):
        assert render_with_dtl('{{ s }}', {'s': 'a & b'}) == 'a & b'

    def test_dtl_with_autoescape_on_would_corrupt_the_value(self):
        # El control que hace observable por qué `report_template._ENGINE`
        # declara `autoescape=False`: con autoescape el dato llega al papel
        # como `&amp;`.
        escaping = Engine(autoescape=True)
        rendered = escaping.from_string('{{ s }}').render(Context({'s': 'a & b'}))
        assert rendered == 'a &amp; b'
