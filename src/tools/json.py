"""Serialización JSON — ≙ ``odoo19c: odoo/tools/json.py``.

Dos piezas con papeles distintos:

- **``scriptsafe``** — el ``json.dumps`` que se puede incrustar dentro de un
  ``<script>`` sin abrir un XSS. Un ``<script>`` no interpreta entidades HTML,
  así que escapar con ``&lt;`` rompe el JSON *y* no protege; la fuente escapa
  a nivel JSON (``<`` → ``\\u003c``), que el parser deshace sin diferencia en
  el resultado. Se porta con su razonamiento, que es el contrato.
- **``stringify_keys``** — normaliza las claves de un mapa a cadena antes de
  serializar. Su consumidor es ``IrActionsServer._compute_webhook_sample_payload``,
  cuya carga puede traer mapas con claves que no son cadena.

Cobertura medida
================

Los **seis** símbolos de nivel de módulo de la fuente (``json.py:1-94``)
están portados, medido por AST: ``JSON_SCRIPTSAFE_MAPPER``, ``_ScriptSafe``,
``JSON``, ``scriptsafe``, ``json_default`` y ``stringify_keys``. Ausentes: 0.

``json_default`` cerró con la tarea **#142**, que aportó las piezas que le
faltaban. Medido al cerrarla, una por rama:

===========================  ==================================================
Rama                         De dónde sale su pieza aquí
===========================  ==================================================
``datetime`` / ``date``      ``Datetime.to_string`` / ``Date.to_string`` — **ya
                             existían** en ``orm/fields_temporal.py:318`` y
                             ``:237``. La medición de la premisa
                             (``grep "def to_string"`` → 0) era **ciega**: los
                             cuerpos se llaman ``_datetime_to_string`` y
                             ``_date_to_string``, y el nombre de la fuente se
                             instala como atributo (``:440``, ``:451``).
``lazy``                     portada en ``tools/func.py`` por esta tarea
``ReadonlyDict``             portada en ``tools/misc.py`` por esta tarea
``Domain``                   ``orm.domains.Domain``, ya existente
``bytes`` / resto            stdlib
===========================  ==================================================

DIVERGENCIA DE MECANISMO, declarada — de dónde vienen los símbolos
==================================================================

La fuente los toma de su fachada ``odoo.fields`` con un import **dentro** de
la función (``json.py:63``), que ahí es obligado: ``odoo/__init__.py`` carga
``tools`` antes que ``orm``, así que al nivel del módulo el ciclo es real.

Aquí los imports van **al top**, que es lo que ``no-lazy-imports.md`` exige, y
se puede porque el ciclo no existe: medido, ningún módulo de ``orm/`` —ni
ninguna de sus dependencias transitivas en ``tools/``— importa ``tools.json``,
cuyo único consumidor es ``addons/base/models/ir_actions.py``. La excepción #3
de esa regla («ciclo real verificado») pide justamente esta comprobación antes
de aceptar un import diferido; el resultado es que no hace falta.

Cada símbolo se importa de **su** módulo y no de una fachada, que es la
convención de este árbol (``tools/__init__.py``). Para ``Domain`` no hay otra
opción: ``orm/fields.py`` deliberadamente **no** lo re-exporta —a diferencia
de la fuente, que sí (``odoo/orm/fields.py:24``)— porque aquí la dirección de
dependencia entre campo y dominio está invertida (``orm/fields.py:1975-1976``).
"""
import json as json_
import re
from collections.abc import Mapping
from datetime import date, datetime

import markupsafe

from orm.domains import Domain
from orm.fields_temporal import Date, Datetime
from tools.func import lazy
from tools.misc import ReadonlyDict

__all__ = ['json_default', 'scriptsafe', 'stringify_keys']

