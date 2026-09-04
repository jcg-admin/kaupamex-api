"""``safe_eval`` — porte completo de ``odoo/tools/safe_eval.py`` (Odoo 19).

Adaptación de ``odoo/tools/safe_eval.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3 → copia con atribución, DEC-KX-03), más el parche de
zonas horarias de ``odoo/_monkeypatches/pytz.py``, que la fuente aplica
justo antes de exponer ``pytz`` aquí.

El módulo evalúa expresiones —y, en ``mode='exec'``, bloques— que vienen de
la base de datos y por tanto no son de fiar: el ``domain_force`` de una
``ir.rule``, el ``attachment`` de un ``ir.actions.report``, el ``code`` de
una ``ir.actions.server``, las expresiones de un archivo de datos XML.

**Cómo protege, que es lo que hay que entender antes de tocarlo.** No filtra
texto ni analiza el AST: **compila** la expresión y valida los *opcodes* del
bytecode resultante contra una lista blanca (``_SAFE_OPCODES``), recorriendo
además los objetos de código anidados de cada ``lambda``. Encima de eso:

- ningún nombre que contenga ``__`` ni ninguno de ``_UNSAFE_ATTRIBUTES``
  (``assert_no_dunder_name``) — cierra el camino de ``__class__``,
  ``__subclasses__`` y compañía, que es como se escapa de un evaluador;
- ``__builtins__`` sustituido por ``_BUILTINS``, un diccionario acotado sin
  ``open``, ``eval``, ``exec`` ni ``compile``;
- ``check_values`` rechaza un módulo entero en el contexto: para exponer uno
  se usa ``wrap_module``, que copia sólo los atributos declarados.

> **Sustituye a la versión de dominio de este archivo (tarea #140).** La
> anterior validaba el **AST** contra una lista blanca de la forma de un
> dominio —listas, tuplas, constantes, nombres y atributos simples— y
> declaraba en su propio docstring que un consumidor que necesitara más
> «amplía este módulo con la validación de opcodes de la referencia — no la
> esquiva». Este es ese pase: lo destapó ``retrieve_attachment`` de
> ``ir.actions.report``, que evalúa ``'INV_%s.pdf' % object.name`` y que bajo
> la versión de dominio moría en ``ValueError: nodo no permitido BinOp``.

Divergencias de stack, declaradas una por una (ninguna recorta el contrato):

- ``psycopg2.OperationalError`` / ``IntegrityError`` → ``django.db``, que es
  donde Django republica las de psycopg 3. Mismo rol: dejar que el reintento
  de transacción serializada haga su trabajo en vez de tragarse el error.
- ``werkzeug.exceptions.HTTPException`` → ``django.http.Http404`` y
  ``rest_framework.exceptions.APIException``. Werkzeug está excluido del
  stack por decisión del ejecutor (servimos con gunicorn); las dos clases que
  cumplen su papel —una excepción que *es* una respuesta HTTP y debe llegar
  entera a la capa de transporte— son ésas.
- ``odoo.exceptions`` → ``exceptions``, la raíz espejada de este árbol.

``pytz`` se declaró como dependencia en este pase: la fuente lo expone al
espacio de nombres de toda expresión almacenada, así que sin él el porte no
ofrecería el mismo contrato.
"""
import dis
import functools
import logging
import sys
import types
import typing
from opcode import opmap, opname
from types import CodeType

from django.db import IntegrityError, OperationalError
from django.http import Http404
from rest_framework.exceptions import APIException

import exceptions

unsafe_eval = eval

__all__ = ['const_eval', 'safe_eval']

# El módulo ``time`` suele estar ya en el entorno de ``safe_eval``, pero algún
# código —``datetime.datetime.now()``, por ejemplo— lo importa por su cuenta.
_ALLOWED_MODULES = ['_strptime', 'math', 'time']


# Simulacro de ``__import__``, tal como lo llama el emulador de importación de
# CPython (``PyImport_Import``) desde ``timemodule.c``, ``_datetimemodule.c`` y
# otros. No necesita hacer nada: su efecto esperado es que el módulo esté ya en
# ``sys.modules``, y por eso los ``_ALLOWED_MODULES`` se importan abajo.
def _import(name, globals=None, locals=None, fromlist=None, level=-1):
    if name not in sys.modules:
        raise ImportError(
            f'module {name} should be imported before calling safe_eval()')


