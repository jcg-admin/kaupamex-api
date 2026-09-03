"""``Query`` — fiel a ``odoo/tools/query.py`` (Odoo 19).

Constructor de SELECT componibles: gestiona tablas con alias, cláusulas JOIN
(con su alias, condición y parámetros), WHERE, GROUP BY, HAVING, ORDER, LIMIT
y OFFSET, y emite el ``SQL`` resultante.

Por qué dejó de ser un alias de ``QuerySet``
============================================

Hasta ``api@38b4e64e`` este archivo era ``Query = models.QuerySet`` — quince
líneas que declaraban la equivalencia y no portaban nada. La equivalencia es
cierta a grandes rasgos (los dos componen una consulta sin ejecutarla) y **es
insuficiente donde importa**: la referencia expone ``make_alias`` y
``add_join``, que es la superficie con la que un campo relacional añade su
LEFT JOIN a una consulta ajena (``odoo19c: odoo/orm/fields_relational.py:466``).
Un ``QuerySet`` de Django no la tiene: sus joins los decide el compilador a
partir de ``filter()``/``select_related()``, y no hay API pública para pedirle
"añade este JOIN con este alias y esta condición".

Sin esa superficie ``BaseModel._traverse_related_sql`` no se puede portar, y
sin él ``_field_to_sql`` —la puerta del motor de consultas— tampoco. Esta es la
pieza de abajo de esa cadena (tarea #127).

Qué NO reemplaza
================

**El ``QuerySet`` de Django sigue siendo el recordset del proyecto.** Este
``Query`` no compite con él: es el constructor de SQL crudo para los casos en
que hay que componer la sentencia a mano, que es exactamente su papel en la
referencia. Un addon que filtra registros sigue escribiendo
``Modelo.objects.filter(...)``.

La divergencia del primer parámetro, declarada
==============================================

La firma es la de la fuente —``Query(env, alias, table=None)``— pero aquí no
hay objeto ``Environment``: ``orm/environments.py`` es un módulo de funciones
sobre las piezas nativas de Django, y así lo declara su propia cabecera. Por
eso ``env`` se interpreta **por lo que traiga**:

- ``None`` → la base por defecto;
- una cadena → el alias de base de Django (``using``);
- cualquier objeto con ``execute_query`` → se usa tal cual.

Es un ensanchamiento, no un recorte: el día que exista un ``Environment``
propio, entra por la tercera rama sin tocar este archivo.

La divergencia de controlador: ``IN %s`` sobre una tupla
========================================================

La fuente emite ``IN %s`` y confía en que su cursor adapte la tupla a un
constructor de fila —``IN (1,2,3)``—, que es lo que hacía psycopg 2. **psycopg
3 no lo hace**: adapta la tupla a un literal de registro entrecomillado, y
PostgreSQL rechaza la sentencia. Medido en este contenedor::

    IN %s                   con (1,2,3)  -> ProgrammingError: syntax error at
                                            or near "'(1,2,3)'"
    = ANY(%s)               con [1,2,3]  -> OK
    IN (SELECT unnest(%s))  con [1,2,3]  -> OK

Por eso los dos sitios que la fuente escribe con ``IN`` sobre una tupla
—``subselect`` con ids memorizados y ``set_result_ids(ordered=False)``— emiten
aquí ``(SELECT unnest(%s))`` y ``= ANY(%s)`` sobre una lista. Es la **misma
operación sobre el mismo conjunto**, en la forma que este controlador adapta;
no es una libertad de diseño sino el precio de cambiar de driver, y sin ella
las dos rutas producían SQL inválido en tiempo de ejecución.
"""
import itertools
from collections.abc import Iterable, Iterator

from .sql import SQL, execute_sql, make_identifier

__all__ = ['Query']


def _sql_from_table(alias: str, table: SQL) -> SQL:
    """Un elemento de la cláusula FROM a partir de ``alias`` y ``table``."""
    if (alias_identifier := SQL.identifier(alias)) == table:
        return table
    return SQL("%s AS %s", table, alias_identifier)


