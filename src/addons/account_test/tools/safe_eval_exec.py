r"""``safe_eval`` en modo ``exec`` — adaptación LOCAL de
``odoo/tools/safe_eval.py`` (Odoo 19).

Adaptación de ``odoo/tools/safe_eval.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, ``odoo19c:``,
LGPL-3 → copia con atribución, DEC-KX-03).

Por qué este módulo existe AQUÍ y no amplía ``api: src/tools/safe_eval.py``
================================================================================

``src/tools/safe_eval.py`` de este árbol declara explícitamente su propio
alcance: *"el único consumidor es ``ir.rule`` ... acotada a la forma de un
dominio (listas/tuplas de leaves) ... Si un consumidor futuro necesita
``mode='exec'`` (``ir.actions.server`` code, ``ir_cron``), ese pase amplía
este módulo con la validación de opcodes de la referencia — no la esquiva."``

``accounting.assert.test.code_exec`` es exactamente ese consumidor: bloques
de sentencias (``for``, ``if``, asignaciones, ``cr.execute(...)``), no una
expresión de dominio. Ampliar el módulo compartido significaría escribir
fuera de ``src/addons/account_test/`` — fuera del alcance de este porte ("no
tocar ningún otro addon"). El mismo problema ya lo resolvió
``account_tax_python/models/account_tax.py::_safe_eval`` de la misma forma:
un evaluador **local**, con su propia lista de opcodes seguros, en vez de
tocar el módulo compartido. Aquí el caso es más amplio (``mode='exec'``, no
sólo una expresión aritmética), así que se replica el mecanismo COMPLETO de
la referencia (validación de **bytecode**, no de AST) — construir, no evadir.

Mecanismo — igual que la referencia, opcodes en vez de AST
================================================================

La referencia valida el *bytecode compilado* contra una whitelist de
opcodes (``_SAFE_OPCODES``) más un chequeo de nombres "dunder"
(``assert_no_dunder_name``) — no un análisis de AST. Esa es la única forma
de permitir sentencias completas (``for``, ``if``, llamadas a método) sin
abrir la puerta a ``__import__``/``__globals__``/etc.

``to_opcodes`` de la referencia ya es version-portable: filtra por
pertenencia a ``opcode.opmap`` del intérprete actual, así que los nombres de
opcodes de versiones de Python que este intérprete no tiene se **saltan**
silenciosamente en vez de fallar. Por eso la lista completa de nombres se
copia tal cual (Python 3.6 a 3.14 incluidos) — es exactamente el mecanismo
que hace portable a la referencia, replicado aquí sin editarlo.

Reducciones declaradas frente a la referencia (consumidor más chico)
==========================================================================

- **Sin módulos wrapeados** (``datetime``/``dateutil``/``pytz``/``json``/
  ``time`` de ``wrap_module``): ninguno de los 6 registros semilla de
  ``data/accounting_assert_tests.py`` los usa (medido:
  ``grep -c "datetime\.\|dateutil\.\|pytz\." data/accounting_assert_tests.py``
  → 0). Si un consumidor futuro los necesita, se agregan aquí — mismo
  mecanismo ``wrap_module`` que la referencia, no un import directo.
- **``_BUILTINS`` reducido**: sin ``__import__`` (no hay ``_ALLOWED_MODULES``
  que preimportar — este consumidor no necesita ``time``/``math``), sin los
  alias Python 2 (``unicode``, ``xrange``). El resto —colecciones,
  comparación, agregación— se conserva íntegro.
- **``_BUBBLEUP_EXCEPTIONS`` reducido a** ``ZeroDivisionError``: los otros
  cinco de la referencia (``ConcurrencyError``, ``UserError``,
  ``RedirectWarning``, ``psycopg2.OperationalError/IntegrityError``,
  ``werkzeug.exceptions.HTTPException``) son tipos que no existen en este
  stack (Django/DRF, sin ``odoo.exceptions``/``werkzeug``); psycopg3
  (``psycopg.Error``) tampoco se reexpone aquí porque el código de prueba no
  captura excepciones de conexión — las deja subir como error 500, que es lo
  que un ``ProgrammingError`` de SQL malformado debe hacer.

Estas tres son reducciones de **superficie del consumidor**, no relajaciones
de seguridad: el whitelist de opcodes y el chequeo de nombres dunder se
copian íntegros.
"""
import dis
from opcode import opmap, opname
from types import CodeType

unsafe_eval = eval

__all__ = ['safe_eval']


# ─── Nombres "dunder" prohibidos (≙ _UNSAFE_ATTRIBUTES + assert_no_dunder_name) ──
_UNSAFE_ATTRIBUTES = [
    # Frames
    'f_builtins', 'f_code', 'f_globals', 'f_locals', 'f_generator',
    # Código
    'co_code', '_co_code_adaptive',
    # Method resolution order
    'mro',
    # Tracebacks
    'tb_frame',
    # Generadores
    'gi_code', 'gi_frame', 'gi_yieldfrom',
    # Corutinas
    'cr_await', 'cr_code', 'cr_frame',
    # Corutinas-generador
    'ag_await', 'ag_code', 'ag_frame',
]