for module in _ALLOWED_MODULES:
    __import__(module)


#: Atributos que exponen frames, código o el MRO — copia verbatim de
#: ``odoo19c: odoo/tools/safe_eval.py:52-70``. La referencia los usa en dos
#: sitios: su evaluador acotado y ``service/model.get_public_method``, que los
#: rechaza como nombre de método invocable remotamente. Se conserva el orden y
#: los comentarios de la fuente porque la lista **es** el contrato.
_UNSAFE_ATTRIBUTES = [
    # Frames
    'f_builtins', 'f_code', 'f_globals', 'f_locals', 'f_generator',
    # Python 2 functions
    'func_code', 'func_globals',
    # Code object
    'co_code', '_co_code_adaptive',
    # Method resolution order,
    'mro',
    # Tracebacks
    'tb_frame',
    # Generators
    'gi_code', 'gi_frame', 'gi_yieldfrom',
    # Coroutines
    'cr_await', 'cr_code', 'cr_frame',
    # Coroutine generators
    'ag_await', 'ag_code', 'ag_frame',
]


def to_opcodes(opnames, _opmap=opmap):
    for x in opnames:
        if x in _opmap:
            yield _opmap[x]


# Opcodes que absoluta y positivamente NO pueden usarse en ``safe_eval``; se
# restan explícitamente de todos los conjuntos válidos, por si acaso.
_BLACKLIST = set(to_opcodes([
    # no se puede dar acceso a módulos arbitrarios
    'IMPORT_STAR', 'IMPORT_NAME', 'IMPORT_FROM',
    # permitiría reemplazar o actualizar atributos del núcleo en modelos y
    # demás; ``setitem`` sirve para fijar valores de campo
    'STORE_ATTR', 'DELETE_ATTR',
    # no hay motivo para permitirlo
    'STORE_GLOBAL', 'DELETE_GLOBAL',
]))

# Opcodes necesarios para construir valores literales
_CONST_OPCODES = set(to_opcodes([
    # manipulación de la pila
    'POP_TOP', 'ROT_TWO', 'ROT_THREE', 'ROT_FOUR', 'DUP_TOP', 'DUP_TOP_TWO',
    'LOAD_CONST',
    'RETURN_VALUE',  # devuelve el resultado de la evaluación
    # colecciones literales
    'BUILD_LIST', 'BUILD_MAP', 'BUILD_TUPLE', 'BUILD_SET',
    # 3.6: mapa literal con claves constantes https://bugs.python.org/issue27140
    'BUILD_CONST_KEY_MAP',
    'LIST_EXTEND', 'SET_UPDATE',
    # 3.11 reemplaza DUP_TOP, DUP_TOP_TWO, ROT_TWO, ROT_THREE, ROT_FOUR
    'COPY', 'SWAP',
    # Añadidos en 3.11 https://docs.python.org/3/whatsnew/3.11.html#new-opcodes
    'RESUME',
    # 3.12 https://docs.python.org/3/whatsnew/3.12.html#cpython-bytecode-changes
    'RETURN_CONST',
    # 3.13
    'TO_BOOL',
    # 3.14 https://docs.python.org/3/whatsnew/3.14.html#cpython-bytecode-changes
    'LOAD_SMALL_INT',
])) - _BLACKLIST

# Operaciones que son binarias y en sitio a la vez, en el orden de la doc
_operations = [
    'POWER', 'MULTIPLY',  # 'MATRIX_MULTIPLY', # operador de matriz (3.5+)
    'FLOOR_DIVIDE', 'TRUE_DIVIDE', 'MODULO', 'ADD',
    'SUBTRACT', 'LSHIFT', 'RSHIFT', 'AND', 'XOR', 'OR',
]

