"""Cursor, transacción del motor y puntos de retorno — ≙ ``odoo/sql_db.py``.

Es la casa de lo que la fuente declara en ``odoo19c: odoo/sql_db.py``: el
:class:`Cursor` que :meth:`orm.registry.Registry.cursor` entrega y los
:class:`Savepoint` que ``cr.savepoint()`` abre. ``Savepoint`` vivía en
``service.db``; se mudó aquí porque ``Registry`` no puede importar
``service.db`` sin cerrar un ciclo con ``orm.environments``, y ``service.db``
lo reexporta para sus consumidores.

El cursor de la fuente es una transacción de PostgreSQL sobre una conexión
del pool. Aquí la conexión la trae Django: cada :class:`Cursor` registra un
alias efímero con la configuración del alias del registro, y la transacción
del ORM cuelga de esa conexión (``orm.environments._connection_transaction``)
como allá cuelga de ``cr.transaction``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
registry-cursor-unit-of-work.md``.
"""
import copy
import itertools
import logging
import re
import threading
import warnings
from contextlib import contextmanager
from datetime import timedelta

import psycopg
from django.db import DEFAULT_DB_ALIAS, connections, transaction

import orm.environments
from tools.misc import Callbacks, split_every
from tools.profiler import real_time
from tools.sql import SQL

_logger = logging.getLogger(__name__)

re_from = re.compile(r'\bfrom\s+"?([a-zA-Z_0-9]+)\b', re.IGNORECASE)
re_into = re.compile(r'\binto\s+"?([a-zA-Z_0-9]+)\b', re.IGNORECASE)


def categorize_query(decoded_query):
    """≙ ``categorize_query`` (``odoo19c: odoo/sql_db.py:68-79``): la tabla
    que una consulta lee o escribe, para la estadística de :meth:`print_log`.
    """
    res_into = re_into.search(decoded_query)
    # prioriza ``insert`` sobre ``select``: un ``select`` dentro de un
    # ``insert`` no cuenta como lectura
    if res_into:
        return 'into', res_into.group(1)
    res_from = re_from.search(decoded_query)
    if res_from:
        return 'from', res_from.group(1)
    return 'other', None


#: ≙ ``sql_counter`` (``:82``): consultas ejecutadas por todos los cursores.
sql_counter = 0

#: Secuencia de los alias efímeros: uno por cursor, nunca reutilizado.
_cursor_aliases = itertools.count(1)


class Savepoint:
    """≙ ``Savepoint`` (``odoo19c: odoo/sql_db.py:87-129``).

    «Reifies an active breakpoint, allows ``BaseCursor.savepoint`` users to
    internally rollback the savepoint (as many times as they want) without
    having to implement their own savepointing, or triggering exceptions.»

    Lo consume :meth:`orm.models.RecordLoaderMixin.load`: abre uno al empezar y
    **vuelve a él** cada vez que una fila del archivo revienta. Sin ese retorno
    la transacción de PostgreSQL queda en estado abortado y el resto del
    archivo ya no se puede importar — de ahí que el cargador lo necesite y no
    le baste con capturar la excepción.

    DIVERGENCIA DE MECANISMO, declarada: la fuente emite ``SAVEPOINT "<uuid>"``
    a mano sobre su cursor. Aquí lo emite la **API pública de Django**
    (``transaction.savepoint`` / ``savepoint_rollback`` /
    ``savepoint_commit``),
    que hace exactamente eso mismo y además mantiene coherente el estado que
    ``atomic`` lleva de la conexión. El nombre del punto lo genera Django y se
    guarda en :attr:`name`, igual que allá.

    El que vacía la transacción del ORM al abrir y al cerrar es
    :class:`_FlushingSavepoint`, y el que la fuente abre por defecto es ése
    (:func:`savepoint`). Esta clase es el ``Savepoint`` llano.
    """

    def __init__(self, connection):
        self._connection = connection
        self.name = transaction.savepoint(using=connection.alias)
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close(rollback=exc_type is not None)

    def close(self, *, rollback=True):
        if not self.closed:
            self._close(rollback)

    def rollback(self):
        """Vuelve al punto de retorno, también tras un error de la base.

        ≙ ``ROLLBACK TO SAVEPOINT``, que en PostgreSQL recupera una
        transacción abortada: es lo que la fuente hace tras un INSERT
        rechazado (``odoo19c: odoo/orm/models.py:985-1022``). Django marca la
        conexión (``needs_rollback``) cuando una consulta falla dentro de
        ``atomic`` y desde ahí rechaza toda consulta, este ``ROLLBACK``
        incluido. Su propio ``Atomic.__exit__`` limpia la marca antes de
        volver a su punto de retorno (``django/db/transaction.py:273-283``);
        aquí se hace lo mismo, porque el punto se abrió en este mismo nivel
        y deshace todo lo que vino después de él, el error incluido.
        """
        self._connection.needs_rollback = False
        transaction.savepoint_rollback(self.name, using=self._connection.alias)

    def _close(self, rollback):
        if rollback:
            self.rollback()
        transaction.savepoint_commit(self.name, using=self._connection.alias)
        self.closed = True


