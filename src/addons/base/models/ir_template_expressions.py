"""``ir.qweb`` — el motor de plantillas de la referencia.

Adaptación de ``odoo/addons/base/models/ir_template_expressions.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 3058 líneas). QWeb es un lenguaje de
plantillas **en XML**: los atributos ``t-*`` de un elemento son directivas
(``t-if``, ``t-foreach``, ``t-out``, ``t-call``…) y el motor las **compila a
código Python**, que luego se ejecuta con una lista blanca de opcodes.

De QWeb se porta el **mecanismo abstracto**, no su misión: ver la sección
«Qué se porta de QWeb, y qué NO» — el HTML aquí lo emite React.

Cubre los **2 enganches** que Enterprise 19 usa aquí
—``_prepare_environment`` y ``_get_template_cache_keys``—, los dos del
compilador. Tarea #78, :ref:`h-api-819`. Este párrafo los dio por portados
desde ese pase y **no existían** hasta que ``http_routing`` (#261) intentó
extender el primero: se portan con ``_get_converted_image_data_uri`` y
``QwebJSON``, que el primero publica.

Qué se porta de QWeb, y qué NO — corregido por el ejecutor 2026-08-29
=====================================================================

**Este bloque se escribió primero con un error de análisis, y el ejecutor lo
corrigió en el mismo pase.** Se conserva la corrección porque el error es la
parte instructiva.

La directiva fue: *"queremos implementar el comportamiento de QWeb en nuestro
stack tecnológico ... para que cuando se usen plantillas en xml, nosotros
también las usemos y las consideremos en nuestro stack de django rest
framework, considerando que se publicarán como API"*. Se leyó como *"portar el
compilador entero"*, y la corrección fue inmediata:

    *"creo que tu solicitud anterior está mal, no es portar el compilador
    QWeb entero porque nuestra web usa React y no analizaste eso, nosotros
    solo construimos api, para que sean consumidos por ui que es react"*.

**Dónde falló el análisis.** El docstring anterior daba dos razones para no
portar el compilador, y se descartaron las dos como si fueran del mismo tipo.
No lo son:

===============================================  ==========================
Razón del docstring anterior                     Qué clase de premisa es
===============================================  ==========================
"no hay plantillas que compilar" — 0 ``.xml``    **de estado**: el ejecutor
                                                 decide que sí las habrá
"el HTML lo genera React; el backend sirve       **de arquitectura**: no
JSON por DRF"                                    cambia porque se añada un
                                                 archivo XML
===============================================  ==========================

Sólo la primera es revocable por directiva. La segunda **decide el alcance**,
y se leyó como parte de la primera. QWeb existe para **emitir HTML a un
cliente web renderizado en servidor**; aquí ese cliente es React y el
backend entrega datos. Portar sus 23 directivas —``t-att``, ``t-tag-open``,
``t-call-assets``, ``t-field`` con sus 18 conversores— sería construir un
emisor de HTML que nadie consume.

Lo que SÍ se porta: el mecanismo abstracto
------------------------------------------

Lo que sobrevive a esa distinción, y es lo que la directiva pide de verdad,
es el **mecanismo**, no su misión: un lenguaje de plantillas **en XML**,
interpretado en servidor, **extensible por XPath**, cuya salida alimenta al
API. Eso ya existe aquí —``addons/base/report_template.py`` interpreta un
``<descriptor>`` XML hacia un ``dict``— y lo que le faltaba es la pieza que
lo hace potente sin hacerlo peligroso:

**el compilador de expresiones** (``_compile_expr`` y su familia). Convierte
``5 + a + b.c`` en ``5 + values.get('a') + values['b'].c`` y **valida el
resultado contra una lista blanca de opcodes** antes de que exista. Es
independiente de si la salida es HTML o JSON: sirve igual a un descriptor de
reporte que a cualquier plantilla futura.

Su guarda es lo que hace admisible compilar texto almacenado, que es lo que
``ir_rule``, ``ir.actions.server`` e ``ir_actions_report`` rechazaron cuando
no había con qué acotarlo. Hoy sí lo hay: ``src/tools/safe_eval.py`` porta la
maquinaria entera (tarea #140) y los cinco símbolos que el compilador
necesita están medidos presentes — ``assert_valid_codeobj``, ``_BUILTINS``,
``to_opcodes``, ``_EXPR_OPCODES`` y ``_BLACKLIST``.

No hace falta instalar nada
===========================

Medido en el ``venv`` de este árbol. Las tres dependencias de terceros del
compilador ya están declaradas en ``pyproject.toml``:

===============  =========  ==================================================
Paquete          Versión    Para qué lo usa el compilador
===============  =========  ==================================================
``lxml``         6.1.1      el árbol XML de la plantilla es su insumo
``markupsafe``   3.0.3      ``Markup``/``escape`` — el contrato de escapado
``dateutil``     2.9.0      ``relativedelta`` en el contexto de la plantilla
===============  =========  ==================================================

Y las dos que **no** se adoptan, con su sustituto exacto:

- ``werkzeug`` está **prohibido** en este árbol (usamos gunicorn) y la fuente
  lo usa en **dos** sitios: ``werkzeug.urls.url_encode`` (``:526``) y
  ``werkzeug.urls.url_quote_plus`` (``:1314``). Los dos tienen equivalente
  literal en ``urllib.parse`` — ``urlencode`` y ``quote_plus``—, y la propia
  fuente ya importa ``unquote_plus`` de ahí (``:394``).
- ``psycopg2`` → **psycopg 3**, que declara los dos errores que el compilador
  atrapa: ``SerializationFailure`` (el ``TransactionRollbackError`` de
  psycopg2) y ``ReadOnlySqlTransaction``.

Lo que este archivo NO porta, y por qué
=======================================

**El compilador de nodos y las 23 directivas** — ``_compile_node``,
``_compile_directives``, ``_compile_directive_*``, ``_render``,
``_render_iterall`` y las cuatro estructuras ``Qweb*`` que la máquina de pila
usa. Todos existen para **emitir HTML**, y aquí el HTML lo emite React.

**``t-call-assets`` y los ~12 ``_get_asset_*``** — dependen de
``AssetsBundle``, el empaquetador de assets del cliente web. Aquí eso vive en
``ui/`` con Webpack.

Lo que queda **abierto y con sucesor**: hoy ``report_template.py`` evalúa sus
expresiones con el motor de plantillas de Django (DTL, ``{{ }}``) y este
archivo aporta un segundo evaluador. Dos motores para el mismo trabajo es una
decisión, no una derivación — tarea **#181**.

Qué se conserva del porte anterior
==================================

- **``MALICIOUS_SCHEMES``** — el detector de ``javascript:`` en una URL, con
  su excepción exacta: se permite si va seguido **sólo** de
  ``[window.]history.back()``. Primitiva de seguridad, verbatim.
- **``VOID_ELEMENTS``** — los 16 elementos HTML sin cierre.
- **``ALLOWED_KEYWORD``**, ``SPECIAL_DIRECTIVES``, ``T_CALL_SLOT`` y las cinco
  expresiones regulares de recorte: el vocabulario de QWeb.
- **``_directives_eval_order``** — el orden de evaluación de las directivas.
  Es la pieza con más conocimiento acumulado del archivo: dice que en
  ``<el t-foreach="foo" t-as="bar" t-if="bar">`` el ``foreach`` corre **antes**
  que el ``if``, y que ``elif``/``else`` van primeros porque los compila el
  ``if`` anterior. Invertir dos entradas da un motor que compila y produce
  resultados equivocados en silencio.
- **``keep_query``** — con la firma cambiada, por el mismo motivo de siempre:
  la fuente lee el ``request`` global de Werkzeug; aquí los parámetros entran
  por argumento.
- **``TemplateError`` / ``TemplateErrorInfo``** — el error con su contexto.
"""
import base64
import fnmatch
import hashlib
import io
import logging
import math
import re
import token
import tokenize
from urllib.parse import quote_plus, urlencode