# Operaciones sobre valores literales
_EXPR_OPCODES = _CONST_OPCODES.union(to_opcodes([
    'UNARY_POSITIVE', 'UNARY_NEGATIVE', 'UNARY_NOT', 'UNARY_INVERT',
    *('BINARY_' + op for op in _operations), 'BINARY_SUBSCR',
    *('INPLACE_' + op for op in _operations),
    'BUILD_SLICE',
    # comprensiones
    'LIST_APPEND', 'MAP_ADD', 'SET_ADD',
    'COMPARE_OP',
    # comparaciones especializadas
    'IS_OP', 'CONTAINS_OP',
    'DICT_MERGE', 'DICT_UPDATE',
    # se usa en cualquier "literal generador"
    'GEN_START',  # añadido en 3.10 y ya retirado en 3.11
    # Añadidos en 3.11, reemplazan a todos los BINARY_* e INPLACE_*
    'BINARY_OP',
    'BINARY_SLICE',
])) - _BLACKLIST

_SAFE_OPCODES = _EXPR_OPCODES.union(to_opcodes([
    'POP_BLOCK', 'POP_EXCEPT',

    # nota: retirados en 3.8
    'SETUP_LOOP', 'SETUP_EXCEPT', 'BREAK_LOOP', 'CONTINUE_LOOP',

    'EXTENDED_ARG',  # P3.6, para saltos largos
    'MAKE_FUNCTION', 'CALL_FUNCTION', 'CALL_FUNCTION_KW', 'CALL_FUNCTION_EX',
    # Añadidos en P3.7 https://bugs.python.org/issue26110
    'CALL_METHOD', 'LOAD_METHOD',

    'GET_ITER', 'FOR_ITER', 'YIELD_VALUE',
    'JUMP_FORWARD', 'JUMP_ABSOLUTE', 'JUMP_BACKWARD',
    'JUMP_IF_FALSE_OR_POP', 'JUMP_IF_TRUE_OR_POP',
    'POP_JUMP_IF_FALSE', 'POP_JUMP_IF_TRUE',
    'SETUP_FINALLY', 'END_FINALLY',
    # Añadidos en 3.8 https://bugs.python.org/issue17611
    'BEGIN_FINALLY', 'CALL_FINALLY', 'POP_FINALLY',

    'RAISE_VARARGS', 'LOAD_NAME', 'STORE_NAME', 'DELETE_NAME', 'LOAD_ATTR',
    'LOAD_FAST', 'STORE_FAST', 'DELETE_FAST', 'UNPACK_SEQUENCE',
    'STORE_SUBSCR',
    'LOAD_GLOBAL',

    'RERAISE', 'JUMP_IF_NOT_EXC_MATCH',

    # Los siguientes se añadieron en 3.11
    # reemplazo de CALL_FUNCTION, CALL_FUNCTION_KW, CALL_METHOD
    'PUSH_NULL', 'PRECALL', 'CALL', 'KW_NAMES',
    # reemplazo de POP_JUMP_IF_TRUE y POP_JUMP_IF_FALSE
    'POP_JUMP_FORWARD_IF_FALSE', 'POP_JUMP_FORWARD_IF_TRUE',
    'POP_JUMP_BACKWARD_IF_FALSE', 'POP_JUMP_BACKWARD_IF_TRUE',
    # caso especial del anterior para IS NONE / IS NOT NONE
    'POP_JUMP_FORWARD_IF_NONE', 'POP_JUMP_BACKWARD_IF_NONE',
    'POP_JUMP_FORWARD_IF_NOT_NONE', 'POP_JUMP_BACKWARD_IF_NOT_NONE',
    # reemplazo de JUMP_IF_NOT_EXC_MATCH
    'CHECK_EXC_MATCH',
    # opcodes nuevos
    'RETURN_GENERATOR',
    'PUSH_EXC_INFO',
    'NOP',
    'FORMAT_VALUE', 'BUILD_STRING',
    # 3.12 https://docs.python.org/3/whatsnew/3.12.html#cpython-bytecode-changes
    'END_FOR',
    'LOAD_FAST_AND_CLEAR', 'LOAD_FAST_CHECK',
    'POP_JUMP_IF_NOT_NONE', 'POP_JUMP_IF_NONE',
    'CALL_INTRINSIC_1',
    'STORE_SLICE',
    # 3.13
    'CALL_KW', 'LOAD_FAST_LOAD_FAST',
    'STORE_FAST_STORE_FAST', 'STORE_FAST_LOAD_FAST',
    'CONVERT_VALUE', 'FORMAT_SIMPLE', 'FORMAT_WITH_SPEC',
    'SET_FUNCTION_ATTRIBUTE',
    # 3.14
    # optimizaciones de LOAD_FAST
    'LOAD_FAST_BORROW', 'LOAD_FAST_BORROW_LOAD_FAST_BORROW',
    'POP_ITER',
    # Lista fija de constantes; no esquiva ``__builtins__``. Ver
    # https://github.com/python/cpython/blob/9181d776daf/Python/pylifecycle.c#L830-L836
    'LOAD_COMMON_CONSTANT',
    'NOT_TAKEN',
])) - _BLACKLIST


