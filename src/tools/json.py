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

Qué NO se porta, con su medición
=================================

``json_default`` (``json.py:63-77``) — el ``default=`` que la fuente pasa a
``json.dumps`` para los tipos que JSON no conoce. Sus siete ramas necesitan
cuatro símbolos que este árbol **no tiene**, medido con
``grep -rn "def to_string\\|class lazy\\|ReadonlyDict" --include=*.py src/`` →
**0** en las tres:

===================  ================================================
Rama                 Qué le falta aquí
===================  ================================================
``datetime``/``date``  ``fields.Datetime.to_string`` / ``fields.Date.to_string``
``lazy``               la clase ``lazy`` de ``tools/func.py``
``ReadonlyDict``       la clase de ``tools/misc.py``
``Domain``             ``orm.domains.Domain`` **sí** existe
``bytes`` / resto      stdlib
===================  ================================================

Portarlo con cuatro de siete ramas sería el porte parcial silencioso que
``porte-completo-no-parcial.md`` prohíbe, y con las cuatro piezas ausentes
construidas al vuelo sería inventar tres símbolos del ORM desde este archivo.
Sucesor registrado: tarea **#142**, que porta ``lazy``, ``ReadonlyDict`` y los
dos ``to_string`` en su sitio y cierra ``json_default`` con sus siete ramas.
"""
import json as json_
import re
from collections.abc import Mapping

import markupsafe

__all__ = ['scriptsafe', 'stringify_keys']

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
