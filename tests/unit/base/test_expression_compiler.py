r"""``IrTemplateExpressions`` — el compilador de expresiones (bloque A de la tarea #181).

Mide el comportamiento, no la forma: cada caso compila una expresión de QWeb
y comprueba el código generado **y** su evaluación contra un contexto real.

El contrato que fija, y que la fuente declara en el docstring de
``_compile_expr_tokens``:

- un nombre libre se resuelve por el espacio de nombres ``values``;
- si de ese nombre se pide un atributo o un índice, se emite ``values['x']``
  y no ``values.get('x')`` — para que el error nombre el valor ausente;
- los locales de una ``lambda`` o de una comprensión **no** llevan espacio de
  nombres, y sus libres sí;
- el código generado pasa por la lista blanca de opcodes antes de existir.
"""
import pytest

from addons.base.models.ir_template_expressions import IrTemplateExpressions


@pytest.fixture
def engine():
    """El motor. Abstracto y sin fila: el compilador no toca la base."""
    return IrTemplateExpressions()


class TestNamesGetTheValuesNamespace:
    """Un nombre libre se resuelve contra ``values``."""

    def test_a_bare_name_is_read_with_get(self, engine):
        # Los DOS niveles de paréntesis son de la fuente y no sobran: uno lo
        # pone `_compile_expr` al envolver el texto antes de tokenizar (es lo
        # que permite compilar expresiones multilínea) y el otro lo devuelve
        # `_compile_expr_tokens` al colapsar ese nivel en un token QWEB.
        assert engine._compile_expr('a') == "((values.get('a')))"

    def test_an_attribute_access_uses_the_subscript(self, engine):
        """``values['b'].c`` para que el error nombre ``b``, no el ``None``."""
        assert engine._compile_expr('b.c') == "((values['b'].c))"

    def test_a_call_uses_the_subscript_too(self, engine):
        assert engine._compile_expr('f()') == "((values['f']()))"

    def test_an_index_uses_the_subscript(self, engine):
        assert engine._compile_expr('b[0]') == "((values['b'][0]))"

    def test_raise_on_missing_forces_the_subscript(self, engine):
        assert engine._compile_expr(
            'a', raise_on_missing=True) == "((values['a']))"

    def test_an_allowed_keyword_is_left_alone(self, engine):
        """``True`` es del lenguaje, no del contexto."""
        assert engine._compile_expr('True') == '((True))'

    def test_a_builtin_is_left_alone(self, engine):
        """``len`` viene de ``_BUILTINS``.

        Cae si alguien vuelve a excluir ``_BUILTINS`` de ``ALLOWED_KEYWORD``:
        el código pasaría a ser ``values['len'](...)``, que evalúa a ``None``
        y rompe toda plantilla con ``t-if="len(docs) > 1"``.
        """
        assert engine._compile_expr('len(a)') == "((len(values.get('a'))))"


class TestLocalScopesAreNotNamespaced:
    """Los locales de lambda y comprensión se acceden directo."""

    def test_a_lambda_argument_is_local_and_its_free_name_is_not(self, engine):
        assert engine._compile_expr('lambda a: a + b') == (
            "((lambda _arg_a__: _arg_a__ + values.get('b')))")

    def test_a_comprehension_variable_is_local(self, engine):
        assert engine._compile_expr('[a + b for a in c]') == (
            "(([_arg_a__ + values.get('b') for _arg_a__ in values.get('c')]))")

    def test_a_lambda_default_value_is_refused(self, engine):
        with pytest.raises(NotImplementedError):
            engine._compile_expr('lambda a=1: a')


class TestTheCompiledCodeActuallyEvaluates:
    """El contrato de punta a punta: compilar y ejecutar."""

    def evaluate(self, engine, expr, values):
        # ``eval`` sobre el código ya validado contra la lista blanca; es lo
        # que el motor hará con él.
        return eval(engine._compile_expr(expr), {}, {'values': values})

    def test_arithmetic_over_the_context(self, engine):
        assert self.evaluate(engine, '5 + a + b', {'a': 2, 'b': 3}) == 10

    def test_a_missing_name_is_none(self, engine):
        assert self.evaluate(engine, 'a', {}) is None

    def test_a_missing_name_with_attribute_names_itself(self, engine):
        """El punto del subíndice: el error dice ``'b'``, no ``NoneType``."""
        with pytest.raises(KeyError) as excinfo:
            self.evaluate(engine, 'b.c', {})
        assert excinfo.value.args[0] == 'b'

    def test_a_comprehension_runs(self, engine):
        assert self.evaluate(
            engine, '[x * 2 for x in items]', {'items': [1, 2, 3]}) == [2, 4, 6]


