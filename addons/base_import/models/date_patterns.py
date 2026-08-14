"""Inferencia del formato de fecha y hora de un archivo importado.

Adaptación de ``odoo19c: base_import/models/base_import.py:1728-1795``
(LGPL-3, ``odoo-tools@622ddc2a``) — atribución preservada (DEC-KX-03).

El problema que resuelve
=========================

Un CSV no declara en qué formato vienen sus fechas. ``12/07/2026`` es el 12
de julio para media humanidad y el 7 de diciembre para la otra, y adivinar
por fila produce una importación en la que unas filas quedan bien y otras
mal. La referencia lo resuelve al revés: en vez de parsear cada valor,
**busca un patrón que explique la columna entera**. Si ninguno explica todos
los valores, no hay formato inferido y el usuario lo declara a mano.

Por qué el catálogo se genera y no se escribe
==============================================

Los patrones son el producto cartesiano de cuatro órdenes de campo
(``%m %d %Y``, ``%d %m %Y``, ``%Y %m %d``, ``%Y %d %m``), su variante de año
corto (``%y``), y cinco separadores. Escribir los 40 a mano es una lista que
se desincroniza en cuanto alguien añade un orden; generarlos mantiene la
correspondencia con la referencia por construcción.

Por qué un regex propio y no ``strptime``
==========================================

``check_patterns`` necesita responder *"¿este patrón explica TODOS los
valores?"* sobre una columna, y ``strptime`` sólo responde por valor y con
una excepción. La referencia compila el patrón a una expresión regular
—``to_re``, que su docstring llama *"cut down version of TimeRE"*— y la
aplica a la columna. Se porta esa forma verbatim: es una decisión de diseño
de la referencia, no un detalle de implementación.
"""
import datetime
import re

#: Separadores admitidos entre los componentes de una fecha. La cadena vacía
#: cubre el formato compacto ``%Y%m%d``.
_SEPARATORS = [' ', '/', '-', '.', '']

#: Los cuatro órdenes de campo base, antes de generar la variante de año
#: corto. ≙ ``_PATTERN_BASELINE`` de la referencia.
_PATTERN_BASELINE = [
    ('%m', '%d', '%Y'),
    ('%d', '%m', '%Y'),
    ('%Y', '%m', '%d'),
    ('%Y', '%d', '%m'),
]

DATE_FORMATS = []
# Se toma el formato base y se duplica sustituyendo el año largo por el
# corto. Cada sustitución se construye sobre las anteriores, por eso el
# `list` intermedio: con un generador, el `set` cambiaría de tamaño durante
# su propia iteración. Es la misma nota que deja la referencia.
for _ps in _PATTERN_BASELINE:
    _patterns = {_ps}
    for _s, _t in [('%Y', '%y')]:
        _patterns.update([
            tuple(_t if _it == _s else _it for _it in _f)
            for _f in _patterns
        ])
    DATE_FORMATS.extend(_patterns)

DATE_PATTERNS = [
    sep.join(fmt)
    for sep in _SEPARATORS
    for fmt in DATE_FORMATS
]

TIME_PATTERNS = [
    '%H:%M:%S', '%H:%M', '%H',            # 24 h
    '%I:%M:%S %p', '%I:%M %p', '%I %p',   # 12 h
]

#: Traducción de cada directiva de ``strptime`` a su grupo de expresión
#: regular. Los rangos están acotados a lo que existe —``3[0-1]`` para el
#: día, ``6[0-1]`` para el segundo bisiesto— para que un valor imposible
#: descarte el patrón en vez de aceptarlo y fallar después al convertir.
_P_TO_RE = {
    'd': r"(3[0-1]|[1-2]\d|0[1-9]|[1-9]| [1-9])",
    'H': r"(2[0-3]|[0-1]\d|\d)",
    'I': r"(1[0-2]|0[1-9]|[1-9])",
    'm': r"(1[0-2]|0[1-9]|[1-9])",
    'M': r"([0-5]\d|\d)",
    'S': r"(6[0-1]|[0-5]\d|\d)",
    'y': r"(\d\d)",
    'Y': r"(\d\d\d\d)",

    'p': r"(am|pm)",

    '%': '%',
}


def _replacer(m):
    """Sustituye una directiva ``%X`` por su grupo de regex."""
    return _P_TO_RE[m.group(1)]


def to_re(pattern):
    """Compila un patrón de ``strptime`` a expresión regular.

    Versión recortada de ``TimeRE`` — el orden de las tres sustituciones
    importa y no es intercambiable:

    1. escapar los metacaracteres del patrón, para que un separador ``.``
       signifique un punto y no "cualquier carácter";
    2. convertir cada espacio en ``\\s+``, para tolerar el espaciado
       irregular de un archivo escrito a mano;
    3. recién entonces expandir las directivas, que introducen sus propios
       metacaracteres y no deben volver a escaparse.

    Se ancla con ``^``/``$``: un patrón que sólo explica el principio del
    valor no lo explica.
    """
    pattern = re.sub(r"([\\.^$*+?\(\){}\[\]|])", r"\\\1", pattern)
    pattern = re.sub(r'\s+', r'\\s+', pattern)
    pattern = re.sub('%([a-z])', _replacer, pattern, flags=re.IGNORECASE)
    pattern = '^' + pattern + '$'
    return re.compile(pattern, re.IGNORECASE)


def check_patterns(patterns, values):
    """Primer patrón que explica **todos** los valores, o ``None``.

    Los ``datetime.date`` se saltan en vez de descartar el patrón: cuando el
    lector de la hoja de cálculo ya devolvió un objeto de fecha, no hay
    cadena que casar y su presencia no dice nada sobre el formato de las
    demás celdas. Los valores vacíos también se saltan — una celda en blanco
    no contradice ningún formato.

    El ``for``/``else`` es deliberado y es donde vive la semántica: se
    devuelve el patrón sólo si el bucle interno terminó **sin** ``break``, es
    decir si ningún valor lo contradijo.
    """
    for pattern in patterns:
        p = to_re(pattern)
        for val in values:
            if isinstance(val, datetime.date):
                continue
            if val and not p.match(val):
                break

        else:  # sin break: todos casan
            return pattern

    return None