from dateutil.relativedelta import relativedelta

from addons.base.models.ir_attachment import IrAttachment
from addons.base.models.ir_http import get_current_request
from orm import registry
from orm.environments import env, get_context
from tools import config
from tools.image import FILETYPE_BASE64_MAGICWORD, image_data_uri
from tools.json import JSON
from tools.safe_eval import (
    _BLACKLIST,
    _BUILTINS,
    _EXPR_OPCODES,
    assert_valid_codeobj,
    to_opcodes,
)
from tools.safe_eval import datetime as safe_datetime
from tools.safe_eval import time as safe_time
from tools.translate import FORMAT_REGEX

_logger = logging.getLogger(__name__)

#: Elementos HTML sin etiqueta de cierre — verbatim de la fuente.
VOID_ELEMENTS = frozenset([
    'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'keygen',
    'link', 'menuitem', 'meta', 'param', 'source', 'track', 'wbr',
])

#: Palabras clave admitidas al compilar una expresión, además de los objetos
#: disponibles — verbatim de la fuente, ``_BUILTINS`` incluido.
#:
#: La versión anterior excluía ``_BUILTINS`` diciendo que ``safe_eval`` era
#: *"un módulo distinto que este árbol no porta"*. Eso dejó de ser cierto con
#: la tarea #140: ``src/tools/safe_eval.py`` lo porta entero. Sin los builtins
#: una expresión tan corriente como ``t-if="len(docs) > 1"`` compilaría a
#: ``values.get('len')`` y evaluaría a ``None``.
ALLOWED_KEYWORD = frozenset([
    'False', 'None', 'True', 'and', 'as', 'elif', 'else', 'for', 'if', 'in',
    'is', 'not', 'or',
]) | set(_BUILTINS)

