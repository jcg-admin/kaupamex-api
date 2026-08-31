"""Fragmentos SQL componibles e introspección (fiel a ``odoo.tools.sql``).

La pieza central es la clase :class:`SQL` (``odoo19c: odoo/tools/sql.py:46``),
portada COMPLETA en la tarea #549 (H-API-698): hasta entonces ``SQL`` era un
alias de ``django.db.models.expressions.RawSQL`` — no componible, sin
``SQL.identifier``, sin ``SQL.join`` ni interpolación por nombre. El alias
quedó retirado; la única traza que se conserva de él es la adaptación
``output_field`` (ver la clase).

Cobertura del resto del módulo fuente — medida por AST el 2026-08-18 sobre
``odoo19c: odoo/tools/sql.py`` (781 líneas): 2 clases, 37 funciones de módulo
y 5 variables de módulo.

  ================================  =====================================
  Símbolo de la referencia          Estado aquí
  ================================  =====================================
  ``SQL`` (clase, ``:46``)          **portada completa** (este pase, #549)
  ``escape_psql`` (``:640``)        portada (previa)
  ``table_exists`` (``:216``)       adaptada (previa; firma con cursor +
                                    ``schema``, vía ``information_schema``
                                    en vez de ``pg_class``)
  ``column_exists`` (``:315``)      adaptada (previa)
  ``table_columns`` (``:299``)      adaptada (previa)
  ``index_exists`` (``:540``)       adaptada (previa; ``pg_indexes``)
  ``IDENT_RE`` (``:35``)            **portada** (la consume
                                    ``SQL.identifier``)
  ================================  =====================================

**Pendientes — 30 funciones de módulo, 1 clase y 3 variables** que la
referencia declara y aquí no existen: ``existing_tables``, ``table_kind`` (+
``TableKind``), ``create_model_table``, ``create_column``, ``rename_column``,
``convert_column``, ``convert_column_translatable``, ``_convert_column``,
``drop_depending_views``, ``get_depending_views``, ``set_not_null``,
``drop_not_null``, ``constraint_definition``, ``add_constraint``,
``drop_constraint``, ``add_foreign_key``, ``get_foreign_keys``,
``fix_foreign_key``, ``check_index_exist``, ``index_definition``,
``create_index``, ``add_index``, ``create_unique_index``, ``drop_index``,
``drop_view_if_exists``, ``reverse_order``,
``increment_fields_skiplock``, ``value_to_translated_trigram_pattern``,
``pattern_to_translated_trigram_pattern``,
``make_index_name``; y ``__all__``, ``_schema``, ``_CONFDELTYPES``.
Todas sirven al DDL del registro de modelos de la
referencia; aquí ese DDL lo emiten las migraciones de Django. Se portan
cuando un consumidor las exija — el alcance de #549 es la clase ``SQL``;
esta declaración medida es el registro de esa cobertura (regla
``porte-completo-no-parcial``). ``make_identifier`` **salió de esa lista**
el 2026-08-28: ``tools/query.py`` lo exige para acotar el alias de un JOIN
al límite de identificador de PostgreSQL, que es el consumidor que la
política anunciaba. ``SQL_ORDER_BY_TYPE`` salió el 2026-08-30 por la misma
regla: ``Field.column_order`` (``orm/fields.py``) es su consumidor. ``pg_varchar`` salió el
2026-08-31 por la misma regla: ``Char._column_type`` lo exige para que un
``CharField`` responda su tipo de columna (tarea #245).

``named_to_positional_printf`` y ``_PrintfArgs`` viven en
``src/tools/misc.py`` — su hogar espejado (``odoo19c: odoo/tools/misc.py:1959``
y ``:1967``) — y este módulo importa la primera igual que la referencia
(``odoo19c: odoo/tools/sql.py:20``). Aterrizaron aquí durante el pase de #549
por el write-set del agente y la consolidación las mudó en el mismo commit.

Sobre los ayudantes de introspección ya existentes: ``odoo/tools/sql.py``
ofrece ``table_exists``/``column_exists``/``index_exists`` sobre
``information_schema``. Tras migrar el motor a PostgreSQL, el "current
schema" vuelve a ser ``current_schema`` (``odoo19c: odoo/tools/sql.py:320``),
que bajo MariaDB había que escribir como ``DATABASE()``.

El cambio no es cosmético — ``schema`` significa otra cosa en cada motor:

  ============  =====================================  ========================
  Motor         ``schema=None`` resuelve a             ``schema='x'`` designa
  ============  =====================================  ========================
  MariaDB       ``DATABASE()`` — la base conectada     una **base**
  PostgreSQL    ``current_schema`` — normalmente       un **namespace** dentro
                ``public``                             de la base (no otra base)
  ============  =====================================  ========================

Un consumidor que pasaba el nombre de la base como ``schema`` funcionaba en
MariaDB y aquí no encontraría nada. Medido a HEAD: **0** consumidores en
``src/`` pasan ``schema`` explícito, así que el cambio de significado no rompe
código vivo — pero queda escrito porque el próximo que lo use tiene que
saberlo. Ver H-API-306.

``index_exists`` cambia de catálogo: PostgreSQL no tiene
``information_schema.STATISTICS`` (es una tabla de MySQL). La referencia usa
``pg_indexes`` (``odoo19c: odoo/tools/sql.py:542``), y aquí se conserva además
el filtro por tabla que nuestra firma ya exponía.
"""
import re
import warnings
from zlib import crc32

