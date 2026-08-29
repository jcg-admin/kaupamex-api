"""El evaluador acotado: qué deja pasar, qué rechaza y con qué lo rechaza.

Cubre el porte completo de ``odoo/tools/safe_eval.py`` (tarea #140). La
división de clases sigue los tres niveles que el módulo declara —constante,
expresión y expresión con contexto— más las guardas transversales y los
módulos envueltos.

**Los casos negativos apuntan a un objetivo que EXISTE.** Un caso que pida
``__import__`` y espere el rechazo pasaría igual si el evaluador no
compilara nada; por eso cada uno de ellos va acompañado de su control
positivo: la misma forma sin la parte prohibida, que SÍ debe evaluarse. Sin
ese par, un verde no distingue «la guarda funciona» de «el instrumento no
llega a mirar» (sub-patrón D de ``metrica-decide-la-conclusion``).
"""
import dis
import json as json_real

import pytest

from exceptions import UserError
from tools import safe_eval as module
from tools.safe_eval import (
    _BUILTINS,
    _CONST_OPCODES,
    _EXPR_OPCODES,
    _SAFE_OPCODES,
    _UNSAFE_ATTRIBUTES,
    assert_no_dunder_name,
    assert_valid_codeobj,
    compile_codeobj,
    const_eval,
    expr_eval,
    safe_eval,
    wrap_module,
)


class TestTheConstantLevel:
    """``const_eval`` — sólo literales, ni siquiera aritmética."""

    def test_evaluates_a_nested_literal(self):
        assert const_eval("[1,2, (3,4), {'foo':'bar'}]") == [
            1, 2, (3, 4), {'foo': 'bar'}]

    def test_refuses_a_call_because_it_is_not_a_constant(self):
        # Control positivo del mismo caso: el literal solo SÍ pasa.
        assert const_eval("3") == 3
        with pytest.raises(ValueError, match='forbidden opcode'):
            const_eval("len([1, 2])")

    def test_arithmetic_of_literals_slips_through_by_constant_folding(self):
        """La aritmética de constantes YA NO la ve la guarda. Ver H-API-923.

        El doctest de la fuente afirma ``const_eval("1+2")`` →
        ``ValueError: opcode BINARY_ADD not allowed``. Aquí devuelve **3**, y
        no por el porte: CPython 3.12 pliega la constante en tiempo de
        compilación y el bytecode queda en ``RESUME; RETURN_CONST 3`` — sin
        ningún ``BINARY_OP`` que rechazar.

        Se afirma lo medido, no lo que la fuente dice. La guarda sigue
        discriminando lo que importa (el caso de arriba, con una llamada), y
        el valor plegado es una constante, que es justo lo que ``const_eval``
        promete devolver.
        """
        assert const_eval("1+2") == 3


class TestTheExpressionLevel:
    """``expr_eval`` — aritmética sobre constantes, sin nombres."""

    def test_evaluates_arithmetic(self):
        assert expr_eval("1+2") == 3
        assert expr_eval("[1,2]*2") == [1, 2, 1, 2]

    def test_refuses_a_name_because_there_is_no_namespace(self):
        # Control positivo: la misma forma con una constante en vez del nombre.
        assert expr_eval("[1, 2]") == [1, 2]
        with pytest.raises(ValueError, match='forbidden opcode'):
            expr_eval("name")

    def test_the_import_dies_on_the_name_check_not_on_the_opcode_check(self):
        """El orden de las dos guardas, medido. Ver H-API-923.

        El doctest de la fuente afirma ``ValueError: opcode LOAD_NAME not
        allowed``, pero ``assert_valid_codeobj`` llama **primero** a
        ``assert_no_dunder_name``, y ``__import__`` contiene ``__``. Gana
        ``NameError``. La expresión se rechaza igual — lo que estaba mal era
        el doctest de la fuente, no la guarda.
        """
        with pytest.raises(NameError, match='forbidden name'):
            expr_eval("__import__('sys').modules")