#: Atributos usados fuera del contexto de QWeb.
SPECIAL_DIRECTIVES = frozenset({'t-translation', 't-ignore', 't-title'})

#: Nombre de la variable donde ``t-call`` inserta el contenido del llamador.
T_CALL_SLOT = '0'

RSTRIP_REGEXP = re.compile(r'\n[ \t]*$')
LSTRIP_REGEXP = re.compile(r'^[ \t]*\n')
FIRST_RSTRIP_REGEXP = re.compile(r'^(\n[ \t]*)+(\n[ \t])')
VARNAME_REGEXP = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
TO_VARNAME_REGEXP = re.compile(r'[^A-Za-z0-9_]+')

#: Espacio en blanco **y** los caracteres de control que un navegador ignora
#: dentro de un atributo — por eso el rango va más allá de ``\s``.
WHITESPACE_REGEX = re.compile(r'[\s\x00-\x08\x0B\x0C\x0E-\x19]+')

#: Sólo se admite un esquema ``javascript:`` si va seguido de
#: ``[window.]history.back()`` y **nada más** (el ``$`` del lookahead).
#: Verbatim de la fuente; ver el docstring del módulo sobre por qué esta
#: primitiva vale con o sin QWeb.
MALICIOUS_SCHEMES = re.compile(
    r'javascript:(?!((window\.)?)history\.back\(\)$)', re.I).findall

#: Tipo de token propio del compilador — verbatim de la fuente (``:418-419``).
#: ``_compile_expr_tokens`` colapsa cada nivel de paréntesis ya compilado en un
#: único token de este tipo, y el siguiente nivel lo trata como opaco. Sin un
#: tipo propio ese token pasaría por ``NAME`` y se le volvería a aplicar el
#: espacio de nombres.
token.QWEB = token.NT_OFFSET - 1
token.tok_name[token.QWEB] = 'QWEB'

#: Los opcodes que el código generado por el compilador puede contener —
#: verbatim de la fuente (``:420-462``), sobre los ``_EXPR_OPCODES`` de
#: ``safe_eval`` y menos su ``_BLACKLIST``.
#:
#: **Es la guarda que hace portable al compilador.** Una plantilla es texto de
#: la base que acaba siendo bytecode; lo que acota esa ejecución no es la
#: gramática de QWeb sino esta lista, y por eso se porta entera y no
#: "adaptada". Los nombres cubren varias versiones de CPython a propósito: un
#: opcode que no existe en la versión en curso lo descarta ``to_opcodes``, así
#: que sobra pero no estorba; uno que falte **bloquea una plantilla legítima**.
_SAFE_QWEB_OPCODES = _EXPR_OPCODES.union(to_opcodes([
    'MAKE_FUNCTION', 'CALL_FUNCTION', 'CALL_FUNCTION_KW', 'CALL_FUNCTION_EX',
    'CALL_METHOD', 'LOAD_METHOD',

    'GET_ITER', 'FOR_ITER', 'YIELD_VALUE',
    'JUMP_FORWARD', 'JUMP_ABSOLUTE', 'JUMP_BACKWARD',
    'JUMP_IF_FALSE_OR_POP', 'JUMP_IF_TRUE_OR_POP',
    'POP_JUMP_IF_FALSE', 'POP_JUMP_IF_TRUE',

    'LOAD_NAME', 'LOAD_ATTR',
    'LOAD_FAST', 'STORE_FAST', 'UNPACK_SEQUENCE',
    'STORE_SUBSCR',
    'LOAD_GLOBAL',
    'EXTENDED_ARG',
    # Añadidos en 3.11
    'RESUME',
    'CALL',
    'PRECALL',
    'PUSH_NULL',
    'KW_NAMES',
    'FORMAT_VALUE', 'BUILD_STRING',
    'RETURN_GENERATOR',
    'SWAP',
    'POP_JUMP_FORWARD_IF_FALSE', 'POP_JUMP_FORWARD_IF_TRUE',
    'POP_JUMP_BACKWARD_IF_FALSE', 'POP_JUMP_BACKWARD_IF_TRUE',
    'POP_JUMP_FORWARD_IF_NONE', 'POP_JUMP_FORWARD_IF_NOT_NONE',
    'POP_JUMP_BACKWARD_IF_NONE', 'POP_JUMP_BACKWARD_IF_NOT_NONE',
    # Añadidos en 3.12
    'END_FOR',
    'LOAD_FAST_AND_CLEAR',
    'POP_JUMP_IF_NOT_NONE', 'POP_JUMP_IF_NONE',
    'RERAISE',
    'CALL_INTRINSIC_1',
    'STORE_SLICE',
    # Añadidos en 3.13
    'CALL_KW', 'LOAD_FAST_LOAD_FAST',
    'STORE_FAST_STORE_FAST', 'STORE_FAST_LOAD_FAST',
    'CONVERT_VALUE', 'FORMAT_SIMPLE', 'FORMAT_WITH_SPEC',
    'SET_FUNCTION_ATTRIBUTE',
    # Añadidos en 3.14
    'LOAD_FAST_BORROW', 'LOAD_FAST_BORROW_LOAD_FAST_BORROW',
    'POP_ITER', 'LOAD_COMMON_CONSTANT', 'NOT_TAKEN',
])) - _BLACKLIST