class _FlushingSavepoint(Savepoint):
    """≙ ``_FlushingSavepoint`` (``odoo19c: odoo/sql_db.py:132-151``).

    Al abrir vacía la transacción del ORM (``cr.flush()``: cómputos y
    escrituras pendientes); al cerrar sin retorno vuelve a vaciarla, y si ese
    vaciado lanza, el punto se deshace y la excepción sube. El ``cr.clear()``
    del retorno (``:137-140``) no se repite aquí: ``savepoint_rollback`` de la
    conexión ya vacía la transacción del ORM
    (``orm.environments._CURSOR_CUTS``),
    que es el mismo corte de la fuente portado al cursor.

    Esta clase decía antes que no tenía contraparte porque Django escribe cada
    ``save()`` en el acto. Era cierto de las escrituras y falso de los
    cómputos: el ORM sí encola recálculos (``env.fields_to_compute()``), y un
    ``@api.constrains`` sobre un calculado almacenado sólo salta cuando esa
    cola se vacía.
    """

    def __init__(self, connection, cursor=None):
        self._flush = (cursor.flush if cursor is not None else
                       orm.environments._connection_transaction(
                           connection.alias).flush)
        self._flush()
        super().__init__(connection)

    def _close(self, rollback):
        try:
            if not rollback:
                self._flush()
        except Exception:
            rollback = True
            raise
        finally:
            super()._close(rollback)


def savepoint(connection, flush=True):
    """≙ ``BaseCursor.savepoint`` (``odoo19c: odoo/sql_db.py:217-226``): con
    ``flush`` (el defecto) el punto vacía y limpia la transacción del ORM."""
    if flush:
        return _FlushingSavepoint(connection)
    return Savepoint(connection)