from django.db.models.expressions import RawSQL

from .misc import named_to_positional_printf

# ≙ ``IDENT_RE`` (``odoo19c: odoo/tools/sql.py:35``) — el filtro de
# ``SQL.identifier``: minúsculas, dígitos, ``_``, ``$`` y ``-``.
IDENT_RE = re.compile(r'^[a-z0-9_][a-z0-9_$\-]*$', re.I)

#: ≙ ``SQL_ORDER_BY_TYPE`` (``odoo19c: odoo/tools/sql.py:261-272``), verbatim.
#:
#: El orden prescrito de columnas dentro de una tabla, por tipo. Los valores
#: se eligieron para minimizar el relleno de alineación de cada fila: primero
#: lo alineado a 4 bytes, luego lo de 1 byte, luego lo de 8. Un tipo que no
#: esté en el mapa va al final (16), que es lo que hace el ``defaultdict`` de
#: la fuente y aquí el ``.get(clave, 16)`` de :func:`sql_order_by_type`.
#:
#: Es un `dict` llano y no un ``defaultdict`` a propósito: un ``defaultdict``
#: consultado con una clave desconocida la **inserta**, así que una lectura
#: silenciosa lo hace crecer. El default se aplica al leer, no al guardar.
SQL_ORDER_BY_TYPE = {
    'int4': 1,          # 4 bytes alineado a 4 bytes
    'varchar': 2,       # variable alineado a 4 bytes
    'date': 3,          # 4 bytes alineado a 4 bytes
    'jsonb': 4,         # jsonb
    'text': 5,          # variable alineado a 4 bytes
    'numeric': 6,       # variable alineado a 4 bytes
    'bool': 7,          # 1 byte alineado a 1 byte
    'timestamp': 8,     # 8 bytes alineado a 8 bytes
    'float8': 9,        # 8 bytes alineado a 8 bytes
}

#: El valor que la fuente da a un tipo desconocido — el ``lambda: 16`` de su
#: ``defaultdict``. Se nombra para que el consumidor no lo teclee.
SQL_ORDER_BY_TYPE_UNKNOWN = 16


def sql_order_by_type(udt_name):
    """El orden prescrito del tipo dado, o el de un tipo desconocido.

    ≙ la lectura ``SQL_ORDER_BY_TYPE[udt]`` de la fuente, que su
    ``defaultdict`` resuelve a 16. Aquí es una función porque el mapa es un
    ``dict`` llano: el default se aplica al leer y no muta el mapa.
    """
    return SQL_ORDER_BY_TYPE.get(udt_name, SQL_ORDER_BY_TYPE_UNKNOWN)



