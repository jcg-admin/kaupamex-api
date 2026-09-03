"""``api`` — fiel a ``odoo/api/__init__.py`` (Odoo 19).

Paquete (no módulo suelto), igual que ``odoo/api/`` es un paquete. Su comentario
de cabecera declara para qué existe, y lo repite palabra por palabra en las
otras dos fachadas del árbol (``odoo/fields/``, ``odoo/models/``)::

    # Exports features of the ORM to developers.
    # This is a `__init__.py` file to avoid merge conflicts on `odoo/api.py`.

Y ``odoo/orm/__init__.py`` declara lo contrario para sí mismo —*"developers
should not import directly from here"*—: no re-exporta nada. Por eso la
re-exportación **es el porte**, no una deuda que se salde aparte. Un símbolo
declarado en ``orm/`` y no ligado aquí no está portado a medias: está portado
en otro sitio que el de la fuente, que es la divergencia de :ref:`h-api-578`.

Se importa **de cada módulo que declara**, en el orden de la fuente, y no con un
``import *`` sobre un agregador: el agregador esconde la procedencia y congela
la superficie en el instante del import (:ref:`h-api-604`).

Los cuatro nombres de la fachada de la referencia que este archivo NO liga, con
su veredicto —``porte-completo-no-parcial.md`` exige uno de tres, no el
silencio—. Los cuatro son **bloqueo medido**: ``orm/`` todavía no los declara, y
ligar un nombre inexistente rompe el import del paquete. Cada uno entra con el
pase que porta su símbolo, que es el mismo pase y no un barrido posterior:

- ``depends_context``, ``deprecated``, ``ondelete`` — decoradores de
  ``odoo19c: odoo/orm/decorators.py`` que ``orm/decorators.py`` aún no declara.
  ``ondelete`` es el de :ref:`tarea-205`.
- ``Self`` — alias de tipo de ``odoo19c: odoo/orm/types.py``. Los otros cuatro
  de ese módulo (``ContextType``, ``DomainType``, ``IdType``, ``ValuesType``) sí
  se ligan aquí.

Divergencia de sitio declarada: la referencia saca ``IdType`` de
``odoo/orm/types.py`` y aquí sale de ``orm/identifiers.py``, junto a ``NewId``
que es su compañero natural. El nombre y el objeto son los de la fuente; lo que
difiere es el archivo que lo aloja.
"""
# ruff: noqa: F401
# Exporta las capacidades del ORM a quien escribe un addon.
# Es un `__init__.py` para no pelear merges sobre `orm/api.py`.

from orm.identifiers import IdType, NewId
from orm.decorators import (
    autovacuum,
    constrains,
    depends,
    depends_context,
    model,
    model_create_multi,
    onchange,
    ondelete,
    private,
    readonly,
    returns,
)
from orm.environments import Environment
from orm.utils import SUPERUSER_ID

from orm.types import ContextType, DomainType, ValuesType

__all__ = [
    'depends', 'constrains', 'onchange', 'model', 'model_create_multi', 'returns',
    'autovacuum', 'private', 'readonly',
    'NewId', 'Environment', 'SUPERUSER_ID',
    'ContextType', 'DomainType', 'IdType', 'ValuesType',
]