class Cursor:
    """Una transacción de PostgreSQL con su conexión propia.

    ≙ ``BaseCursor`` + ``Cursor`` (``odoo19c: odoo/sql_db.py:156-588``).
    Docstring de la fuente: *"Represents an open transaction to the PostgreSQL
    DB backend, acting as a lightweight wrapper around psycopg2's cursor
    objects"*.

    **La conexión.** La fuente toma una del pool; aquí se registra un alias
    efímero ``<alias>__cursor_<n>`` con la configuración vigente del alias de
    origen (``settings_dict`` de su conexión, que bajo pruebas ya nombra la
    base de pruebas) y se abre en modo transacción (``autocommit`` apagado),
    que es como trabaja psycopg2 allá. :meth:`close` la cierra y retira el
    alias: ``_close`` de la fuente la devuelve al pool.

    **La transacción del ORM** cuelga de esa conexión: el primer
    ``Environment(cr.alias, ...)`` la crea, igual que ``Environment.__new__``
    crea ``cr.transaction`` (``environments.py:70-72``). Muere con el cursor:
    el corte ``close`` de la conexión la descarta.

    **El nivel de aislamiento** de la fuente es ``REPEATABLE READ``
    (``:300``); aquí rige el que declare ``OPTIONS`` del alias de origen.
    """

    #: ≙ ``IN_MAX`` (``:158``): tamaño razonable de una lista ``IN``.
    IN_MAX = 1000

    def __init__(self, using=DEFAULT_DB_ALIAS, readonly=False):
        origin = connections[using]
        self.alias = f'{using}__cursor_{next(_cursor_aliases)}'
        connections.settings[self.alias] = copy.deepcopy(
            origin.settings_dict)
        self._cnx = connections[self.alias]
        self._cnx.set_autocommit(False)
        self._obj = self._cnx.cursor()
        self._closed = False
        self._readonly = readonly
        self.dbname = origin.settings_dict['NAME']
        # ≙ ``BaseCursor.__init__`` (``:164-174``)
        self.precommit = Callbacks()
        self.postcommit = Callbacks()
        self.prerollback = Callbacks()
        self.postrollback = Callbacks()
        self._now = None
        self.cache = {}
        # ≙ las estadísticas de ``Cursor.__init__`` (``:285-295``)
        self.sql_from_log = {}
        self.sql_into_log = {}
        self.sql_log_count = 0

    @property
    def transaction(self):
        """≙ ``cr.transaction``: ``None`` hasta que un entorno la crea."""
        return getattr(self._cnx, orm.environments._TRANSACTION_ATTRIBUTE,
                       None)

    # --- BaseCursor -------------------------------------------------------

    def flush(self):
        """≙ ``BaseCursor.flush`` (``:176-187``) — *"Flush the current
        transaction, and run precommit hooks"*."""
        # un ``precommit`` puede añadir otro o disparar cambios en el ORM:
        # se vuelca y se repite, con el tope de la fuente
        for _ in range(10):
            if self.transaction is not None:
                self.transaction.flush()
            if not self.precommit:
                break
            self.precommit.run()
        else:
            _logger.warning("Too many iterations for flushing the cursor!")

    def clear(self):
        """≙ ``BaseCursor.clear`` (``:189-193``) — *"Clear the current
        transaction, and clear precommit hooks"*."""
        if self.transaction is not None:
            self.transaction.clear()
        self.precommit.clear()

    def reset(self):
        """≙ ``BaseCursor.reset`` (``:195-200``) — *"Reset the current
        transaction (this invalidates more that clear())"*."""
        if self.transaction is not None:
            self.transaction.reset()

    def savepoint(self, flush=True):
        """≙ ``BaseCursor.savepoint`` (``:217-226``)."""
        if flush:
            return _FlushingSavepoint(self._cnx, self)
        return Savepoint(self._cnx)

    def __enter__(self):
        """≙ ``BaseCursor.__enter__`` (``:228-238``): ``with cr:`` confirma si
        no hubo error y cierra siempre."""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type is None:
                self.commit()
        finally:
            self.close()

    def _build_dict(self, row):
        description = self._obj.description
        assert description, "Query does not have results"
        return {column.name: row[index]
                for index, column in enumerate(description)}

    def dictfetchone(self):
        """≙ ``Cursor.dictfetchone`` (``:308-310``)."""
        row = self._obj.fetchone()
        return self._build_dict(row) if row else None

    def dictfetchmany(self, size):
        """≙ ``Cursor.dictfetchmany`` (``:312-313``)."""
        return [self._build_dict(row) for row in self._obj.fetchmany(size)]

    def dictfetchall(self):
        """≙ ``Cursor.dictfetchall`` (``:315-316``)."""
        return [self._build_dict(row) for row in self._obj.fetchall()]

    def split_for_in_conditions(self, ids, size=0):
        """≙ ``BaseCursor.split_for_in_conditions`` (``:264-269``)."""
        warnings.warn("Deprecated since 19.0, use split_every(cr.IN_MAX, ids)",
                      DeprecationWarning)
        return split_every(size or self.IN_MAX, ids)

    def now(self):
        """≙ ``BaseCursor.now`` (``:271-278``) — *"Return the transaction's
        timestamp NOW() AT TIME ZONE 'UTC'"*."""
        if self._now is None:
            self.execute("SELECT (now() AT TIME ZONE 'UTC')")
            row = self.fetchone()
            assert row
            self._now = row[0]
        return self._now

    # --- Cursor -----------------------------------------------------------

    def __del__(self):
        """≙ ``Cursor.__del__`` (``:318-332``): un cursor que nadie cerró se
        avisa y se cierra. Sólo se cierra desde su hilo: Django rechaza usar
        una conexión desde otro."""
        if getattr(self, '_closed', True):
            return
        _logger.warning("Cursor not closed explicitly")
        if threading.get_ident() == self._cnx._thread_ident:
            self._close(leak=True)

    def _format(self, query, params=None):
        """≙ ``Cursor._format`` (``:334-336``)."""
        return self.mogrify(query, params).decode('utf-8', 'replace')

    def mogrify(self, query, params=None):
        """≙ ``Cursor.mogrify`` (``:338-342``): la consulta con sus
        parámetros incrustados, como la enviaría el cliente."""
        if isinstance(query, SQL):
            assert params is None, "Unexpected parameters for SQL query object"
            query, params = query.code, query.params
        raw = self._cnx.connection
        return psycopg.ClientCursor(raw).mogrify(query, params).encode()

    def execute(self, query, params=None, log_exceptions=True):
        """≙ ``Cursor.execute`` (``:344-400``)."""
        global sql_counter
        if isinstance(query, SQL):
            assert params is None, "Unexpected parameters for SQL query object"
            query, params = query.code, query.params
        if params and not isinstance(params, (tuple, list, dict)):
            raise ValueError("SQL query parameters should be a tuple, list or "
                             "dict; got %r" % (params,))
        start = real_time()
        current_thread = threading.current_thread()
        try:
            self._obj.execute(query, params)
        except Exception as error:
            if log_exceptions:
                _logger.error("bad query: %s\nERROR: %s", query, error)
            raise
        finally:
            delay = real_time() - start
            if _logger.isEnabledFor(logging.DEBUG):
                _logger.debug("[%.3f ms] query: %s", 1000 * delay,
                              self._format(query, params))
        self.sql_log_count += 1
        sql_counter += 1
        if hasattr(current_thread, 'query_count'):
            current_thread.query_count += 1
        if hasattr(current_thread, 'query_time'):
            current_thread.query_time += delay
        if _logger.isEnabledFor(logging.DEBUG):
            query_type, table = categorize_query(query)
            log_target = {'into': self.sql_into_log,
                          'from': self.sql_from_log}.get(query_type)
            if log_target is not None:
                stat_count, stat_time = log_target.get(table or '', (0, 0))
                log_target[table or ''] = (stat_count + 1,
                                           stat_time + delay * 1E6)

    def execute_values(self, query, argslist, template=None, page_size=100,
                       fetch=False):
        """≙ ``Cursor.execute_values`` (``:402-411``), el proxy de
        ``psycopg2.extras.execute_values``: la consulta lleva un ``%s`` que
        se sustituye por una página de filas ``VALUES``; con ``fetch`` se
        devuelven las filas de todas las páginas."""
        rows = list(argslist)
        result = []
        for page in split_every(page_size, rows, piece_maker=list):
            values = b','.join(
                self.mogrify(template or self._row_template(row), row)
                for row in page)
            self.execute(query.replace('%s', values.decode(), 1))
            if fetch:
                result.extend(self._obj.fetchall())
        return result if fetch else None

    @staticmethod
    def _row_template(row):
        if isinstance(row, dict):
            return '(' + ','.join(f'%({key})s' for key in row) + ')'
        return '(' + ','.join(['%s'] * len(row)) + ')'

    def print_log(self):
        """≙ ``Cursor.print_log`` (``:413-436``): la estadística por tabla
        que ``execute`` acumula en modo ``DEBUG``."""
        if not _logger.isEnabledFor(logging.DEBUG):
            return

        def process(log_type):
            sqllog = {'from': self.sql_from_log,
                      'into': self.sql_into_log}[log_type]
            total = 0.0
            if sqllog:
                _logger.debug("SQL LOG %s:", log_type)
                for table, (stat_count, stat_time) in sorted(
                        sqllog.items(), key=lambda item: item[1]):
                    delay = timedelta(microseconds=stat_time)
                    _logger.debug("table: %s: %s/%s", table, delay,
                                  stat_count)
                    total += stat_time
                sqllog.clear()
            total_delay = timedelta(microseconds=total)
            _logger.debug("SUM %s:%s/%d [%d]", log_type, total_delay,
                          self.sql_log_count, sql_counter)

        process('from')
        process('into')
        self.sql_log_count = 0

    @contextmanager
    def _enable_logging(self):
        """≙ ``Cursor._enable_logging`` (``:438-449``)."""
        level = _logger.level
        _logger.setLevel(logging.DEBUG)
        try:
            yield
        finally:
            _logger.setLevel(level)

    def close(self):
        """≙ ``Cursor.close`` (``:451-453``)."""
        if not self.closed:
            return self._close(False)
        return None

    def _close(self, leak=False):
        """≙ ``Cursor._close`` (``:455-480``): vacía la caché, revierte lo
        no confirmado y suelta la conexión. Aquí soltarla es cerrarla y
        retirar su alias; el corte ``close`` descarta la transacción del
        ORM, que es el «la transacción muere con su cursor» de la fuente."""
        if self._closed:
            return
        self.cache.clear()
        self.print_log()
        try:
            self._obj.close()
            self.rollback()
        finally:
            self._closed = True
            try:
                self._cnx.close()
            finally:
                del connections[self.alias]
                connections.settings.pop(self.alias, None)
        if leak:
            _logger.warning("Cursor %s closed by the garbage collector",
                            self.alias)

    def commit(self):
        """≙ ``Cursor.commit`` (``:482-490``) — *"Perform an SQL COMMIT"*."""
        self.flush()
        self._cnx.commit()
        self.clear()
        self._now = None
        self.prerollback.clear()
        self.postrollback.clear()
        self.postcommit.run()

    def rollback(self):
        """≙ ``Cursor.rollback`` (``:492-499``) — *"Perform an SQL
        ROLLBACK"*."""
        self.clear()
        self.postcommit.clear()
        self.prerollback.run()
        self._cnx.rollback()
        self._now = None
        self.postrollback.run()

    def __getattr__(self, name):
        """≙ ``Cursor.__getattr__`` (``:501-504``): lo demás es del cursor
        de la base (``fetchone``, ``rowcount``, ``description`` …)."""
        if name == '_obj' or self.__dict__.get('_closed'):
            raise psycopg.InterfaceError("Cursor already closed")
        return getattr(self._obj, name)

    @property
    def closed(self):
        """≙ ``Cursor.closed`` (``:506-508``)."""
        return self._closed

    @property
    def readonly(self):
        """≙ ``Cursor.readonly`` (``:510-512``)."""
        return self._readonly
