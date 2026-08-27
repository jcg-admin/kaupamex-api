"""``ir.qweb`` — el motor de plantillas de la referencia.

Adaptación de ``odoo/addons/base/models/ir_qweb.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 3058 líneas). QWeb es un lenguaje de
plantillas **en XML**: los atributos ``t-*`` de un elemento son directivas
(``t-if``, ``t-foreach``, ``t-out``, ``t-call``…) y el motor las **compila a
código Python**, que luego se ejecuta con una lista blanca de opcodes.

Este archivo porta el **vocabulario y las primitivas**; no el compilador. La
razón está medida abajo, y no es "falta tiempo".

Cubre de paso los **2 enganches** que Enterprise 19 usa aquí
—``_prepare_environment`` y ``_get_template_cache_keys``—, los dos del
compilador. Tarea #78, :ref:`h-api-819`.

Por qué el compilador no se porta
=================================

Dos motivos independientes, y cada uno bastaría.

**1. No hay plantillas que compilar.** Medido en este árbol:
``find src -name '*.xml'`` → **0** archivos; plantillas con directivas
``t-*`` → **0**. [PROVEN] El HTML de este producto lo genera **React** en el
cliente (``ui``, Webpack); el backend sirve JSON por DRF. Django trae su
propio motor de plantillas configurado (``DjangoTemplates`` con
``APP_DIRS=True``, ``config/settings/base.py:133-135``) y ni siquiera ése se
usa para vistas: ``grep -rn "from django.shortcuts import" src/`` con
``render`` → **0**. [PROVEN] Un tercer motor de plantillas, sin plantillas,
sería una pieza muerta.

**2. Es el caso máximo de lo que este árbol ya rechazó tres veces.** El
compilador toma **texto almacenado en la base** y produce **bytecode que se
ejecuta**. Es la misma operación que se rechazó en ``ir_rule.domain_force``
(``api@020e965``), en ``ir_actions.server.code`` (``api@bdef44a``) y en
``ir_actions_report.attachment`` (``api@bacee17``) — sólo que aquí en lugar
de una expresión es un lenguaje entero, con su lista blanca de opcodes
(``_SAFE_QWEB_OPCODES``) precisamente porque la superficie es enorme.

Conectarlo exigiría decidir, explícitamente y con su propio análisis, quién
puede escribir plantillas y con qué garantías. Eso no se decide de rebote al
portar un archivo.

Qué SÍ se porta, y por qué vale por sí solo
==========================================

- **``MALICIOUS_SCHEMES``** — el detector de ``javascript:`` en una URL, con
  su excepción exacta: se permite si va seguido **sólo** de
  ``[window.]history.back()``. Es una **primitiva de seguridad**, es verbatim,
  y es útil con o sin QWeb: cualquier sitio que acepte una URL de un usuario
  la necesita. Portarla es lo contrario de código muerto.
- **``VOID_ELEMENTS``** — los 16 elementos HTML sin cierre. Hecho del formato,
  no del motor.
- **``ALLOWED_KEYWORD``**, ``SPECIAL_DIRECTIVES``, ``T_CALL_SLOT`` y las cinco
  expresiones regulares de recorte: el **vocabulario** de QWeb. Se conserva
  para que el día que alguien lea una plantilla de la referencia tenga aquí el
  glosario, y para que ``directives_eval_order`` signifique algo.
- **``directives_eval_order``** — el orden de evaluación de las 18 directivas.
  Es la pieza con más conocimiento acumulado del archivo y la que peor se
  reconstruye desde cero: dice, por ejemplo, que en
  ``<el t-foreach="foo" t-as="bar" t-if="bar">`` el ``foreach`` corre **antes**
  que el ``if``, y que ``elif``/``else`` van primeros porque los compila el
  ``if`` anterior. Invertir dos entradas de esa lista da un motor que compila
  y produce resultados equivocados en silencio.
- **``keep_query``** — compone una cadena de consulta preservando parámetros
  actuales, con comodines. Se porta **con la firma cambiada**: la referencia
  lee el ``request`` global de Werkzeug; aquí los parámetros entran por
  argumento. La lógica —qué se conserva, qué gana el adicional, cómo se
  fusionan los multivalor— es la misma y es lo que aporta.
- **``QWebError`` / ``QWebErrorInfo``** — el error con su contexto de
  plantilla y línea.

Qué NO se porta, con su medición
================================

- **El compilador entero**: ``_compile_node``, ``_compile_directive*`` (una
  por directiva), ``_compile_expr``, ``_compile_format``, el caché de
  plantillas compiladas y ``_SAFE_QWEB_OPCODES``. Ver arriba.
- **``QwebContent`` / ``QwebJSON`` / ``QwebStackFrame`` /
  ``QwebCallParameters``**: estructuras internas del compilador; sin él no
  tienen consumidor.
- **``render(template_name, values, load, **options)``** (línea 2975): el
  punto de entrada del motor.
- **``_id_or_xmlid``**: convierte una referencia a ``int`` o la deja como
  ``xml_id``. Depende de ``ir.model.data``, tabla que existe desde
  ``api@b618a6b`` pero que nadie puebla; y su única razón de ser es alimentar
  al compilador.
"""
import fnmatch
import logging
import re
from urllib.parse import urlencode

import models

_logger = logging.getLogger(__name__)

#: Elementos HTML sin etiqueta de cierre — verbatim de la fuente.
VOID_ELEMENTS = frozenset([
    'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'keygen',
    'link', 'menuitem', 'meta', 'param', 'source', 'track', 'wbr',
])

#: Palabras clave admitidas al compilar una expresión, además de los objetos
#: disponibles. Verbatim de la fuente **menos** ``_BUILTINS``, que allá es la
#: lista de builtins de su ``safe_eval`` — un módulo distinto que este árbol
#: no porta. Se conserva la mitad que es vocabulario del lenguaje.
ALLOWED_KEYWORD = frozenset([
    'False', 'None', 'True', 'and', 'as', 'elif', 'else', 'for', 'if', 'in',
    'is', 'not', 'or',
])

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


class QWebErrorInfo:
    """Contexto de un error de plantilla — ``QWebErrorInfo`` de la fuente.

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


class QWebError(Exception):
    """Error de plantilla con su contexto (``QWebError`` de la fuente)."""

    def __init__(self, info):
        self.info = info if isinstance(info, QWebErrorInfo) \
            else QWebErrorInfo(str(info))
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


class IrQweb(models.Model):
    """``ir.qweb`` — el motor de plantillas.

    Abstracto en la referencia (``AbstractModel``) y abstracto aquí. Sin el
    compilador queda como **portador del vocabulario**: el orden de
    evaluación de directivas y el conjunto de las que existen. Ver el
    docstring del módulo.
    """

    class Meta:
        abstract = True

    @staticmethod
    def directives_eval_order():
        """``_directives_eval_order`` — orden de evaluación, verbatim.

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

    @classmethod
    def directive_attribute_names(cls):
        """Los atributos ``t-*`` que corresponden al orden de evaluación.

        Utilidad de lectura: convierte la lista de directivas en los nombres
        tal como aparecen en una plantilla, que es como los ve quien la lee.
        """
        return [f't-{name}' for name in cls.directives_eval_order()]

    @staticmethod
    def has_malicious_scheme(value):
        """¿La URL trae un ``javascript:`` que no sea el ``history.back()``?

        Envuelve ``MALICIOUS_SCHEMES`` para que el punto de uso lea como una
        pregunta y no como un ``findall`` suelto.
        """
        return bool(MALICIOUS_SCHEMES(value or ''))

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