_logger = logging.getLogger(__name__)


def assert_no_dunder_name(code_obj, expr):
    """``assert_no_dunder_name(code_obj, expr) -> None``

    Comprueba que el objeto de código no referencia ningún "nombre dunder"
    (``__$name__``), de modo que ``safe_eval`` impide el acceso a cualquier
    atributo o método interno de Python (los dos se cargan con ``LOAD_ATTR``,
    que usa un nombre, no una constante ni una variable).

    Verifica que ese nombre no exista en el objeto de código dado
    (``co_names``).

    :param code_obj: objeto de código cuyos nombres se validan
    :type code_obj: CodeType
    :param str expr: expresión correspondiente al objeto de código, para
                     depuración
    :raises NameError: si aparece un nombre prohibido (con dos guiones bajos)

    .. note:: en realidad prohíbe todo nombre que contenga 2 guiones bajos
    """
    for name in code_obj.co_names:
        if "__" in name or name in _UNSAFE_ATTRIBUTES:
            raise NameError('Access to forbidden name %r (%r)' % (name, expr))


def assert_valid_codeobj(allowed_codes, code_obj, expr):
    """Comprueba que el objeto de código dado cumple las restricciones de
    bytecode y de nombres.

    Valida recursivamente los objetos de código guardados en ``co_consts``,
    por si se crean o usan ``lambda`` (cada una genera su propio objeto de
    código, que no vive en el raíz).

    :param allowed_codes: instrucciones de bytecode permitidas
    :type allowed_codes: set(int)
    :param code_obj: objeto de código a validar
    :type code_obj: CodeType
    :param str expr: expresión correspondiente al objeto de código, para
                     depuración
    :raises ValueError: si hay bytecode prohibido en ``code_obj``
    :raises NameError: si aparece un nombre prohibido (con dos guiones bajos)
    """
    assert_no_dunder_name(code_obj, expr)

    # las operaciones de conjunto son casi el doble de rápidas que iterar a
    # mano con una condición, al cargar /web según line_profiler
    code_codes = {i.opcode for i in dis.get_instructions(code_obj)}
    if not allowed_codes >= code_codes:
        raise ValueError("forbidden opcode(s) in %r: %s" % (
            expr, ', '.join(opname[x] for x in (code_codes - allowed_codes))))

    for const in code_obj.co_consts:
        if isinstance(const, CodeType):
            assert_valid_codeobj(allowed_codes, const, 'lambda')


def compile_codeobj(expr: str, /, filename: str = '<unknown>',
                    mode: typing.Literal['eval', 'exec'] = 'eval'):
    """
        :param str filename: pseudo-nombre de archivo opcional para la
                             expresión compilada, que se muestra por ejemplo
                             en los frames del traceback
        :param str mode: 'eval' si es una sola expresión
                         'exec' si es una secuencia de sentencias
        :return: objeto de código compilado
        :rtype: types.CodeType
    """
    assert mode in ('eval', 'exec')
    try:
        if mode == 'eval':
            # a eval() no le gustan los espacios de los extremos
            expr = expr.strip()
        code_obj = compile(expr, filename or '', mode)
    except (SyntaxError, TypeError, ValueError):
        raise
    except Exception as e:
        raise ValueError('%r while compiling\n%r' % (e, expr))
    return code_obj