class SQL:
    """≙ ``SQL`` (``odoo19c: odoo/tools/sql.py:46``) — fragmento SQL con sus
    parámetros, componible::

        sql = SQL("UPDATE TABLE foo SET a = %s, b = %s", 'hello', 42)
        cursor.execute(sql.code, sql.params)

    El código es una plantilla printf (``%``) con argumentos posicionales
    (``%s``) o por nombre (``%(name)s``). El carácter ``%`` literal siempre
    va escapado como ``%%``, incluso sin parámetros
    (``SQL("foo LIKE 'a%%'")``).

    Los argumentos pueden ser parámetros reales u objetos ``SQL`` — de ahí la
    composición::

        sql = SQL(
            "UPDATE TABLE %s SET %s",
            SQL.identifier(tablename),
            SQL("%s = %s", SQL.identifier(columnname), value),
        )

    El código combinado sale por ``sql.code`` y los parámetros combinados por
    ``sql.params``, así que N fragmentos se componen sin cuadrar sus
    parámetros a mano. El segundo propósito es desalentar la inyección: si
    ``code`` es un literal, el objeto es seguro siempre que los ``SQL``
    anidados lo sean.

    El wrapper puede llevar la metadata ``to_flush``: campos de los que el
    código depende, accesibles (los propios y los de sus partes) por el
    iterable ``sql.to_flush``. La referencia lo tipa con ``odoo.fields.Field``;
    aquí se acepta cualquier objeto campo (divergencia declarada: el tipo
    ``Field`` de la referencia no gobierna este árbol y las anotaciones que
    lo citan se omiten).

    **Adaptaciones a este stack (no existen en la referencia):**

    - En la referencia ``cr.execute(sql)`` acepta el objeto porque su cursor
      lo desenvuelve; el cursor de Django/psycopg 3 no — aquí se ejecuta con
      ``cursor.execute(sql.code, sql.params)``.
    - ``output_field`` (keyword-only) + :meth:`resolve_expression`: conservan
      el uso del alias ``RawSQL`` retirado — un ``SQL('NULL',
      output_field=DecimalField())`` sigue siendo utilizable como expresión
      del ORM en ``annotate()``/``aggregate()`` (consumidor vivo:
      ``addons/stock/models/stock_quant.py:831,834``). Como ``to_flush``, el
      nombre ``output_field`` queda reservado y no puede usarse como
      parámetro por nombre de la plantilla.
    """
    __slots__ = ('__code', '__params', '__to_flush', '__output_field')

    # pylint: disable=keyword-arg-before-vararg
    def __init__(self, code="", /, *args, to_flush=None, output_field=None, **kwargs):
        # ≙ ``__init__`` (``odoo19c: odoo/tools/sql.py:89-135``); la rama de
        # ``output_field`` es la adaptación declarada arriba.
        if isinstance(code, SQL):
            if args or kwargs or to_flush or output_field:
                raise TypeError("SQL() unexpected arguments when code has type SQL")
            self.__code = code.__code
            self.__params = code.__params
            self.__to_flush = code.__to_flush
            self.__output_field = code.__output_field
            return

        # valida la forma del código y de los parámetros
        if args and kwargs:
            raise TypeError("SQL() takes either positional arguments, or named arguments")

        if kwargs:
            code, args = named_to_positional_printf(code, kwargs)
        elif not args:
            code % ()  # verifica que el código no contenga %s sin parámetro
            self.__code = code
            self.__params = ()
            if to_flush is None:
                self.__to_flush = ()
            elif hasattr(to_flush, '__iter__'):
                self.__to_flush = tuple(to_flush)
            else:
                self.__to_flush = (to_flush,)
            self.__output_field = output_field
            return

        code_list = []
        params_list = []
        to_flush_list = []
        for arg in args:
            if isinstance(arg, SQL):
                code_list.append(arg.__code)
                params_list.extend(arg.__params)
                to_flush_list.extend(arg.__to_flush)
            else:
                code_list.append("%s")
                params_list.append(arg)
        if to_flush is not None:
            if hasattr(to_flush, '__iter__'):
                to_flush_list.extend(to_flush)
            else:
                to_flush_list.append(to_flush)

        self.__code = code.replace('%%', '%%%%') % tuple(code_list)
        self.__params = tuple(params_list)
        self.__to_flush = tuple(to_flush_list)
        self.__output_field = output_field

    @property
    def code(self):
        """El código SQL combinado (``odoo19c: odoo/tools/sql.py:137-140``)."""
        return self.__code

    @property
    def params(self):
        """Los parámetros combinados, como lista
        (``odoo19c: odoo/tools/sql.py:142-145``).
        """
        return list(self.__params)

    @property
    def to_flush(self):
        """Iterable de los campos a vaciar en la metadata de ``self`` y de
        todas sus partes (``odoo19c: odoo/tools/sql.py:147-152``).
        """
        return self.__to_flush

    def __repr__(self):
        # ≙ ``__repr__`` (``odoo19c: odoo/tools/sql.py:154-155``)
        return f"SQL({', '.join(map(repr, [self.__code, *self.__params]))})"

    def __bool__(self):
        # ≙ ``__bool__`` (``odoo19c: odoo/tools/sql.py:157-158``)
        return bool(self.__code)

    def __eq__(self, other):
        # ≙ ``__eq__`` (``odoo19c: odoo/tools/sql.py:160-161``)
        return isinstance(other, SQL) and self.__code == other.__code and self.__params == other.__params

    def __hash__(self):
        # ≙ ``__hash__`` (``odoo19c: odoo/tools/sql.py:163-164``)
        return hash((self.__code, self.__params))

    def __iter__(self):
        """≙ ``__iter__`` (``odoo19c: odoo/tools/sql.py:166-176``). Rinde
        ``self.code`` y ``self.params`` — retrocompatibilidad que la propia
        referencia declara deprecada::

            code, params = sql
        """
        warnings.warn("Deprecated since 19.0, use code and params properties directly", DeprecationWarning)
        yield self.code
        yield self.params

    def join(self, args):
        """≙ ``join`` (``odoo19c: odoo/tools/sql.py:178-192``): une objetos
        ``SQL`` o parámetros con ``self`` como separador.
        """
        args = list(args)
        # optimizaciones para los casos especiales
        if len(args) == 0:
            return SQL()
        if len(args) == 1 and isinstance(args[0], SQL):
            return args[0]
        if not self.__params:
            return SQL(self.__code.join("%s" for arg in args), *args)
        # caso general: alterna args con self
        items = [self] * (len(args) * 2 - 1)
        for index, arg in enumerate(args):
            items[index * 2] = arg
        return SQL("%s" * len(items), *items)

    @classmethod
    def identifier(cls, name, subname=None, to_flush=None):
        """≙ ``identifier`` (``odoo19c: odoo/tools/sql.py:194-201``): un
        objeto ``SQL`` que representa un identificador (entrecomillado).
        """
        assert name.isidentifier() or IDENT_RE.match(name), f"{name!r} invalid for SQL.identifier()"
        if subname is None:
            return cls(f'"{name}"', to_flush=to_flush)
        assert subname.isidentifier() or IDENT_RE.match(subname), f"{subname!r} invalid for SQL.identifier()"
        return cls(f'"{name}"."{subname}"', to_flush=to_flush)

    def resolve_expression(self, *args, **kwargs):
        """Adaptación Django — NO existe en la referencia.

        Hace al fragmento utilizable como expresión del ORM
        (``annotate()``/``aggregate()``): delega en un ``RawSQL`` con el
        ``output_field`` recibido en el constructor. Es la superficie que el
        alias retirado (``SQL = RawSQL``) daba gratis y que
        ``stock_quant._read_group_select`` consume.
        """
        raw = RawSQL(self.__code, self.__params, output_field=self.__output_field)
        return raw.resolve_expression(*args, **kwargs)