def _to_opcodes(opnames, _opmap=opmap):
    """≙ ``to_opcodes`` de la referencia. Filtra por lo que este intérprete
    reconoce — hace la whitelist version-portable sin tocarla por versión."""
    for name in opnames:
        if name in _opmap:
            yield _opmap[name]


# Opcodes que NUNCA deben ser usables, restados de todos los conjuntos.
_BLACKLIST = set(_to_opcodes([
    'IMPORT_STAR', 'IMPORT_NAME', 'IMPORT_FROM',
    'STORE_ATTR', 'DELETE_ATTR',
    'STORE_GLOBAL', 'DELETE_GLOBAL',
]))

# Opcodes necesarios para construir literales.
_CONST_OPCODES = set(_to_opcodes([
    'POP_TOP', 'ROT_TWO', 'ROT_THREE', 'ROT_FOUR', 'DUP_TOP', 'DUP_TOP_TWO',
    'LOAD_CONST', 'RETURN_VALUE',
    'BUILD_LIST', 'BUILD_MAP', 'BUILD_TUPLE', 'BUILD_SET',
    'BUILD_CONST_KEY_MAP', 'LIST_EXTEND', 'SET_UPDATE',
    'COPY', 'SWAP', 'RESUME', 'RETURN_CONST', 'TO_BOOL', 'LOAD_SMALL_INT',
])) - _BLACKLIST

_operations = [
    'POWER', 'MULTIPLY', 'FLOOR_DIVIDE', 'TRUE_DIVIDE', 'MODULO', 'ADD',
    'SUBTRACT', 'LSHIFT', 'RSHIFT', 'AND', 'XOR', 'OR',
]

# Operaciones sobre literales.
_EXPR_OPCODES = _CONST_OPCODES.union(_to_opcodes([
    'UNARY_POSITIVE', 'UNARY_NEGATIVE', 'UNARY_NOT', 'UNARY_INVERT',
    *('BINARY_' + op for op in _operations), 'BINARY_SUBSCR',
    *('INPLACE_' + op for op in _operations),
    'BUILD_SLICE',
    'LIST_APPEND', 'MAP_ADD', 'SET_ADD',
    'COMPARE_OP', 'IS_OP', 'CONTAINS_OP',
    'DICT_MERGE', 'DICT_UPDATE',
    'GEN_START',
    'BINARY_OP', 'BINARY_SLICE',
])) - _BLACKLIST

# El conjunto completo — statements, llamadas, control de flujo, excepciones.
_SAFE_OPCODES = _EXPR_OPCODES.union(_to_opcodes([
    'POP_BLOCK', 'POP_EXCEPT',
    'SETUP_LOOP', 'SETUP_EXCEPT', 'BREAK_LOOP', 'CONTINUE_LOOP',
    'EXTENDED_ARG',
    'MAKE_FUNCTION', 'CALL_FUNCTION', 'CALL_FUNCTION_KW', 'CALL_FUNCTION_EX',
    'CALL_METHOD', 'LOAD_METHOD',
    'GET_ITER', 'FOR_ITER', 'YIELD_VALUE',
    'JUMP_FORWARD', 'JUMP_ABSOLUTE', 'JUMP_BACKWARD',
    'JUMP_IF_FALSE_OR_POP', 'JUMP_IF_TRUE_OR_POP',
    'POP_JUMP_IF_FALSE', 'POP_JUMP_IF_TRUE',
    'SETUP_FINALLY', 'END_FINALLY',
    'BEGIN_FINALLY', 'CALL_FINALLY', 'POP_FINALLY',
    'RAISE_VARARGS', 'LOAD_NAME', 'STORE_NAME', 'DELETE_NAME', 'LOAD_ATTR',
    'LOAD_FAST', 'STORE_FAST', 'DELETE_FAST', 'UNPACK_SEQUENCE',
    'STORE_SUBSCR', 'LOAD_GLOBAL',
    'RERAISE', 'JUMP_IF_NOT_EXC_MATCH',
    'PUSH_NULL', 'PRECALL', 'CALL', 'KW_NAMES',
    'POP_JUMP_FORWARD_IF_FALSE', 'POP_JUMP_FORWARD_IF_TRUE',
    'POP_JUMP_BACKWARD_IF_FALSE', 'POP_JUMP_BACKWARD_IF_TRUE',
    'POP_JUMP_FORWARD_IF_NONE', 'POP_JUMP_BACKWARD_IF_NONE',
    'POP_JUMP_FORWARD_IF_NOT_NONE', 'POP_JUMP_BACKWARD_IF_NOT_NONE',
    'CHECK_EXC_MATCH',
    'RETURN_GENERATOR', 'PUSH_EXC_INFO', 'NOP',
    'FORMAT_VALUE', 'BUILD_STRING',
    'END_FOR', 'LOAD_FAST_AND_CLEAR', 'LOAD_FAST_CHECK',
    'POP_JUMP_IF_NOT_NONE', 'POP_JUMP_IF_NONE',
    'CALL_INTRINSIC_1', 'STORE_SLICE',
    'CALL_KW', 'LOAD_FAST_LOAD_FAST',
    'STORE_FAST_STORE_FAST', 'STORE_FAST_LOAD_FAST',
    'CONVERT_VALUE', 'FORMAT_SIMPLE', 'FORMAT_WITH_SPEC',
    'SET_FUNCTION_ATTRIBUTE',
    'LOAD_FAST_BORROW', 'LOAD_FAST_BORROW_LOAD_FAST_BORROW',
    'POP_ITER', 'LOAD_COMMON_CONSTANT', 'NOT_TAKEN',
])) - _BLACKLIST


