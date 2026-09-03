"""Clave de version ordenable — adaptacion de ``odoo19c:
odoo/tools/parse_version.py`` (``odoo-tools@622ddc2a``, LGPL-3 segun el
``__manifest__.py`` de su addon raiz: copia + adaptacion con atribucion
preservada, DEC-KX-03).

La fuente a su vez lo toma del paquete ``setuptools`` (version 0.6c8),
http://peak.telecommunity.com/DevCenter/PkgResources#parsing-utilities, y le
añade su propio dialecto: ``saas`` se descarta y ``dev`` pesa menos que
cualquier letra.

Que resuelve: convertir una cadena de version en una tupla que ordena
**cronologicamente** con el ``<`` de Python, sin depender de como comparan un
numero y una letra.

**Se portan 4 de 4 simbolos** (``component_re``, ``replace``,
``_parse_version_parts``, ``parse_version``). El archivo aterriza en
``src/tools/`` porque ``src/tools`` ↔ ``odoo/tools`` es una raiz espejada.

Por que entra ahora
===================

Es el segundo modulo de la tarea #338 por consumidores medidos en la
referencia: **18** archivos lo importan —entre ellos ``ir_module.py``,
``ir_actions_report.py``, ``ir_mail_server.py`` y ``modules/migration.py``—,
y los cuatro tienen contraparte viva en este arbol. Aqui lo cita
``addons/certificate/models/certificate.py:22`` en prosa, describiendo como
la referencia decide si ``cryptography`` llega a la version que necesita.

El stack lo TRAE — no hay nada que construir
=============================================

Es CPython puro: ``re`` y nada mas. **No** se sustituye por
``packaging.version``, que no esta instalado (medido: 0 hits en ``src/`` y
``addons/``) y que ademas no comparte el dialecto: ``packaging`` implementa
PEP 440 y rechazaria ``saas~15.4``, que es una version real de la referencia.

Divergencia de mecanismo declarada — una
=========================================

El bloque ``if __name__ == '__main__'`` de la fuente (sus dos cadenas de
auto-verificacion) **no se porta como bloque**: su contenido es el nucleo de
``tests/unit/tools/test_parse_version.py``. Un control que solo corre cuando
alguien ejecuta el archivo a mano no esta en ninguna suite, y por tanto no
puede fallar cuando debe.
"""
import re

#: Parte la cadena en sus componentes: numero, palabra, punto o guion.
component_re = re.compile(r'(\d+ | [a-z]+ | \.| -)', re.VERBOSE)

#: El dialecto: los tres alias de «candidate», los dos separadores que valen
#: por «final-», el ``dev`` que precede a toda letra, y el ``saas``/``~`` de
#: la propia referencia, que no pesan.
replace = {
    'pre': 'c',
    'preview': 'c',
    '-': 'final-',
    '_': 'final-',
    'rc': 'c',
    'dev': '@',
    'saas': '',
    '~': '',
}.get


def _parse_version_parts(s):
    """Emite las partes ya traducidas al dialecto, con su centinela final."""
    for part in component_re.split(s):
        part = replace(part, part)
        if not part or part == '.':
            continue
        if part[:1] in '0123456789':
            yield part.zfill(8)    # relleno para que comparen como numeros
        else:
            yield '*' + part

    yield '*final'  # deja alpha/beta/candidate por debajo de final


def parse_version(s: str) -> tuple[str, ...]:
    """Convierte una cadena de version en una clave ordenable en el tiempo.

    Es un cruce basto entre ``StrictVersion`` y ``LooseVersion`` de distutils:
    con versiones que ``StrictVersion`` aceptaria se comporta igual; con el
    resto actua como un ``LooseVersion`` algo mas listo. Se *pueden* construir
    esquemas de version patologicos que engañen a este parser, pero deberian
    ser muy raros en la practica.

    El valor devuelto es una tupla de cadenas. Las porciones numericas se
    rellenan a 8 digitos para que comparen como numeros, sin depender de como
    comparan numeros y letras entre si. Los puntos se descartan; los guiones
    se conservan. Los ceros finales entre segmentos alfabeticos o guiones se
    suprimen, de modo que «2.4.0» se considera lo mismo que «2.4». Las partes
    alfanumericas se pasan a minusculas.

    El algoritmo asume que cadenas como «-», y toda cadena alfabetica que siga
    a «final» en orden alfabetico, representan un «nivel de parche». Asi,
    «2.4-1» se toma por una rama o parche de «2.4», y por tanto «2.4.1» es mas
    nuevo que «2.4-1», que a su vez es mas nuevo que «2.4».

    Cadenas como «a», «b», «c», «alpha», «beta», «candidate» y demas —las que
    preceden a «final» alfabeticamente— se toman por versiones de
    pre-lanzamiento, de modo que «2.4» se considera mas nuevo que «2.4a1».

    Por ultimo, para casos sueltos, las cadenas «pre», «preview» y «rc» se
    tratan como si fueran «c», es decir, como candidatas a lanzamiento, y por
    tanto no son tan nuevas como una version que no las lleve.
    """
    parts: list[str] = []
    for part in _parse_version_parts((s or '0.1').lower()):
        if part.startswith('*'):
            if part < '*final':   # quita el '-' que precede a una pre-release
                while parts and parts[-1] == '*final-':
                    parts.pop()
            # quita los ceros finales de cada serie de partes numericas
            while parts and parts[-1] == '00000000':
                parts.pop()
        parts.append(part)
    return tuple(parts)