def make_identifier(identifier: str) -> str:
    """≙ ``make_identifier`` (``odoo19c: odoo/tools/sql.py:604-612``).

    Devuelve ``identifier`` acotado al límite de PostgreSQL —**63 caracteres**—
    y, si hay que truncar, con un ``crc32`` pegado detrás para que siga siendo
    casi único. El caso que lo exige es el alias de un JOIN encadenado:
    ``Query.make_alias`` compone ``tabla__campo__campo`` y una cadena de tres
    saltos ya se pasa del límite. Sin este recorte PostgreSQL trunca por su
    cuenta y **dos alias distintos colapsan en uno**, que es un JOIN silencioso
    contra la tabla equivocada.
    """
    # si la longitud excede el límite de 63 caracteres de PostgreSQL.
    if len(identifier) > 63:
        # Hay que meter un hash crc32 y un guion bajo en 63 caracteres. El
        # espacio restante se usa como prefijo legible.
        return f"{identifier[:54]}_{crc32(identifier.encode()):08x}"
    return identifier


def pg_varchar(size=0):
    """≙ ``pg_varchar`` (``odoo19c: odoo/tools/sql.py:644-659``).

    Devuelve la declaración ``VARCHAR`` de la columna: ``VARCHAR(n)`` con un
    tamaño positivo y ``VARCHAR`` —sin límite— sin él. Verbatim de la fuente,
    incluida la mayúscula y el ``ValueError`` ante un tamaño no entero.

    **Sale hoy de la lista de pendientes de este módulo** porque su consumidor
    apareció, que es la condición que esa lista declara: ``Char._column_type``
    (``odoo19c: odoo/orm/fields_textual.py:494-496``) es
    ``('varchar', pg_varchar(self.size))``, y el porte de los atributos de
    clase de campo lo necesita para que un ``CharField`` responda su tipo de
    columna en vez de ``None``. Mismo camino que recorrieron
    ``make_identifier`` y ``SQL_ORDER_BY_TYPE``.
    """
    if size:
        if not isinstance(size, int):
            raise ValueError("VARCHAR parameter should be an int, got %s"
                             % type(size))
        if size > 0:
            return 'VARCHAR(%d)' % size
    return 'VARCHAR'