def _sql_from_join(kind: SQL, alias: str, table: SQL, condition: SQL) -> SQL:
    """Un elemento de la cláusula FROM para un JOIN."""
    return SQL("%s %s ON (%s)", kind, _sql_from_table(alias, table), condition)


_SQL_JOINS = {
    "JOIN": SQL("JOIN"),
    "LEFT JOIN": SQL("LEFT JOIN"),
}


def _generate_table_alias(src_table_alias: str, link: str) -> str:
    """Genera el alias estándar de una tabla. Se compone así:

        - la base es el nombre de la tabla origen (que ya puede ser un alias);
        - se le añade la tabla unida usando el nombre del campo de enlace, que
          es lo que hace único el alias de un camino dado;
        - el nombre se recorta si se pasa del límite de identificador de
          PostgreSQL.

    .. code-block:: pycon

        >>> _generate_table_alias('res_users', link='parent_id')
        'res_users__parent_id'

    :param str src_table_alias: alias de la tabla origen
    :param str link: nombre del campo
    :return str: alias
    """
    return make_identifier(f"{src_table_alias}__{link}")


class Query:
    """Implementación simple de un objeto de consulta, que gestiona tablas con
    alias, cláusulas de JOIN (con alias, condición y parámetros), cláusulas
    WHERE (con parámetros), orden, límite y desplazamiento.

    :param env: entorno del modelo (para evaluación perezosa) — ver la
        divergencia declarada en la cabecera del módulo
    :param alias: nombre o alias de la tabla
    :param table: expresión de tabla (``str`` o ``SQL``), opcional
    """

    def __init__(self, env, alias: str, table: (SQL | None) = None):
        # cursor de base de datos
        self._env = env

        self._tables: dict[str, SQL] = {
            alias: table if table is not None else SQL.identifier(alias),
        }

        # joins {alias: (kind(SQL), table(SQL), condition(SQL))}
        self._joins: dict[str, tuple[SQL, SQL, SQL]] = {}

        # lista de condiciones WHERE (se unen con 'AND')
        self._where_clauses: list[SQL] = []

        # groupby, having, order, limit, offset
        self.groupby: SQL | None = None
        self._order_groupby: list[SQL] = []
        self.having: SQL | None = None
        self._order: SQL | None = None
        self.limit: int | None = None
        self.offset: int | None = None

        # resultado memorizado
        self._ids: tuple[int, ...] | None = None

    def _execute_query(self, sql: SQL) -> list[tuple]:
        """Corre ``sql`` por la vía que ``env`` haya traído.

        NO existe en la referencia: allá ``self._env.execute_query(...)`` es
        una sola cosa porque el ``Environment`` siempre es un objeto. Aquí es
        el punto donde se resuelve la divergencia del primer parámetro que la
        cabecera del módulo declara, y se resuelve **una vez** en lugar de en
        cada llamada.
        """
        if hasattr(self._env, 'execute_query'):
            return self._env.execute_query(sql)
        return execute_sql(sql, using=self._env)

    @staticmethod
    def make_alias(alias: str, link: str) -> str:
        """Devuelve un alias construido sobre ``alias`` y ``link``."""
        return _generate_table_alias(alias, link)

    def add_table(self, alias: str, table: (SQL | None) = None):
        """Añade a la cláusula FROM una tabla con el alias dado."""
        assert alias not in self._tables and alias not in self._joins, \
            f"Alias {alias!r} already in {self}"
        self._tables[alias] = table if table is not None else SQL.identifier(alias)
        self._ids = self._ids and None

    def add_join(self, kind: str, alias: str, table: str | SQL | None, condition: SQL):
        """Añade una cláusula de JOIN con el alias, la tabla y la condición dados."""
        sql_kind = _SQL_JOINS.get(kind.upper())
        assert sql_kind is not None, f"Invalid JOIN type {kind!r}"
        assert alias not in self._tables, f"Alias {alias!r} already used"
        table = table or alias
        if isinstance(table, str):
            table = SQL.identifier(table)

        if alias in self._joins:
            assert self._joins[alias] == (sql_kind, table, condition)
        else:
            self._joins[alias] = (sql_kind, table, condition)
            self._ids = self._ids and None

    def add_where(self, where_clause: str | SQL, where_params=()):
        """Añade una condición a la cláusula WHERE."""
        self._where_clauses.append(SQL(where_clause, *where_params))
        self._ids = self._ids and None

    def join(self, lhs_alias: str, lhs_column: str, rhs_table: str | SQL,
             rhs_column: str, link: str) -> str:
        """Une una tabla ya presente en este ``Query`` con otra tabla.

        Es en esencia un atajo de :meth:`~.make_alias` y :meth:`~.add_join`.

        :param str lhs_alias: alias de una tabla ya definida en este ``Query``.
        :param str lhs_column: columna de ``lhs_alias`` para la condición ON.
        :param str rhs_table: nombre de la tabla a unir con ``lhs_alias``.
        :param str rhs_column: columna de ``rhs_alias`` para la condición ON.
        :param str link: sirve para generar el alias de la tabla unida; debe
            representar la relación (el enlace) entre ambas tablas.
        """
        assert lhs_alias in self._tables or lhs_alias in self._joins, \
            "Alias %r not in %s" % (lhs_alias, str(self))
        rhs_alias = self.make_alias(lhs_alias, link)
        condition = SQL("%s = %s", SQL.identifier(lhs_alias, lhs_column),
                        SQL.identifier(rhs_alias, rhs_column))
        self.add_join('JOIN', rhs_alias, rhs_table, condition)
        return rhs_alias

    def left_join(self, lhs_alias: str, lhs_column: str, rhs_table: str,
                  rhs_column: str, link: str) -> str:
        """Añade un LEFT JOIN a la tabla actual (si hace falta) y devuelve el
        alias que corresponde a ``rhs_table``.

        Ver la documentación de :meth:`join` para el detalle de los argumentos.
        """
        assert lhs_alias in self._tables or lhs_alias in self._joins, \
            "Alias %r not in %s" % (lhs_alias, str(self))
        rhs_alias = self.make_alias(lhs_alias, link)
        condition = SQL("%s = %s", SQL.identifier(lhs_alias, lhs_column),
                        SQL.identifier(rhs_alias, rhs_column))
        self.add_join('LEFT JOIN', rhs_alias, rhs_table, condition)
        return rhs_alias

    @property
    def order(self) -> SQL | None:
        return self._order

    @order.setter
    def order(self, value: SQL | str | None):
        self._order = SQL(value) if value is not None else None

    @property
    def table(self) -> str:
        """La tabla principal, es decir la primera de la cláusula FROM."""
        return next(iter(self._tables))

    @property
    def from_clause(self) -> SQL:
        """La cláusula FROM de ``self``, sin la palabra FROM."""
        tables = SQL(", ").join(itertools.starmap(_sql_from_table, self._tables.items()))
        if not self._joins:
            return tables
        items = (
            tables,
            *(
                _sql_from_join(kind, alias, table, condition)
                for alias, (kind, table, condition) in self._joins.items()
            ),
        )
        return SQL(" ").join(items)

    @property
    def where_clause(self) -> SQL:
        """La condición WHERE de ``self``, sin la palabra WHERE."""
        return SQL(" AND ").join(self._where_clauses)

    def is_empty(self) -> bool:
        """Si se sabe que la consulta no devuelve nada."""
        return self._ids == ()

    def select(self, *args: str | SQL) -> SQL:
        """La consulta SELECT como objeto ``SQL``."""
        sql_args = map(SQL, args) if args else [SQL.identifier(self.table, 'id')]
        return SQL(
            "%s%s%s%s%s%s%s%s",
            SQL("SELECT %s", SQL(", ").join(sql_args)),
            SQL(" FROM %s", self.from_clause),
            SQL(" WHERE %s", self.where_clause) if self._where_clauses else SQL(),
            SQL(" GROUP BY %s", self.groupby) if self.groupby else SQL(),
            SQL(" HAVING %s", self.having) if self.having else SQL(),
            SQL(" ORDER BY %s", self._order) if self._order else SQL(),
            SQL(" LIMIT %s", self.limit) if self.limit else SQL(),
            SQL(" OFFSET %s", self.offset) if self.offset else SQL(),
        )

    def subselect(self, *args: str | SQL) -> SQL:
        """Como :meth:`.select`, pero para subconsultas. Evita el ORDER BY
        cuando puede, y envuelve la subconsulta en paréntesis.
        """
        if self._ids is not None and not args:
            # inyecta el resultado conocido en lugar de la subconsulta
            if not self._ids:
                # sin nada, hace falta una subconsulta sin registros: la tupla
                # vacía es un error de sintaxis, y una que sólo tenga None da
                # problemas con `NOT IN`
                return SQL("(SELECT 1 WHERE FALSE)")
            # DIVERGENCIA DE CONTROLADOR (ver la cabecera): la fuente devuelve
            # `SQL("%s", self._ids)` y deja que el cursor adapte la tupla a un
            # constructor de fila. psycopg 3 la adapta a un literal de registro
            # entrecomillado, así que `IN (...)` sale con un `'(1,2,3)'` que
            # PostgreSQL rechaza. `unnest` de una lista ocupa la misma posición
            # —una subconsulta— y devuelve el mismo conjunto.
            return SQL("(SELECT unnest(%s))", list(self._ids))

        if self.limit or self.offset:
            # en este caso la cláusula ORDER BY es necesaria
            return SQL("(%s)", self.select(*args))

        sql_args = map(SQL, args) if args else [SQL.identifier(self.table, 'id')]
        return SQL(
            "(%s%s%s)",
            SQL("SELECT %s", SQL(", ").join(sql_args)),
            SQL(" FROM %s", self.from_clause),
            SQL(" WHERE %s", self.where_clause) if self._where_clauses else SQL(),
        )

    def get_result_ids(self) -> tuple[int, ...]:
        """El resultado de ``self.select()`` como tupla de ids. Se memoriza,
        lo que evita hacer dos veces la misma consulta.
        """
        if self._ids is None:
            self._ids = tuple(id_ for id_, in self._execute_query(self.select()))
        return self._ids

    def set_result_ids(self, ids: Iterable[int], ordered: bool = True) -> None:
        """Prepara la consulta para devolver las filas de ``ids``. El parámetro
        ``ordered`` dice si la consulta debe ordenarse para corresponder
        exactamente a la secuencia ``ids``.
        """
        assert not (self._joins or self._where_clauses or self.limit or self.offset), \
            "Method set_result_ids() can only be called on a virgin Query"
        ids = tuple(ids)
        if not ids:
            self.add_where("FALSE")
        elif ordered:
            # Esto garantiza que self.select() devuelva los resultados en el
            # orden esperado de ids:
            #   SELECT "stuff".id
            #   FROM "stuff"
            #   JOIN (SELECT * FROM unnest(%s) WITH ORDINALITY) AS "stuff__ids"
            #       ON ("stuff"."id" = "stuff__ids"."unnest")
            #   ORDER BY "stuff__ids"."ordinality"
            alias = self.join(
                self.table, 'id',
                SQL('(SELECT * FROM unnest(%s) WITH ORDINALITY)', list(ids)), 'unnest',
                'ids',
            )
            self.order = SQL.identifier(alias, 'ordinality')
        else:
            # Misma divergencia de controlador que en `subselect`: `= ANY`
            # sobre una lista es la forma que psycopg 3 adapta, y es
            # equivalente a `IN` sobre el mismo conjunto.
            self.add_where(SQL("%s = ANY(%s)",
                               SQL.identifier(self.table, 'id'), list(ids)))
        self._ids = ids

    def __str__(self) -> str:
        sql = self.select()
        return f"<Query: {sql.code!r} with params: {sql.params!r}>"

    def __bool__(self):
        return bool(self.get_result_ids())

    def __len__(self) -> int:
        if self._ids is None:
            if self.limit or self.offset:
                # optimización: generar un SELECT FROM y contar las filas
                sql = SQL("SELECT COUNT(*) FROM (%s) t", self.select(""))
            else:
                sql = self.select('COUNT(*)')
            return self._execute_query(sql)[0][0]
        return len(self.get_result_ids())

    def __iter__(self) -> Iterator[int]:
        return iter(self.get_result_ids())