def const_eval(expr):
    """``const_eval(expression) -> value``

    Evaluación segura de una constante de Python.

    Evalúa una cadena que contiene una expresión que describe una constante de
    Python. Una cadena que no sea una expresión válida, o que contenga algo más
    que la constante, levanta ``ValueError``.

    >>> const_eval("10")
    10
    >>> const_eval("[1,2, (3,4), {'foo':'bar'}]")
    [1, 2, (3, 4), {'foo': 'bar'}]
    >>> const_eval("1+2")
    Traceback (most recent call last):
    ...
    ValueError: opcode BINARY_ADD not allowed
    """
    c = compile_codeobj(expr)
    assert_valid_codeobj(_CONST_OPCODES, c, expr)
    return unsafe_eval(c)


def expr_eval(expr):
    """``expr_eval(expression) -> value``

    Evaluación restringida de una expresión de Python.

    Evalúa una cadena que contiene una expresión que sólo usa constantes de
    Python. Sirve, por ejemplo, para evaluar una expresión numérica de origen
    no confiable.

    >>> expr_eval("1+2")
    3
    >>> expr_eval("[1,2]*2")
    [1, 2, 1, 2]
    >>> expr_eval("__import__('sys').modules")
    Traceback (most recent call last):
    ...
    ValueError: opcode LOAD_NAME not allowed
    """
    c = compile_codeobj(expr)
    assert_valid_codeobj(_EXPR_OPCODES, c, expr)
    return unsafe_eval(c)


_BUILTINS = {
    '__import__': _import,
    'True': True,
    'False': False,
    'None': None,
    'bytes': bytes,
    'str': str,
    'unicode': str,
    'bool': bool,
    'int': int,
    'float': float,
    'enumerate': enumerate,
    'dict': dict,
    'list': list,
    'tuple': tuple,
    'map': map,
    'abs': abs,
    'min': min,
    'max': max,
    'sum': sum,
    'reduce': functools.reduce,
    'filter': filter,
    'sorted': sorted,
    'round': round,
    'len': len,
    'repr': repr,
    'set': set,
    'all': all,
    'any': any,
    'ord': ord,
    'chr': chr,
    'divmod': divmod,
    'isinstance': isinstance,
    'range': range,
    'xrange': range,
    'zip': zip,
    'Exception': Exception,
}


#: Excepciones que atraviesan ``safe_eval`` sin envolverse en ``ValueError``.
#: La fuente declara siete (``safe_eval.py:357-365``); aquí son ocho porque el
#: papel de ``werkzeug.exceptions.HTTPException`` —una excepción que *es* una
#: respuesta HTTP— lo cumplen dos clases en este stack.
_BUBBLEUP_EXCEPTIONS = (
    exceptions.ConcurrencyError,  # que el reintento maneje este error
    exceptions.UserError,
    exceptions.RedirectWarning,
    # que la reejecución automática de transacciones serializadas haga su magia
    OperationalError,
    IntegrityError,  # que el reintento maneje este error
    Http404,
    APIException,
    ZeroDivisionError,
)


def safe_eval(expr, /, context=None, *, mode="eval", filename=None):
    """Evaluación de expresiones de Python restringida por el sistema.

    Evalúa una cadena que contiene una expresión hecha sobre todo de
    constantes de Python, expresiones aritméticas y los objetos que el
    contexto provee directamente.

    Sirve, por ejemplo, para evaluar la expresión de un dominio de origen no
    confiable.

    :param expr: la expresión de Python (o el bloque, si ``mode='exec'``)
    :type expr: string | bytes
    :param context: espacio de nombres disponible para la expresión. Este
                    diccionario se MUTA con cualquier variable creada durante
                    la evaluación
    :type context: dict
    :param mode: ``exec`` o ``eval``
    :type mode: str
    :param filename: pseudo-nombre de archivo opcional para la expresión
                     compilada, que se muestra por ejemplo en los frames del
                     traceback
    :type filename: string
    :throws TypeError: si lo que se pasa es un objeto de código
    :throws SyntaxError: si la expresión no es Python válido
    :throws NameError: si la expresión accede a nombres prohibidos
    :throws ValueError: si la expresión usa bytecode prohibido
    """
    if type(expr) is CodeType:
        raise TypeError(
            "safe_eval does not allow direct evaluation of code objects.")

    assert context is None or type(context) is dict, "Context must be a dict"

    check_values(context)

    globals_dict = dict(context or {}, __builtins__=dict(_BUILTINS))

    c = compile_codeobj(expr, filename=filename, mode=mode)
    assert_valid_codeobj(_SAFE_OPCODES, c, expr)
    try:
        # un diccionario de locales vacío hace que eval se comporte como
        # código de nivel superior
        return unsafe_eval(c, globals_dict, None)

    except _BUBBLEUP_EXCEPTIONS:
        raise

    except Exception as e:
        raise ValueError('%r while evaluating\n%r' % (e, expr))

    finally:
        if context is not None:
            del globals_dict['__builtins__']
            context.update(globals_dict)


