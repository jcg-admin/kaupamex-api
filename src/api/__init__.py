"""``api`` — fiel a ``odoo/api/__init__.py`` (Odoo 19).

Paquete (no módulo suelto), igual que ``odoo/api/`` es un paquete. Su
comentario
de cabecera declara para qué existe, y lo repite palabra por palabra en las
otras dos fachadas del árbol (``odoo/fields/``, ``odoo/models/``)::

    # Exports features of the ORM to developers.
    # This is a `__init__.py` file to avoid merge conflicts on `odoo/api.py`.

Y ``odoo/orm/__init__.py`` declara lo contrario para sí mismo —*"developers
should not import directly from here"*—: no re-exporta nada. Por eso la
re-exportación **es el porte**, no una deuda que se salde aparte. Un símbolo
declarado en ``orm/`` y no ligado aquí no está portado a medias: está portado
en otro sitio que el de la fuente, que es la divergencia de :ref:`h-api-578`.

Se importa **de cada módulo que declara**, en el orden de la fuente, y no con
un
``import *`` sobre un agregador: el agregador esconde la procedencia y congela
la superficie en el instante del import (:ref:`h-api-604`).

Todos los nombres de la fachada de la referencia quedan ligados, y ninguno
más: ``returns`` venía de ``odoo18c: odoo/api.py`` y la 19 lo retiró; aquí era
un decorador vacío sin llamadas y se retiró con ella. Lo único que este archivo
añade es ``__all__``, que la fuente no declara y que aquí fija la superficie de
``import *``.

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
    deprecated,
    model,
    model_create_multi,
    onchange,
    ondelete,
    private,
    readonly,
)
from orm.environments import Environment
from orm.utils import SUPERUSER_ID

from orm.types import ContextType, DomainType, Self, ValuesType

__all__ = [
    'depends',
    'constrains',
    'onchange',
    'model',
    'model_create_multi',
    'autovacuum',
    'private',
    'readonly',
    'depends_context',
    'ondelete',
    'deprecated',
    'NewId',
    'Environment',
    'SUPERUSER_ID',
    'ContextType',
    'DomainType',
    'IdType',
    'Self',
    'ValuesType',
]