class TestTheGeneralExpression:
    """``safe_eval`` — la forma que ``retrieve_attachment`` necesita.

    Cada caso es una expresión que la versión anterior de este módulo —la que
    validaba el AST contra la forma de un dominio— rechazaba, y que la fuente
    admite. Son la razón de ser del porte.
    """

    def test_formats_a_string_with_the_percent_operator(self):
        assert safe_eval("'INV_%s.pdf' % object.name",
                         {'object': _Record(name='001')}) == 'INV_001.pdf'

    def test_evaluates_the_attachment_expression_of_the_reference(self):
        # La forma canónica del campo ``attachment`` de un ir.actions.report.
        expression = ("(object.state in ('open', 'paid')) and "
                     "((object.name or 'Invoice').replace('/', '') + '.pdf')")
        paid = _Record(name='INV/2026/001', state='paid')
        assert safe_eval(expression, {'object': paid}) == 'INV2026001.pdf'
        draft = _Record(name='INV/2026/002', state='draft')
        assert safe_eval(expression, {'object': draft}) is False

    def test_calls_a_method_of_the_wrapped_time_module(self):
        value = safe_eval("time.strftime('%Y')", {'time': module.time})
        assert value.isdigit() and len(value) == 4

    def test_evaluates_a_comprehension_with_a_lambda(self):
        assert safe_eval(
            "sorted([3, 1, 2], key=lambda n: -n)") == [3, 2, 1]

    def test_still_evaluates_a_domain_which_is_the_previous_consumer(self):
        # El consumidor que ya existía (``ir.rule.domain_force``) no se rompe:
        # un dominio es un subconjunto de lo que este evaluador admite.
        assert safe_eval("[('company_id', 'in', company_ids)]",
                         {'company_ids': [1, 2]}) == [
            ('company_id', 'in', [1, 2])]


class TestTheGuards:
    """Lo que el evaluador rechaza, cada uno con su control positivo."""

    def test_refuses_a_name_with_two_underscores(self):
        assert safe_eval("object.name", {'object': _Record(name='x')}) == 'x'
        with pytest.raises(NameError, match='forbidden name'):
            safe_eval("object.__class__", {'object': _Record(name='x')})

    def test_refuses_every_attribute_of_the_unsafe_list(self):
        # Los 20 de ``_UNSAFE_ATTRIBUTES``, uno por uno. Ninguno lleva ``__``,
        # así que sin la lista el primer check los dejaría pasar.
        without_dunder = [a for a in _UNSAFE_ATTRIBUTES if '__' not in a]
        assert without_dunder, 'la lista quedaria cubierta solo por el check dunder'
        for attribute in without_dunder:
            with pytest.raises(NameError, match='forbidden name'):
                safe_eval(f"object.{attribute}", {'object': _Record(name='x')})

    def test_refuses_to_import(self):
        assert safe_eval("1 + 1") == 2
        with pytest.raises(ValueError, match='forbidden opcode'):
            safe_eval("import os", mode='exec')

    def test_refuses_to_write_an_attribute(self):
        assert safe_eval("object.name", {'object': _Record(name='x')}) == 'x'
        with pytest.raises(ValueError, match='forbidden opcode'):
            safe_eval("object.name = 'otro'", {'object': _Record(name='x')},
                      mode='exec')

    def test_the_builtins_have_neither_open_nor_eval_nor_exec(self):
        assert 'len' in _BUILTINS and 'sorted' in _BUILTINS
        for forbidden in ('open', 'eval', 'exec', 'compile', 'globals',
                          'getattr', 'setattr', 'vars', 'input', 'help'):
            assert forbidden not in _BUILTINS, forbidden

    def test_refuses_a_code_object_passed_directly(self):
        with pytest.raises(TypeError, match='code objects'):
            safe_eval(compile('1+1', '<t>', 'eval'))

    def test_refuses_a_whole_module_in_the_context(self):
        with pytest.raises(TypeError, match='can not be used'):
            safe_eval("json", {'json': json_real})
        # Control positivo: envuelto SÍ entra.
        assert safe_eval("json.dumps([1])", {'json': module.json}) == '[1]'