def test_python_expr(expr, mode="eval"):
    try:
        c = compile_codeobj(expr, mode=mode)
        assert_valid_codeobj(_SAFE_OPCODES, c, expr)
    except (SyntaxError, TypeError, ValueError) as err:
        if len(err.args) >= 2 and len(err.args[1]) >= 4:
            error = {
                'message': err.args[0],
                'filename': err.args[1][0],
                'lineno': err.args[1][1],
                'offset': err.args[1][2],
                'error_line': err.args[1][3],
            }
            msg = "%s : %s at line %d\n%s" % (
                type(err).__name__, error['message'], error['lineno'],
                error['error_line'])
        else:
            msg = str(err)
        return msg
    return False


def check_values(d):
    if not d:
        return d
    for v in d.values():
        if isinstance(v, types.ModuleType):
            raise TypeError(
                f"""Module {v} can not be used in evaluation contexts

Prefer providing only the items necessary for your intended use.

If a "module" is necessary for backwards compatibility, use
`tools.safe_eval.wrap_module` to generate a wrapper recursively
whitelisting allowed attributes.

Pre-wrapped modules are provided as attributes of `tools.safe_eval`.
""")
    return d


class wrap_module:
    def __init__(self, module, attributes):
        """Ayudante para envolver un paquete o módulo y exponer los atributos
        seleccionados.

        :param module: el paquete o módulo real a envolver, tal como lo
                       devuelve ``import <module>``
        :param iterable attributes: atributos a exponer. Si es un diccionario,
                                    las claves son los atributos y los valores
                                    se usan como ``attributes`` cuando el
                                    elemento correspondiente es un submódulo
        """
        # los módulos internos no tienen ``__file__`` en absoluto
        modfile = getattr(module, '__file__', '(built-in)')
        self._repr = f"<wrapped {module.__name__!r} ({modfile})>"
        for attrib in attributes:
            target = getattr(module, attrib)
            if isinstance(target, types.ModuleType):
                target = wrap_module(target, attributes[attrib])
            setattr(self, attrib, target)

    def __repr__(self):
        return self._repr


# los submódulos de dateutil son perezosos, así que hay que importarlos para
# que "existan"
import dateutil  # noqa: E402

mods = ['parser', 'relativedelta', 'rrule', 'tz']
for mod in mods:
    __import__('dateutil.%s' % mod)

# hay que parchear pytz antes de exponerlo
from _monkeypatches.pytz import patch_module as patch_pytz  # noqa: E402, F401

patch_pytz()

datetime = wrap_module(__import__('datetime'), [
    'date', 'datetime', 'time', 'timedelta', 'timezone', 'tzinfo',
    'MAXYEAR', 'MINYEAR'])
dateutil = wrap_module(dateutil, {
    "tz": ["UTC", "tzutc"],
    "parser": ["isoparse", "parse"],
    "relativedelta": [
        "relativedelta", "MO", "TU", "WE", "TH", "FR", "SA", "SU"],
    "rrule": [
        "rrule", "rruleset", "rrulestr", "YEARLY", "MONTHLY", "WEEKLY",
        "DAILY", "HOURLY", "MINUTELY", "SECONDLY",
        "MO", "TU", "WE", "TH", "FR", "SA", "SU"],
})
json = wrap_module(__import__('json'), ['loads', 'dumps'])
time = wrap_module(__import__('time'), [
    'time', 'strptime', 'strftime', 'sleep'])
pytz = wrap_module(__import__('pytz'), [
    'utc', 'UTC', 'timezone',
])
dateutil.tz.gettz = pytz.timezone