#: ≙ ``JSON_SCRIPTSAFE_MAPPER`` (``json.py:11-17``), verbatim. Los cinco
#: caracteres son los que rompen un ``<script>`` o un ``<!--``; ninguno es
#: metacarácter de JSON, así que la sustitución se puede hacer sobre el JSON
#: ya serializado sin romperlo.
JSON_SCRIPTSAFE_MAPPER = {
    '&': r'\u0026',
    '<': r'\u003c',
    '>': r'\u003e',
    '\u2028': r'\u2028',
    '\u2029': r'\u2029',
}


class _ScriptSafe(str):
    """≙ ``_ScriptSafe`` (``json.py:18-27``) — la cadena que sabe escaparse."""

    def __html__(self):
        return markupsafe.Markup(re.sub(
            r'[<>&\u2028\u2029]',
            lambda m: JSON_SCRIPTSAFE_MAPPER[m[0]],
            self,
        ))


class JSON:
    """≙ ``JSON`` (``json.py:28-59``) — ``loads`` normal, ``dumps`` seguro."""

    def loads(self, *args, **kwargs):
        return json_.loads(*args, **kwargs)

    def dumps(self, *args, **kwargs):
        """Serializa dejando la cadena lista para incrustarse en un ``<script>``.

        Un ``<script>`` es un contexto especial: sólo espera ``</script>`` y no
        interpreta nada más, así que el escapado HTML estándar no sirve —rompe
        las comillas dobles y convierte ``<`` en ``&lt;`` *dentro del JSON*, no
        sólo en la página. Pero **no** escapar deja que una cadena del JSON
        contenga ``</script>``, que es un vector de XSS.

        La salida es un escape JSON (``<`` → ``\\u003c``) de los caracteres
        peligrosos: cierra el XSS, no rompe el JSON, y el resultado tras
        parsearlo es idéntico. ``U+2028`` y ``U+2029`` van en el mismo saco
        porque JavaScript los lee como salto de línea y JSON no.

        .. warning::

           Fuera de un ``<script>`` esto se escapa además con las reglas
           normales del formato que lo contiene.
        """
        return _ScriptSafe(json_.dumps(*args, **kwargs))


#: ≙ ``scriptsafe = JSON()`` (``json.py:60``).
scriptsafe = JSON()


def json_default(obj):
    """El ``default=`` de ``json.dumps`` — ≙ ``json.py:62-76``.

    ``json.dumps`` sólo llama aquí cuando su codificador **no sabe** serializar
    un objeto, así que cada rama es un tipo opaco y su representación. El
    resultado vuelve al codificador, no a la salida: por eso las ramas de
    ``lazy`` y ``ReadonlyDict`` devuelven el dato (el valor envuelto, un
    ``dict``) y no su texto — un mapa se serializa como objeto JSON y no como
    la representación de un diccionario de Python.

    **El orden de las dos primeras ramas es el contrato**, no una casualidad de
    redacción: ``datetime`` es subclase de ``date``, así que invertirlas
    truncaría la hora de todo instante sin que nada fallara.

    La última rama, ``str(obj)``, hace que la función no lance nunca: un tipo
    sin rama propia se degrada a su texto en vez de reventar la serialización.
    """
    if isinstance(obj, datetime):
        return Datetime.to_string(obj)
    if isinstance(obj, date):
        return Date.to_string(obj)
    if isinstance(obj, lazy):
        return obj._value
    if isinstance(obj, ReadonlyDict):
        return dict(obj)
    if isinstance(obj, bytes):
        return obj.decode()
    if isinstance(obj, Domain):
        return list(obj)
    return str(obj)


def stringify_keys(obj):
    """≙ ``stringify_keys`` (``json.py:80-94``), verbatim.

    Convierte a cadena, recursivamente, las claves de todo mapa. Las cargas de
    ejemplo de un webhook pueden traer mapas con claves que no son cadena
    —``frozendict`` entre ellas— y ``json.dumps`` exige claves compatibles con
    JSON, así que hay que normalizarlas antes de serializar.
    """
    if isinstance(obj, Mapping):
        return {str(k): stringify_keys(v) for k, v in obj.items()}

    return obj
