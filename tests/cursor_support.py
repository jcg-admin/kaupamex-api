"""El cursor de pruebas — ≙ ``odoo/tests/test_cursor.py``.

En la fuente, mientras corre una prueba, ``registry.cursor()`` no abre una
conexión: ``odoo/tests/common.py:800-806`` lo sustituye por un
:class:`TestCursor` que trabaja **sobre el cursor de la prueba** y simula
``commit``/``rollback``/``close`` con savepoints, para que lo confirmado por
una unidad de trabajo se deshaga con la prueba. Aquí la prueba es una
transacción de pytest-django sobre la conexión ``default``; una conexión
nueva, además de escapar de ese rollback, la rechaza Django dentro de un
``TestCase`` (``DatabaseOperationForbidden``).

**La transacción del ORM.** En la fuente cada ``TestCursor`` es un
``BaseCursor`` con ``transaction = None`` (``sql_db.py:174``): su primer
entorno crea una propia, aunque comparta la conexión. Aquí la transacción
cuelga de la conexión (``orm.environments._TRANSACTION_ATTRIBUTE``), así que
el cursor de pruebas **aparta** la de la prueba al abrirse —el primer
entorno crea otra— y la **devuelve** al cerrarse. Es el mismo ciclo: el
``default_env`` de la unidad de trabajo muere con su cursor.
"""
import threading
from datetime import datetime

from django.db import connections

import orm.environments
from sql_db import Savepoint, _logger
from tools.misc import Callbacks

#: ≙ el ``RLock`` del registro que serializa los cursores de pruebas.
_lock = threading.RLock()


class TestCursor:
    """≙ ``TestCursor`` (``odoo19c: odoo/tests/test_cursor.py:10-123``).

    Docstring de la fuente: *"A pseudo-cursor to be used for tests, on top of
    a real cursor. It keeps the transaction open across requests, and
    simulates committing, rolling back, and closing"*.
    """

    __test__ = False
    _cursors_stack = []

    def __init__(self, alias, readonly=False):
        self.alias = alias
        self._cnx = connections[alias]
        self.readonly = readonly
        self._now = None
        self._closed = False
        self.precommit = Callbacks()
        self.postcommit = Callbacks()
        self.prerollback = Callbacks()
        self.postrollback = Callbacks()
        self.cache = {}
        self._lock = _lock
        if not self._lock.acquire(timeout=20):
            raise Exception('Unable to acquire lock for test cursor after 20s')
        try:
            self._check_cursor_readonly()
        except Exception:
            self._lock.release()
            raise
        self._cursors_stack.append(self)
        # El savepoint de la fuente nace con la primera consulta, porque
        # todas pasan por ``execute``. Aquí el ORM escribe por la conexión de
        # Django sin pasar por el cursor: se abre al construirlo.
        self._savepoint = None
        self._obj = self._cnx.cursor()
        # la transacción del ORM de quien abrió el cursor queda apartada
        attribute = orm.environments._TRANSACTION_ATTRIBUTE
        self._outer_transaction = getattr(self._cnx, attribute, None)
        if hasattr(self._cnx, attribute):
            delattr(self._cnx, attribute)
        self._check_savepoint()

    @property
    def transaction(self):
        return getattr(self._cnx, orm.environments._TRANSACTION_ATTRIBUTE,
                       None)

    def _check_cursor_readonly(self):
        last_cursor = self._cursors_stack and self._cursors_stack[-1]
        if (last_cursor and last_cursor.readonly and not self.readonly
                and last_cursor._savepoint):
            raise Exception(
                'Opening a read/write test cursor from a readonly one')

    def _check_savepoint(self):
        if not self._savepoint:
            self._savepoint = Savepoint(self._cnx)
            if self.readonly:
                self._obj.execute('SET TRANSACTION READ ONLY')

    def flush(self):
        """≙ ``BaseCursor.flush`` (``odoo/sql_db.py:176-187``)."""
        for _ in range(10):
            if self.transaction is not None:
                self.transaction.flush()
            if not self.precommit:
                break
            self.precommit.run()
        else:
            _logger.warning("Too many iterations for flushing the cursor!")

    def clear(self):
        """≙ ``BaseCursor.clear`` (``odoo/sql_db.py:189-193``)."""
        if self.transaction is not None:
            self.transaction.clear()
        self.precommit.clear()

    def execute(self, query, params=None, log_exceptions=True):
        assert not self._closed, "Cannot use a closed cursor"
        self._check_savepoint()
        code, values = (query.code, query.params) if hasattr(
            query, 'code') else (query, params)
        return self._obj.execute(code, values)

    def close(self):
        if not self._closed:
            try:
                self.rollback()
                if self._savepoint:
                    self._savepoint.close(rollback=False)
            finally:
                self._closed = True
                attribute = orm.environments._TRANSACTION_ATTRIBUTE
                if self._outer_transaction is not None:
                    setattr(self._cnx, attribute, self._outer_transaction)
                elif hasattr(self._cnx, attribute):
                    delattr(self._cnx, attribute)
                top_of_stack = self._cursors_stack.pop()
                if top_of_stack is not self:
                    _logger.warning(
                        "Found different un-closed cursor when trying to "
                        "close %s: %s", self, top_of_stack)
                self._lock.release()

    def commit(self):
        """Perform an SQL ``COMMIT``."""
        self.flush()
        if self._savepoint:
            self._savepoint.close(rollback=self.readonly)
            self._savepoint = None
        self.clear()
        if not self._closed:
            self._check_savepoint()
        self.prerollback.clear()
        self.postrollback.clear()
        # TestCursor ignores post-commit hooks by default
        self.postcommit.clear()

    def rollback(self):
        """Perform an SQL ``ROLLBACK``."""
        self.clear()
        self.postcommit.clear()
        self.prerollback.run()
        if self._savepoint:
            self._savepoint.close(rollback=True)
            self._savepoint = None
        self.postrollback.run()
        if not self._closed:
            self._check_savepoint()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type is None:
                self.commit()
        finally:
            self.close()

    def __getattr__(self, name):
        return getattr(self._obj, name)

    def _build_dict(self, row):
        return {column.name: row[index]
                for index, column in enumerate(self._obj.description)}

    def dictfetchone(self):
        row = self._obj.fetchone()
        return self._build_dict(row) if row else None

    def dictfetchmany(self, size):
        return [self._build_dict(row) for row in self._obj.fetchmany(size)]

    def dictfetchall(self):
        return [self._build_dict(row) for row in self._obj.fetchall()]

    def now(self):
        """Return the transaction's timestamp ``datetime.now()``."""
        if self._now is None:
            self._now = datetime.now()
        return self._now

    @property
    def closed(self):
        return self._closed