class TestTheOpcodeAllowlistIsTheGuard:
    """La guarda que hace admisible compilar texto almacenado."""

    def test_an_import_is_refused(self, engine):
        """El veto del ``__`` llega antes que la lista de opcodes."""
        with pytest.raises(SyntaxError, match="'__'"):
            engine._compile_expr('__import__("os").system("id")')

    def test_a_dunder_name_is_refused(self, engine):
        # La puerta clásica a la ejecución arbitraria: ``x.__class__`` abre la
        # cadena hasta ``object.__subclasses__``.
        with pytest.raises(SyntaxError, match="'__'"):
            engine._compile_expr('a.__class__')

    def test_a_nested_closure_is_refused_by_the_allowlist_alone(self, engine):
        """El caso que **sólo** la lista blanca rechaza — y es el que faltaba.

        Los dos casos de ``__`` de arriba caen por el veto del nombre, que es
        una guarda **distinta** y anterior. Sin este caso la suite pasaba
        entera con ``assert_valid_codeobj`` anulado: verde que no discrimina
        (sub-patrón D de ``metrica-decide-la-conclusion.md``).

        Una lambda anidada captura por celda, y ni ``MAKE_CELL`` ni
        ``LOAD_CLOSURE`` están en :data:`_SAFE_QWEB_OPCODES`. Es una
        restricción **de la fuente**, no nuestra: una expresión de plantilla
        no crea clausuras.
        """
        with pytest.raises(ValueError, match='forbidden opcode'):
            engine._compile_expr('lambda a: (lambda: a)')

    def test_an_unparseable_expression_is_refused(self, engine):
        # ``tokenize`` la acepta —los tokens son válidos— y quien la rechaza
        # es el ``compile()`` de la validación. Por eso es ``SyntaxError`` y
        # no el ``ValueError`` del ``TokenError``.
        with pytest.raises(SyntaxError):
            engine._compile_expr('a +')


class TestFormatStrings:
    """``_compile_format`` — los dos estilos de sustitución."""

    def test_a_plain_string_is_a_literal(self, engine):
        assert engine._compile_format('Hola') == repr('Hola')

    def test_the_ruby_style_substitutes(self, engine):
        code = engine._compile_format('Hola #{name}')
        assert eval(code, {}, {'self': engine,
                               'values': {'name': 'Kim'}}) == 'Hola Kim'

    def test_the_jinja_style_substitutes(self, engine):
        code = engine._compile_format('Hola {{name}}')
        assert eval(code, {}, {'self': engine,
                               'values': {'name': 'Kim'}}) == 'Hola Kim'

    def test_a_literal_percent_survives(self, engine):
        """El ``%`` del texto se duplica antes de formatear; si no, revienta."""
        code = engine._compile_format('100% de #{n}')
        assert eval(code, {}, {'self': engine,
                               'values': {'n': 'todo'}}) == '100% de todo'


class TestTheAttributeVocabularyIsXmlNotPython:
    """``_compile_bool`` lee un atributo, no un valor de Python."""

    @pytest.mark.parametrize('given,expected', [
        ('false', False), ('0', False), ('FALSE', False),
        ('true', True), ('1', True), ('True', True),
        (True, True), ('', False), (None, False),
    ])
    def test_the_xml_vocabulary(self, engine, given, expected):
        assert engine._compile_bool(given) is expected

    def test_an_unknown_string_falls_to_the_default(self, engine):
        """``bool('quizas')`` de Python daría ``True``; aquí manda el default."""
        assert engine._compile_bool('quizas') is False
        assert engine._compile_bool('quizas', default=True) is True


class TestValuesBecomeText:
    """``_compile_to_str`` — y por qué ``False`` no imprime ``"False"``."""

    @pytest.mark.parametrize('given,expected', [
        (None, ''), (False, ''), ('ya texto', 'ya texto'),
        (b'bytes', 'bytes'), (42, '42'), (0, '0'), (True, 'True'),
    ])
    def test_the_conversions(self, engine, given, expected):
        assert engine._compile_to_str(given) == expected

    def test_zero_is_not_empty(self, engine):
        """``0`` es falsy pero SÍ se imprime — sólo ``None`` y ``False`` no."""
        assert engine._compile_to_str(0) == '0'