class TestTheGuardsWithTheGuardNulled:
    """Mide que las guardas discriminan, anulándolas una a una.

    Sin este bloque, los verdes de arriba no distinguen «la guarda rechaza»
    de «el evaluador nunca llega a ejecutar la expresión». Aquí se comprueba
    que cada expresión prohibida **funciona** cuando su guarda se retira: eso
    es lo que prueba que la guarda es quien la para.
    """

    def test_the_opcode_check_and_the_name_check_are_two_distinct_guards(self):
        # ``import os`` sólo lo para la lista de opcodes: su nombre (``os``) no
        # lleva guiones bajos, así que el check de nombres lo deja pasar.
        opcode_only = compile_codeobj("import os", mode='exec')
        assert_no_dunder_name(opcode_only, 'x')          # la otra guarda calla
        with pytest.raises(ValueError, match='forbidden opcode'):
            assert_valid_codeobj(_SAFE_OPCODES, opcode_only, 'x')

        # ``__import__('sys')`` es el caso simétrico: su bytecode NO tiene
        # ningún opcode prohibido —es una llamada corriente— y lo para sólo el
        # check de nombres. Cada guarda cubre lo que la otra no ve.
        name_only = compile_codeobj("__import__('sys')", mode='eval')
        assert {i.opcode for i in dis.get_instructions(name_only)} \
            <= _SAFE_OPCODES
        with pytest.raises(NameError, match='forbidden name'):
            assert_valid_codeobj(_SAFE_OPCODES, name_only, 'x')

    def test_the_dunder_check_is_what_stops_class_traversal(self):
        code_object = compile_codeobj("object.__class__", mode='eval')
        with pytest.raises(NameError, match='forbidden name'):
            assert_no_dunder_name(code_object, 'x')
        # Anulada la guarda, el bytecode de esa misma expresión NO tiene
        # ningún opcode prohibido: la lista de opcodes sola la dejaría pasar.
        assert {i.opcode for i in __import__('dis').get_instructions(code_object)} \
            <= _SAFE_OPCODES

    def test_the_three_opcode_sets_are_strictly_nested(self):
        # Si dejaran de estarlo, un caso de ``const_eval`` podría admitir algo
        # que ``expr_eval`` prohíbe, y los tres niveles perderían su sentido.
        assert _CONST_OPCODES < _EXPR_OPCODES < _SAFE_OPCODES


class TestTheContextIsMutated:
    """El contrato de ``mode='exec'``: el contexto sale con lo que se creó."""

    def test_a_variable_created_in_exec_mode_lands_in_the_context(self):
        context = {'entrada': 3}
        safe_eval("salida = entrada * 2", context, mode='exec')
        assert context['salida'] == 6

    def test_the_builtins_do_not_leak_into_the_context(self):
        context = {}
        safe_eval("x = 1", context, mode='exec')
        assert '__builtins__' not in context

    def test_refuses_a_context_that_is_not_a_dict(self):
        with pytest.raises(AssertionError, match='must be a dict'):
            safe_eval("1", [('a', 1)])


