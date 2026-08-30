"""``fields`` — la **fachada pública** del ORM, fiel a ``odoo/fields/__init__.py``.

Paquete, no módulo suelto, igual que ``odoo19c: odoo/fields/``. Su comentario de
cabecera declara para qué existe, y lo repite palabra por palabra en las otras
dos fachadas del árbol (``odoo/api/``, ``odoo/models/``)::

    # Exports features of the ORM to developers.
    # This is a `__init__.py` file to avoid merge conflicts on `odoo/fields.py`.

**Por qué la implementación vive en ``orm/`` y esto sólo re-exporta.** No es
cosmética: es la frontera que desacopla *lo que un addon escribe* de *dónde el
núcleo guarda sus archivos*. Medido en ``odoo19c`` (``odoo-tools@622ddc2a``):
**797** archivos de addon escriben ``from odoo import fields`` y **582**
``from odoo.fields import …``; los que importan ``odoo.orm.fields*`` son
**0**. Dentro del propio núcleo la cruzan **2** archivos, y uno es esta misma
fachada. Esa frontera es la que permitió que 19 moviera las 5 443 líneas de
``odoo/fields.py`` a ``odoo/orm/`` **sin tocar un solo addon**.

**Y no es un re-export mecánico: es una superficie curada.** La fachada de la
referencia ensambla nombres de **doce** módulos distintos, y cuatro de ellos no
son ``fields*`` — ``Command`` sale de ``orm/commands.py``, ``Domain`` de
``orm/domains.py``, ``NO_ACCESS`` de ``orm/models.py`` y ``parse_field_expr`` de
``orm/utils.py``. Un addon escribe ``fields.Domain(...)`` sin enterarse de que
los dominios son otro módulo. Por eso aquí se importa **de cada módulo que
define**, en su orden, y no con un ``import *`` sobre un agregador: el agregador
esconde la procedencia y congela la superficie (ver la nota de ``Serialized``).

Los cinco nombres de la fachada de la referencia que este archivo tuvo que
resolver, con su veredicto medido (``porte-completo-no-parcial.md`` exige uno de
tres, no el silencio). Dos ya se exportan; **tres siguen faltando** —``Field``,
``Id`` y ``NO_ACCESS``— y su ausencia es la que mide el recorrido AST de la
sección «Verificación»:

- ``parse_field_expr`` — **RESUELTO**: el símbolo ya existía en ``orm/utils.py``
  y es idéntico al de la fuente; lo que faltaba era su exportación. Se exporta
  aquí. La referencia también lo consume por la fachada
  (``odoo19c: addons/base/models/ir_default.py:244`` →
  ``fields.parse_field_expr(...)``).
- ``Field`` — la clase base del ORM de la fuente. Es el núcleo de
  :ref:`iniciativa-completar-primitiva-fields`, no una omisión.
- ``Id`` — **divergencia de mecanismo declarada.** Allá ``Id`` es un descriptor
  propio porque un *recordset* envuelve N ids (``odoo19c:
  odoo/orm/fields_misc.py:103-114`` lanza si ``len(ids) > 1``). Aquí una
  instancia **es** un registro, y Django ya provee el descriptor:
  ``pk = property(_get_pk_val, _set_pk_val)``
  (``django/db/models/base.py:686``). Portarlo sería duplicar lo que el stack
  da por construcción.
- ``NO_ACCESS`` — **bloqueado por algo medido.** Es el centinela de
  ``Field.groups`` (``odoo19c: odoo/orm/fields.py:299``), el ACL a nivel de
  campo que consume ``is_field_accessible`` (``orm/models.py:3379``). Sin la
  clase ``Field`` el centinela es una cadena sin consumidor; su bloqueo es el
  porte de ``Field``.
- ``Domain`` — **RESUELTO**: la clase ya vivía en ``orm/domains.py`` con sus
  ocho subclases y sus helpers (``AND``/``OR``/``NOT``/``to_q``); lo que
  faltaba era su exportación por la fachada, que es como la consume un
  addon (``odoo19c: addons/base/models/ir_actions.py:18`` →
  ``from odoo.fields import Command, Domain``). Se exporta aquí.
"""
# ruff: noqa: F401
# Exporta las capacidades del ORM a quien escribe un addon.
# Es un `__init__.py` para no pelear merges sobre `orm/fields.py`.

from orm.fields_misc import Boolean, Json
from orm.fields_numeric import Float, Integer, Monetary
from orm.fields_textual import Char, Html, Text
from orm.fields_selection import Selection
from orm.fields_temporal import Date, Datetime

from orm.fields_relational import Many2many, Many2one, One2many
from orm.fields_reference import Many2oneReference, Reference

from orm.fields_properties import Properties, PropertiesDefinition
from orm.fields_binary import Binary, Image

from orm.commands import Command
from orm.domains import Domain
from orm.utils import parse_field_expr

# ``NonStored`` es campo NUESTRO —la referencia no lo tiene— pero es **un
# campo**, así que entra por la misma puerta que los demás. Sin esta línea sus
# cinco consumidores tenían que escribir ``from orm.fields_nonstored import
# NonStored``, cruzando la frontera que esta fachada existe para sostener.
from orm.fields_nonstored import NonStored