class TemplateErrorInfo:
    """Contexto de un error de plantilla — ``TemplateErrorInfo`` de la fuente.

    Lleva dónde falló (plantilla, línea, elemento) además del error, porque
    un fallo de plantilla sin esa localización es casi inútil para quien la
    escribió.
    """

    def __init__(self, message, template=None, path=None, line=None):
        self.message = message
        self.template = template
        self.path = path
        self.line = line

    def __str__(self):
        location = ', '.join(
            f'{label}={value!r}'
            for label, value in (
                ('plantilla', self.template),
                ('ruta', self.path),
                ('línea', self.line),
            )
            if value is not None
        )
        return f'{self.message} [{location}]' if location else self.message


class TemplateError(Exception):
    """Error de plantilla con su contexto (``TemplateError`` de la fuente)."""

    def __init__(self, info):
        self.info = info if isinstance(info, TemplateErrorInfo) \
            else TemplateErrorInfo(str(info))
        super().__init__(str(self.info))


def keep_query(current_params=None, *keep_params, **additional_params):
    """``keep_query`` — cadena de consulta que preserva los parámetros pedidos.

    Los nombres de ``keep_params`` admiten comodines
    (``keep_query(params, 'search', 'shop_*', page=4)``). Sin argumentos se
    conserva **todo** (``'*'``), que es el comportamiento de la fuente. Un
    parámetro pasado explícitamente en ``additional_params`` **gana** sobre el
    conservado; ése es el punto de la función y por eso el filtro lo excluye.

    Divergencia de firma declarada: la fuente lee el ``request`` global de
    Werkzeug (``request.httprequest.args``). Aquí los parámetros actuales
    entran como primer argumento —un ``QueryDict`` de Django o un dict de
    listas—, porque un modelo que lee un global de petición no es testeable y
    Django no tiene ese global.
    """
    if not keep_params and not additional_params:
        keep_params = ('*',)
    params = dict(additional_params)
    current_params = current_params or {}
    keys = list(current_params)
    for pattern in keep_params:
        for name in fnmatch.filter(keys, pattern):
            if name in additional_params:
                continue
            value = current_params[name]
            params[name] = (
                list(value) if isinstance(value, (list, tuple)) else [value])
    return urlencode(params, doseq=True)


class QwebJSON(JSON):
    """≙ ``QwebJSON`` (``odoo19c: base/models/ir_qweb.py:672-680``).

    El ``json`` que ``_prepare_environment`` publica a las plantillas: el
    ``dumps`` seguro de :class:`tools.json.JSON` más un ``default`` que
    convierte a texto un fragmento renderizado antes de serializarlo. La
    fuente reconoce ese fragmento por su clase (``QwebContent``); aquí no hay
    fragmento renderizado —el motor no se porta, ver el docstring de
    :class:`IrTemplateExpressions`— y se reconoce por el protocolo que esa
    clase implementa: ``__html__``. Cualquier ``default`` que el llamador pase
    sigue aplicándose después, como allá.
    """

    def dumps(self, *args, **kwargs):
        prev_default = kwargs.pop('default', lambda obj: obj)
        return super().dumps(*args, **kwargs, default=(
            lambda obj: prev_default(
                str(obj) if hasattr(obj, '__html__') else obj)
        ))


#: ≙ ``qwebJSON = QwebJSON()`` (``:680``).
qwebJSON = QwebJSON()