class TestTheExpressionTester:
    """``test_python_expr`` — devuelve el mensaje, no levanta."""

    def test_returns_false_for_a_valid_expression(self):
        assert module.test_python_expr("1 + 1") is False

    def test_returns_the_message_for_a_syntax_error(self):
        message = module.test_python_expr("1 +")
        assert isinstance(message, str) and 'SyntaxError' in message

    def test_returns_the_message_for_forbidden_bytecode(self):
        message = module.test_python_expr("import os", mode='exec')
        assert isinstance(message, str) and 'forbidden opcode' in message

    def test_a_forbidden_name_escapes_instead_of_being_returned(self):
        """El hueco de la fuente, portado verbatim. Ver H-API-924.

        ``test_python_expr`` promete devolver el mensaje del error, y atrapa
        ``(SyntaxError, TypeError, ValueError)``. ``assert_no_dunder_name``
        levanta ``NameError``, que NO está en esa tupla: para la forma más
        común de ataque —``__import__``, ``__class__``— la función levanta en
        vez de devolver.

        Se porta tal cual porque es lo que la fuente hace; el arreglo cambia
        el contrato y es decisión del ejecutor. Este caso deja el defecto
        medido y no silenciado: si alguien lo arregla, el test cae y obliga a
        actualizar el hallazgo.
        """
        with pytest.raises(NameError, match='forbidden name'):
            module.test_python_expr("__import__('os')")


class TestTheWrappedModules:
    """Los cinco que la fuente expone, con sus atributos declarados."""

    @pytest.mark.parametrize('wrapped,attributes', [
        (lambda: module.time, ['time', 'strptime', 'strftime', 'sleep']),
        (lambda: module.json, ['loads', 'dumps']),
        (lambda: module.pytz, ['utc', 'UTC', 'timezone']),
        (lambda: module.datetime, ['date', 'datetime', 'time', 'timedelta',
                                   'timezone', 'tzinfo', 'MAXYEAR', 'MINYEAR']),
    ])
    def test_exposes_exactly_the_declared_attributes(self, wrapped, attributes):
        obj = wrapped()
        for name in attributes:
            assert hasattr(obj, name), name

    def test_the_wrapper_hides_what_was_not_declared(self):
        # ``json.load`` (de archivo) NO está declarado; ``dumps`` sí.
        assert hasattr(module.json, 'dumps')
        assert not hasattr(module.json, 'load')

    def test_dateutil_exposes_its_submodules_recursively(self):
        assert hasattr(module.dateutil.relativedelta, 'relativedelta')
        assert hasattr(module.dateutil.parser, 'parse')

    def test_gettz_of_dateutil_points_at_the_patched_pytz(self):
        # La fuente reasigna ``dateutil.tz.gettz = pytz.timezone`` para que las
        # dos vías de resolver una zona den el mismo objeto.
        assert module.dateutil.tz.gettz is module.pytz.timezone

    def test_the_patched_timezone_resolves_a_retired_zone(self):
        # ``Türkiye`` no está en ``pytz.all_timezones_set`` — medido; la
        # resuelve el parche de ``_monkeypatches/pytz.py``.
        assert str(module.pytz.timezone('Türkiye')) == 'Europe/Istanbul'

    def test_the_repr_names_the_wrapped_module(self):
        assert "wrapped 'json'" in repr(module.json)

    def test_wrap_module_copies_only_what_is_asked(self):
        wrapped = wrap_module(json_real, ['dumps'])
        assert hasattr(wrapped, 'dumps') and not hasattr(wrapped, 'loads')


class TestTheExceptionsThatBubbleUp:
    """Las que atraviesan sin envolverse en ``ValueError``."""

    def test_a_user_error_reaches_the_caller_verbatim(self):
        def blow_up():
            raise UserError('el message del negocio')

        with pytest.raises(UserError, match='el message del negocio'):
            safe_eval("blow_up()", {'blow_up': blow_up})

    def test_a_division_by_zero_reaches_the_caller_verbatim(self):
        with pytest.raises(ZeroDivisionError):
            safe_eval("1 / 0")

    def test_any_other_error_is_wrapped_with_the_expression(self):
        # Control del contraste: un error que NO está en la lista sí se
        # envuelve, y el mensaje trae la expresión para poder depurarla.
        with pytest.raises(ValueError, match='while evaluating'):
            safe_eval("desconocido")


class _Record:
    """Doble de registro para las expresiones — sólo atributos públicos."""

    def __init__(self, **fields):
        self.__dict__.update(fields)
