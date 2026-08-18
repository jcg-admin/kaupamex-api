"""Sondas de capacidades de la base — fiel a ``odoo/modules/db.py`` (parcial).

**Cobertura declarada.** La fuente (``odoo19c: odoo/modules/db.py``, 200
líneas) declara **6** símbolos; aquí se portan **3** — los que preguntan por
capacidades del motor:

- ``FunctionStatus`` (``:162-165``), ``has_unaccent`` (``:168-189``) y
  ``has_trigram`` (``:192-200``).

Los otros 3 tienen su desenlace declarado en el docstring de
``modules/__init__.py`` y su sucesor en la tarea **#298**: ``is_initialized``
e ``initialize`` los cubre el mecanismo ``INSTALLED_APPS`` + migraciones, y
``create_categories`` depende de ``ir.module.category`` poblado (#452).

El primer consumidor es la búsqueda del sitio (``Website._search_find_fuzzy_term``):
con ``pg_trgm`` presente enumera palabras por ``word_similarity``; sin él cae
al enumerador básico — el mismo despacho que la fuente hace con
``registry.has_trigram``.
"""
from enum import IntEnum


class FunctionStatus(IntEnum):
    """≙ ``FunctionStatus`` (``odoo19c: odoo/modules/db.py:162-165``)."""

    MISSING = 0    # la función no está (falsy)
    PRESENT = 1    # está, pero no es indexable (no inmutable)
    INDEXABLE = 2  # está y es indexable (inmutable)


def has_unaccent(cr):
    """≙ ``has_unaccent`` (``odoo19c: odoo/modules/db.py:168-189``).

    ¿Existe la función ``unaccent`` y en qué estado? La provee normalmente el
    módulo contrib ``unaccent`` de PostgreSQL, pero cualquier función homónima
    de un argumento sirve — mismo criterio que la fuente.

    El ``provolatile`` distingue si sirve para **crear índices**: sólo una
    función inmutable (``'i'``) es indexable.

    :param cr: cursor de base de datos abierto.
    :returns: un :class:`FunctionStatus`.
    """
    cr.execute("""
        SELECT p.provolatile
        FROM pg_proc p
        WHERE p.proname = 'unaccent'
              AND p.pronamespace = current_schema::regnamespace
              AND p.pronargs = 1
    """)
    result = cr.fetchone()
    if not result:
        return FunctionStatus.MISSING
    return FunctionStatus.INDEXABLE if result[0] == 'i' else FunctionStatus.PRESENT


def has_trigram(cr):
    """≙ ``has_trigram`` (``odoo19c: odoo/modules/db.py:192-200``).

    ¿Existe ``word_similarity``? La provee ``pg_trgm``, pero —igual que la
    fuente— cualquier función con ese nombre cuenta: se pregunta por el
    símbolo, no por la extensión.

    :param cr: cursor de base de datos abierto.
    :returns: ``True`` si la función existe.
    """
    cr.execute("SELECT proname FROM pg_proc WHERE proname='word_similarity'")
    return len(cr.fetchall()) > 0