class IrTemplateExpressions:
    """El compilador de expresiones y el catálogo de directivas — **no** el motor.

    El nombre de la clase dice lo que hay, no lo que hay en la referencia:
    aquí ``render`` levanta (ver abajo), así que llamarla «motor de
    plantillas» inducía a creer que este árbol renderiza QWeb. Ese era el
    motivo del renombre — directiva del ejecutor 2026-08-29: *"tenemos que
    quitar el nombre, porque puedes estar tentado a seguir pensando que
    usamos QWeb"*.

    ``_name`` y ``_description`` **sí** se conservan verbatim: son la
    identidad de la entidad en el porte, y es el mismo trato que
    ``SystemParameter`` recibe con su ``_name = ir.config_parameter``
    (``scripts/check_porte_completo.py``, ``PORTE_ALIAS``). La clase se llama
    por lo que es aquí; el ``_name`` prueba que es la misma entidad y no un
    homónimo.

    En la referencia es ``models.AbstractModel``; aquí es una **clase llana**,
    por el mismo camino que ``IrFieldsConverter`` (``ir_fields.py:152``): un
    modelo sin columnas no necesita pasar por ``ModelBase``, y hacerlo tiene
    un coste que aquí importa.

    **Por qué llana y no ``Meta.abstract = True``.** Django prohíbe
    instanciar un modelo abstracto (``"Abstract models cannot be
    instantiated"``), y los métodos de la fuente reciben ``self`` — allá un
    *recordset* vacío, que es exactamente lo que aquí es una instancia sin
    fila. Con ``Meta.abstract`` habría que degradarlos a ``classmethod``, y
    eso **cambia la firma de 85 métodos**: el guion bajo se porta y la firma
    también (``porte-completo-no-parcial.md``). Una clase llana conserva las
    dos.

    Los dos atributos de clase son los que la fuente declara (``:691-692``),
    medidos con el recorrido AST de ``atributos-de-clase-de-modelo.md``: no
    hay un tercero que omitir. ``_name`` es la clave con la que
    ``registry.model_by_name('ir.qweb')`` la resuelve — ≙ el
    ``env['ir.qweb']`` de allá, que es como la nombran los cuatro addons que
    esperan por el motor.
    """

    _name = 'ir.qweb'
    _description = 'Qweb'

    # ------------------------------------------------------------------ #
    #  Compilación de expresiones y de cadenas de formato                 #
    #  (fuente ``:1388-1627``) — el bloque A de la tarea #181.            #
    # ------------------------------------------------------------------ #

    def _is_static_node(self, el, compile_context):
        """≙ ``_is_static_node`` (``odoo19c: :1388``).

        Un nodo es estático cuando no lleva ningún atributo ``t-*`` y por
        tanto sus atributos no necesitan render dinámico. ``t-tag-open`` y
        ``t-inner-content`` se excluyen porque son directivas **técnicas**
        que el propio compilador añade, no del autor de la plantilla.
        """
        return el.tag != 't' and 'groups' not in el.attrib and not any(
            att.startswith('t-')
            and att not in ('t-tag-open', 't-inner-content')
            for att in el.attrib
        )

    def _compile_format(self, expr):
        """≙ ``_compile_format`` (``odoo19c: :1400``).

        Compila una cadena de formato a **una sola** expresión con ``%``, que
        es más rápido que concatenar. Los dos estilos que
        :data:`~tools.translate.FORMAT_REGEX` reconoce::

            <t t-setf-name="Hello #{world} %s !"/>
            → values['name'] = 'Hello %s %%s !' % (values['world'],)

        El ``%`` literal del texto se duplica **antes** de sustituir, si no el
        formateo final lo consumiría como marcador.
        """
        values = [
            f'self._compile_to_str('
            f'{self._compile_expr(m.group(1) or m.group(2))})'
            for m in FORMAT_REGEX.finditer(expr)
        ]
        if not values:
            return repr(expr)
        code = repr(FORMAT_REGEX.sub('%s', expr.replace('%', '%%')))
        code += f' % ({", ".join(values)},)'
        return code

    def _compile_expr_tokens(self, tokens, allowed_keys, argument_names=None,
                             raise_on_missing=False):
        """≙ ``_compile_expr_tokens`` (``odoo19c: :1419``).

        Convierte la lista de tokens en una instrucción de Python en forma de
        texto, añadiendo el espacio de nombres de los valores dinámicos::

            5 + a + b.c   →   5 + values.get('a') + values['b'].c

        Un valor desconocido vale ``None``; pero cuando de él se pide un
        atributo o un índice se emite ``values['b']`` en vez de
        ``values.get('b')`` — así el error es ``KeyError: 'b'``, que dice qué
        falta, y no ``AttributeError: 'NoneType' object has no attribute 'c'``,
        que no.

        **Los ámbitos anidados se resuelven por recursión sobre los
        paréntesis.** Las variables locales de una ``lambda`` o de una
        comprensión NO llevan espacio de nombres —son locales— mientras que
        las libres sí::

            lambda a: a + b        →  lambda _arg_a__: _arg_a__ + values['b']
            [a + b for a in c]     →  [_arg_a__ + values.get('b')
                                       for _arg_a__ in values.get('c')]

        Cada nivel de paréntesis se procesa por separado y se colapsa en un
        token :data:`token.QWEB`, para que no haya confusión entre lambdas o
        comprensiones anidadas.
        """
        bracket_depth = 0

        argument_name = '_arg_%s__'
        argument_names = argument_names or []

        # Primera pasada: recolectar los nombres locales que este nivel de
        # paréntesis introduce (parámetros de lambda, variables de bucle).
        for index, t in enumerate(tokens):
            if t.exact_type in (token.LPAR, token.LSQB, token.LBRACE):
                bracket_depth += 1
            elif t.exact_type in (token.RPAR, token.RSQB, token.RBRACE):
                bracket_depth -= 1
            elif bracket_depth == 0 and t.exact_type == token.NAME:
                string = t.string
                if string == 'lambda':
                    for i in range(index + 1, len(tokens)):
                        t = tokens[i]
                        if t.exact_type == token.NAME:
                            argument_names.append(t.string)
                        elif t.exact_type == token.COMMA:
                            pass
                        elif t.exact_type == token.COLON:
                            break
                        elif t.exact_type == token.EQUAL:
                            raise NotImplementedError(
                                'Lambda default values are not supported')
                        else:
                            raise NotImplementedError(
                                'This lambda code style is not implemented.')
                elif string == 'for':
                    for i in range(index + 1, len(tokens)):
                        t = tokens[i]
                        if t.exact_type == token.NAME:
                            if t.string == 'in':
                                break
                            argument_names.append(t.string)
                        elif t.exact_type in (token.COMMA, token.LPAR,
                                              token.RPAR):
                            pass
                        else:
                            raise NotImplementedError(
                                'This loop code style is not implemented.')

        # Segunda pasada: compilar recursivamente cada sub-ámbito y colapsarlo
        # en un token QWEB, con los nombres locales ya recogidos arriba.
        index = 0
        open_bracket_index = -1
        bracket_depth = 0

        while index < len(tokens):
            t = tokens[index]

            if t.exact_type in (token.LPAR, token.LSQB, token.LBRACE):
                if bracket_depth == 0:
                    open_bracket_index = index
                bracket_depth += 1
            elif t.exact_type in (token.RPAR, token.RSQB, token.RBRACE):
                bracket_depth -= 1
                if bracket_depth == 0:
                    code = self._compile_expr_tokens(
                        tokens[open_bracket_index + 1:index],
                        list(allowed_keys),
                        list(argument_names),
                        raise_on_missing,
                    )
                    code = tokens[open_bracket_index].string + code + t.string
                    tokens[open_bracket_index:index + 1] = [
                        tokenize.TokenInfo(
                            token.QWEB, code,
                            tokens[open_bracket_index].start, t.end, '')]
                    index = open_bracket_index

            index += 1

        # Tercera pasada: emitir el texto, poniendo el espacio de nombres a
        # cada nombre que no sea local ni palabra clave permitida.
        code = []
        index = 0
        pos = tokens and tokens[0].start   # conserva el nivel en multilínea
        while index < len(tokens):
            t = tokens[index]
            string = t.string

            if t.start[0] != pos[0]:
                pos = (t.start[0], 0)
            space = t.start[1] - pos[1]
            if space:
                code.append(' ' * space)
            pos = t.start

            if t.exact_type == token.NAME:
                if '__' in string:
                    raise SyntaxError(
                        "Using variable names with '__' is not allowed: "
                        f'{string!r}')
                if string == 'lambda':
                    code.append('lambda ')
                    index += 1
                    while index < len(tokens):
                        t = tokens[index]
                        if (t.exact_type == token.NAME
                                and t.string in argument_names):
                            code.append(argument_name % t.string)
                        if t.exact_type in (token.COMMA, token.COLON):
                            code.append(t.string)
                        if t.exact_type == token.COLON:
                            break
                        index += 1
                    if t.end[0] != pos[0]:
                        pos = (t.end[0], 0)
                    else:
                        pos = t.end
                elif string in argument_names:
                    code.append(argument_name % t.string)
                elif string in allowed_keys:
                    code.append(string)
                elif (index + 1 < len(tokens)
                        and tokens[index + 1].exact_type == token.EQUAL):
                    code.append(string)          # argumento por nombre
                elif (index > 0 and tokens[index - 1]
                        and tokens[index - 1].exact_type == token.DOT):
                    code.append(string)          # atributo tras un punto
                elif raise_on_missing or (
                        index + 1 < len(tokens)
                        and tokens[index + 1].exact_type in (
                            token.DOT, token.LPAR, token.LSQB, token.QWEB)):
                    # ``values['product'].price`` para que el error nombre el
                    # valor que falta, no el atributo del ``None``.
                    code.append(f'values[{string!r}]')
                else:
                    # sólo lectura: no se admite asignación
                    code.append(f'values.get({string!r})')
            elif t.type not in (tokenize.ENCODING, token.ENDMARKER,
                                token.DEDENT):
                code.append(string)

            if t.end[0] != pos[0]:
                pos = (t.end[0], 0)
            else:
                pos = t.end

            index += 1

        return ''.join(code)

    def _compile_expr(self, expr, raise_on_missing=False):
        """≙ ``_compile_expr`` (``odoo19c: :1576``).

        Tokeniza la expresión y delega en :meth:`_compile_expr_tokens`. Los
        paréntesis que envuelven al texto no son cosmética: permiten compilar
        expresiones **multilínea**, que existen en plantillas reales.

        :param raise_on_missing: emite ``values['product'].price`` en vez de
            ``values.get('product').price``, para que el fallo nombre el valor
            ausente y no el atributo de un ``None``.

        El resultado se valida contra :data:`_SAFE_QWEB_OPCODES` **antes** de
        devolverse. Ésa es la guarda que hace admisible compilar texto
        almacenado: sin ella el porte del compilador no sería defendible.
        """
        readable = io.BytesIO(f"({expr or ''})".encode('utf-8'))
        try:
            tokens = list(tokenize.tokenize(readable.readline))
        except tokenize.TokenError:
            raise ValueError(f'Can not compile expression: {expr}')

        expression = self._compile_expr_tokens(
            tokens, ALLOWED_KEYWORD, raise_on_missing=raise_on_missing)

        assert_valid_codeobj(
            _SAFE_QWEB_OPCODES, compile(expression, '<>', 'eval'), expr)

        return f'({expression})'

    def _compile_bool(self, attr, default=False):
        """≙ ``_compile_bool`` (``odoo19c: :1603``) — el atributo como booleano.

        El vocabulario es el de un atributo XML, no el de Python: ``'false'`` y
        ``'0'`` son falsos, ``'true'`` y ``'1'`` verdaderos, y cualquier otra
        cadena cae al ``default``. ``bool('false')`` de Python daría ``True``,
        que es justo el error que este método existe para no cometer.
        """
        if attr:
            if attr is True:
                return True
            attr = attr.lower()
            if attr in ('false', '0'):
                return False
            elif attr in ('true', '1'):
                return True
        return bool(default)

    def _compile_to_str(self, expr):
        """≙ ``_compile_to_str`` (``odoo19c: :1615``) — texto de cualquier valor.

        ``None`` y ``False`` dan cadena vacía; ``bytes`` se decodifica; el
        resto pasa por ``str``. La distinción de ``False`` es deliberada: un
        campo booleano vacío no debe imprimir ``"False"`` en el documento.
        """
        if expr is None or expr is False:
            return ''

        if isinstance(expr, str):
            return expr
        elif isinstance(expr, bytes):
            return expr.decode()
        else:
            return str(expr)

    # ------------------------------------------------------------------ #
    #  Orden de evaluación de directivas                                  #
    # ------------------------------------------------------------------ #

    def _directives_eval_order(self):
        """≙ ``_directives_eval_order`` (``odoo19c: :1629``) — verbatim.

        Es una **lista ordenada, no un conjunto**: intercambiar dos entradas
        produce un motor que compila igual y da resultados distintos sin
        avisar. Los dos casos que la fuente explica y que la lista codifica:

        - ``elif`` y ``else`` van **primeros** porque los compila el ``if``
          anterior, no ellos mismos;
        - ``foreach`` va **antes** que ``if``, así que
          ``<el t-foreach="foo" t-as="bar" t-if="bar">`` equivale a un
          ``foreach`` que envuelve a un ``if``, y no al revés.
        """
        return [
            'elif',   # primero: lo compila el ``if`` anterior
            'else',   # primero: lo compila el ``if`` anterior
            'debug',
            'groups',
            'as', 'foreach',
            'if',
            'call-assets',
            'lang',
            'options',
            'call',
            'att',
            'field', 'esc', 'raw', 'out',
            'tag-open',
            'set',
            'inner-content',
            'tag-close',
        ]

    def directive_attribute_names(self):
        """Los atributos ``t-*`` que corresponden al orden de evaluación.

        **Forma propia**, declarada como tal: la fuente no la tiene. Es azúcar
        de lectura — convierte la lista de directivas en los nombres tal como
        aparecen en una plantilla, que es como los ve quien la escribe. Sin
        guion bajo porque es API nuestra, no un símbolo reservado de la
        fuente.
        """
        return [f't-{name}' for name in self._directives_eval_order()]

    @staticmethod
    def has_malicious_scheme(value):
        """¿La URL trae un ``javascript:`` que no sea el ``history.back()``?

        Envuelve ``MALICIOUS_SCHEMES`` para que el punto de uso lea como una
        pregunta y no como un ``findall`` suelto.
        """
        return bool(MALICIOUS_SCHEMES(value or ''))

    def _get_template_cache_keys(self):
        """≙ ``_get_template_cache_keys`` (``odoo19c: :951-953``) — verbatim.

        Las claves de contexto que distinguen una compilación de otra en la
        caché de ``_compile``. Es uno de los dos enganches que Enterprise 19
        consulta (:ref:`h-api-819`); hasta este pase el docstring del módulo
        lo daba por portado y no existía.
        """
        return ['lang', 'inherit_branding', 'inherit_branding_auto',
                'edit_translations', 'profile']

    def _get_converted_image_data_uri(self, base64_source):
        """≙ ``_get_converted_image_data_uri`` (``odoo19c: :1269-1291``).

        Con ``webp_as_jpg`` en el contexto, una imagen WEBP se sustituye por
        su conversión JPEG ya adjunta —un ``ir.attachment`` cuyo
        ``res_model``/``res_id`` apuntan al adjunto original, localizado por
        el SHA1 del binario, que es el ``checksum`` que ``IrAttachment.save()``
        calcula— porque el rasterizador no entiende WEBP. Sin conversión, o
        sin el contexto, devuelve la URL ``data:`` del binario tal cual.
        """
        if get_context().get('webp_as_jpg'):
            mimetype = FILETYPE_BASE64_MAGICWORD.get(base64_source[:1], 'png')
            if 'webp' in mimetype:
                bin_source = base64.b64decode(base64_source)
                checksum = hashlib.sha1(bin_source).hexdigest()
                origins = list(IrAttachment.objects
                               .filter(checksum=checksum)
                               .values_list('pk', flat=True))
                if origins:
                    converted = (IrAttachment.objects
                                 .filter(res_model='ir.attachment',
                                         res_id__in=origins,
                                         mimetype='image/jpeg')
                                 .first())
                    if converted is not None and converted.datas:
                        with converted.datas.open('rb') as handle:
                            base64_source = base64.b64encode(handle.read())
        return image_data_uri(base64_source)

    def _prepare_environment(self, values):
        """≙ ``_prepare_environment`` (``odoo19c: :1293-1327``).

        Publica en ``values`` los nombres con que toda plantilla cuenta:
        ``true``/``false`` siempre; y, salvo con ``minimal_qcontext`` en el
        contexto, el usuario, la empresa, la petición, las utilidades de
        fecha del ``safe_eval``, ``json``, ``floor``/``ceil``, ``env``,
        ``lang`` y ``keep_query``. Es el otro enganche que Enterprise 19
        consulta (:ref:`h-api-819`), y el que ``http_routing`` extiende para
        sumar ``slug``/``unslug_url``.

        Tres divergencias de forma, declaradas:

        - ``request.session.debug`` es ``request.session.get('debug', '')``:
          la sesión de Django es un mapa, no un objeto con atributos.
        - ``res_company`` no lleva ``.sudo()``: la elevación aquí es un alcance
          (``orm.environments.sudo``), no un atributo del registro.
        - La fuente devuelve ``self.with_context(dev_mode=…)``; el contexto en
          este árbol es un alcance de hilo (``context_scope``), no un atributo
          del receptor, así que ``dev_mode`` lo sirve
          :func:`tools.config.dev_mode` a quien lo consulte y el método
          devuelve ``self`` — que es lo que sus llamadores encadenan.
        """
        request = get_current_request()
        session = getattr(request, 'session', None)
        debug = (session.get('debug', '') if session is not None else '') or ''
        values.update(
            true=True,
            false=False,
        )
        if not get_context().get('minimal_qcontext'):
            environment = env()
            values.setdefault('debug', debug)
            values.setdefault('user_id', environment.user)
            values.setdefault('res_company', environment.company)
            values.update(
                request=request,  # puede ser None fuera de una petición
                test_mode_enabled=config.test_enable(),
                json=qwebJSON,
                quote_plus=quote_plus,
                time=safe_time,
                datetime=safe_datetime,
                relativedelta=relativedelta,
                image_data_uri=self._get_converted_image_data_uri,
                # ``math`` acotado para redondear en plantillas sin pasar por
                # el controlador — mismas dos funciones que la fuente.
                floor=math.floor,
                ceil=math.ceil,
                env=environment,
                lang=environment.lang,
                keep_query=keep_query,
            )
        return self

    def render(self, *args, **kwargs):
        """Punto de entrada del motor — **no** implementado aquí.

        Levanta a propósito, igual que ``ResConfig.execute``: dejarlo devolver
        cadena vacía haría que una plantilla rota se viera como una plantilla
        vacía. Ver el docstring del módulo sobre por qué el compilador no se
        porta.
        """
        raise NotImplementedError(
            'El compilador de QWeb no está portado: este árbol renderiza en '
            'el cliente (React) y no compila plantillas almacenadas. Ver el '
            'docstring del módulo.'
        )


# Anotado bajo su ``_name`` para que un consumidor lo resuelva por nombre sin
# importar la clase — ≙ el ``env['ir.qweb']`` de la fuente. Ver el docstring.
registry.register_abstract(IrTemplateExpressions)