def _assert_no_dunder_name(code_obj, expr):
    """≙ ``assert_no_dunder_name``. Prohíbe cualquier nombre "dunder"
    (``__algo__``) referenciado por el código — es la puerta de
    ``LOAD_ATTR``/``LOAD_NAME`` hacia ``__globals__``/``__class__``/etc."""
    for name in code_obj.co_names:
        if '__' in name or name in _UNSAFE_ATTRIBUTES:
            raise NameError(
                'safe_eval: nombre prohibido %r (%r)' % (name, expr))


def _assert_valid_codeobj(allowed_codes, code_obj, expr):
    """≙ ``assert_valid_codeobj``. Recursivo sobre ``co_consts`` (lambdas)."""
    _assert_no_dunder_name(code_obj, expr)
    code_codes = {i.opcode for i in dis.get_instructions(code_obj)}
    if not allowed_codes >= code_codes:
        raise ValueError(
            'safe_eval: opcode(s) prohibido(s) en %r: %s'
            % (expr, ', '.join(opname[x] for x in (code_codes - allowed_codes))))
    for const in code_obj.co_consts:
        if isinstance(const, CodeType):
            _assert_valid_codeobj(allowed_codes, const, 'lambda')


def _compile_codeobj(expr, filename='<code_exec>', mode='exec'):
    """≙ ``compile_codeobj``."""
    try:
        if mode == 'eval':
            expr = expr.strip()
        return compile(expr, filename, mode)
    except (SyntaxError, TypeError, ValueError):
        raise
    except Exception as exc:
        raise ValueError('%r al compilar\n%r' % (exc, expr)) from exc


#: Builtins disponibles — subconjunto de la referencia sin
#: ``__import__``/alias Python 2 (ver la sección "Reducciones declaradas").
_BUILTINS = {
    'True': True, 'False': False, 'None': None,
    'bytes': bytes, 'str': str, 'bool': bool, 'int': int, 'float': float,
    'enumerate': enumerate, 'dict': dict, 'list': list, 'tuple': tuple,
    'set': set, 'map': map, 'filter': filter, 'zip': zip,
    'abs': abs, 'min': min, 'max': max, 'sum': sum, 'sorted': sorted,
    'round': round, 'len': len, 'repr': repr, 'all': all, 'any': any,
    'ord': ord, 'chr': chr, 'divmod': divmod, 'isinstance': isinstance,
    'range': range, 'Exception': Exception,
}

#: Excepciones que se re-lanzan sin envolver — reducido a la única con
#: sentido en este consumidor (ver "Reducciones declaradas").
_BUBBLEUP_EXCEPTIONS = (ZeroDivisionError,)


def safe_eval(expr, context=None, *, mode='exec', filename=None):
    """≙ ``safe_eval`` de la referencia, acotado a lo que
    ``accounting.assert.test.code_exec`` necesita.

    :param expr: el código (statements si ``mode='exec'``) a evaluar.
    :param context: namespace disponible — se MUTA con las variables creadas
        durante la evaluación (igual que la referencia: ``result``/
        ``column_order`` se leen de vuelta desde aquí).
    :param mode: ``'exec'`` (statements) o ``'eval'`` (una expresión).
    :param filename: pseudo-nombre de archivo para tracebacks.
    :raises SyntaxError: código Python inválido.
    :raises NameError: nombre dunder prohibido.
    :raises ValueError: opcode prohibido, o error durante la evaluación.
    """
    if isinstance(expr, CodeType):
        raise TypeError(
            'safe_eval no evalúa objetos code directamente.')
    assert context is None or isinstance(context, dict), (
        'El contexto debe ser un dict')

    globals_dict = dict(context or {}, __builtins__=dict(_BUILTINS))
    code_obj = _compile_codeobj(expr, filename=filename or '<code_exec>', mode=mode)
    _assert_valid_codeobj(_SAFE_OPCODES, code_obj, expr)
    try:
        return unsafe_eval(code_obj, globals_dict, None)
    except _BUBBLEUP_EXCEPTIONS:
        raise
    except Exception as exc:
        raise ValueError('%r al evaluar\n%r' % (exc, expr)) from exc
    finally:
        if context is not None:
            del globals_dict['__builtins__']
            context.update(globals_dict)