def escape_psql(to_escape):
    """≙ ``escape_psql`` (``odoo19c: odoo/tools/sql.py:640-641``).

    Escapa los comodines de ``LIKE``/``ILIKE`` para que el texto que teclea un
    usuario se busque **literal**. Sin esto, un término con ``%`` o ``_`` deja
    de ser un término y pasa a ser un patrón: ``%`` casa con cualquier cosa y
    ``_`` con cualquier carácter.

    El orden de los tres reemplazos no es intercambiable — la barra invertida
    va primero, porque si no, escaparía a las barras que los otros dos
    introducen.

    :param to_escape: el texto a escapar.
    :returns: el texto con ``\\``, ``%`` y ``_`` escapados.
    """
    return to_escape.replace('\\', r'\\').replace('%', r'\%').replace('_', r'\_')


def table_exists(cursor, table_name, schema=None):
    """== ``odoo.tools.sql.table_exists``: ¿existe la tabla?

    ``schema=None`` → el schema de la conexión (``current_schema``).
    """
    if schema is None:
        cursor.execute(
            'SELECT 1 FROM information_schema.tables '
            'WHERE table_schema = current_schema AND table_name = %s',
            [table_name])
    else:
        cursor.execute(
            'SELECT 1 FROM information_schema.tables '
            'WHERE table_schema = %s AND table_name = %s',
            [schema, table_name])
    return cursor.fetchone() is not None


def column_exists(cursor, table_name, column_name, schema=None):
    """== ``odoo.tools.sql.column_exists``: ¿existe la columna?"""
    if schema is None:
        cursor.execute(
            'SELECT 1 FROM information_schema.columns '
            'WHERE table_schema = current_schema AND table_name = %s AND column_name = %s',
            [table_name, column_name])
    else:
        cursor.execute(
            'SELECT 1 FROM information_schema.columns '
            'WHERE table_schema = %s AND table_name = %s AND column_name = %s',
            [schema, table_name, column_name])
    return cursor.fetchone() is not None


def table_columns(cursor, table_name, schema=None):
    """== ``odoo.tools.sql.table_columns``: columnas de la tabla y su forma.

    Devuelve ``{nombre: {udt_name, character_maximum_length, is_nullable}}``.
    Fiel a ``odoo19c: odoo/tools/sql.py`` — incluida su omisión deliberada de
    ``character_octet_length``, que su comentario justifica: en hospedaje
    compartido (Heroku, OVH) el rol de la aplicación puede no tener permiso
    para leer esa columna, y pedirla haría fallar la consulta entera.

    La referencia devuelve el ``row`` de ``dictfetchall()``; aquí se arma el
    diccionario a mano porque el cursor de Django devuelve tuplas.
    """
    if schema is None:
        cursor.execute(
            'SELECT column_name, udt_name, character_maximum_length, is_nullable '
            'FROM information_schema.columns '
            'WHERE table_name = %s AND table_schema = current_schema',
            [table_name])
    else:
        cursor.execute(
            'SELECT column_name, udt_name, character_maximum_length, is_nullable '
            'FROM information_schema.columns '
            'WHERE table_name = %s AND table_schema = %s',
            [table_name, schema])
    return {
        fila[0]: {
            'column_name': fila[0],
            'udt_name': fila[1],
            'character_maximum_length': fila[2],
            'is_nullable': fila[3],
        }
        for fila in cursor.fetchall()
    }


def index_exists(cursor, table_name, index_name, schema=None):
    """== ``odoo.tools.sql.index_exists``: ¿existe el índice? (``pg_indexes``)."""
    if schema is None:
        cursor.execute(
            'SELECT 1 FROM pg_indexes '
            'WHERE schemaname = current_schema AND tablename = %s AND indexname = %s '
            'LIMIT 1', [table_name, index_name])
    else:
        cursor.execute(
            'SELECT 1 FROM pg_indexes '
            'WHERE schemaname = %s AND tablename = %s AND indexname = %s '
            'LIMIT 1', [schema, table_name, index_name])
    return cursor.fetchone() is not None
