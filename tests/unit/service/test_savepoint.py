"""``Savepoint`` — el punto de retorno reificado (#132).

≙ ``odoo19c: odoo/sql_db.py:87-129``. Lo consume ``BaseModel.load``, que abre
uno al empezar y vuelve a él cada vez que una fila del archivo revienta: sin
ese retorno la transacción queda rota y el resto del archivo ya no se puede
importar.

Qué haría fallar a estos casos
==============================

Un punto de retorno que no retorna es indistinguible de uno que sí, salvo que
se mida el efecto en la base (sub-patrón D de
``metrica-decide-la-conclusion.md``). Por eso cada caso **escribe una fila** y
comprueba su presencia o su ausencia, en vez de inspeccionar el objeto.
"""

import pytest
from django.db import DEFAULT_DB_ALIAS, connections

from addons.base.models.res_country import ResCountry
from orm.environments import Environment
from orm.utils import SUPERUSER_ID
from service.db import Savepoint, savepoint


@pytest.mark.django_db(transaction=False)
class TestTheSavepointReturns:
    """El retorno explícito deshace lo escrito después de abrirlo."""

    def test_rollback_undoes_what_came_after(self):
        savepoint = Savepoint(connections[DEFAULT_DB_ALIAS])
        ResCountry.objects.create(name='Sinelandia', code='ZY')
        assert ResCountry.objects.filter(code='ZY').exists()

        savepoint.rollback()

        assert not ResCountry.objects.filter(code='ZY').exists()
        savepoint.close(rollback=False)

    def test_rollback_can_be_called_more_than_once(self):
        """
        «as many times as they want» — verbatim del docstring de la fuente.
        """
        savepoint = Savepoint(connections[DEFAULT_DB_ALIAS])
        ResCountry.objects.create(name='Sinelandia', code='ZY')

        savepoint.rollback()
        savepoint.rollback()

        assert not ResCountry.objects.filter(code='ZY').exists()
        savepoint.close(rollback=False)

    def test_closing_without_rollback_keeps_the_rows(self):
        savepoint = Savepoint(connections[DEFAULT_DB_ALIAS])
        ResCountry.objects.create(name='Sinelandia', code='ZY')

        savepoint.close(rollback=False)

        assert ResCountry.objects.filter(code='ZY').exists()

    def test_closing_twice_is_a_no_op(self):
        savepoint = Savepoint(connections[DEFAULT_DB_ALIAS])
        savepoint.close(rollback=False)
        assert savepoint.closed

        savepoint.close(rollback=False)

        assert savepoint.closed


@pytest.mark.django_db(transaction=False)
class TestTheContextManager:
    """Sale con retorno ante una excepción; sin él cuando el cuerpo termina."""

    def test_an_exception_rolls_back(self):
        with pytest.raises(RuntimeError):
            with Savepoint(connections[DEFAULT_DB_ALIAS]):
                ResCountry.objects.create(name='Sinelandia', code='ZY')
                raise RuntimeError('el cuerpo revienta')

        assert not ResCountry.objects.filter(code='ZY').exists()

    def test_a_clean_exit_releases(self):
        with Savepoint(connections[DEFAULT_DB_ALIAS]):
            ResCountry.objects.create(name='Sinelandia', code='ZY')

        assert ResCountry.objects.filter(code='ZY').exists()


@pytest.fixture
def pending_compute():
    """Un registro con un cálculo almacenado pendiente en la transacción:
    ``test_orm.message.name`` (``@depends('author.name', 'discussion.name')``)
    sin discusión, para que ``_check_author`` no aplique."""
    with Environment(None, SUPERUSER_ID, {}) as environment:
        message = environment['test_orm.message'].create(
            [{'body': 'savepoint'}])
        environment.flush_all()
        field = message._fields['name']
        environment.add_to_compute(field, message._ids)
        assert environment.fields_to_compute()
        yield environment, message


@pytest.mark.django_db(transaction=False)
class TestTheFlushingSavepoint:
    """≙ ``_FlushingSavepoint`` (``odoo19c: odoo/sql_db.py:132-151``), el que
    ``cr.savepoint()`` abre por defecto (``:217-226``)."""

    def test_opening_flushes_the_transaction(self, pending_compute):
        environment, _message = pending_compute
        with savepoint(connections[DEFAULT_DB_ALIAS]):
            assert not environment.fields_to_compute()

    def test_closing_without_error_flushes_again(self, pending_compute):
        environment, message = pending_compute
        with savepoint(connections[DEFAULT_DB_ALIAS]):
            environment.add_to_compute(message._fields['name'], message._ids)
        assert not environment.fields_to_compute()

    def test_the_rollback_clears_the_transaction(self, pending_compute):
        environment, message = pending_compute
        with pytest.raises(ZeroDivisionError):
            with savepoint(connections[DEFAULT_DB_ALIAS]):
                environment.add_to_compute(
                    message._fields['name'], message._ids)
                1 / 0
        assert not environment.fields_to_compute()

    def test_without_flush_nothing_is_flushed(self, pending_compute):
        """``savepoint(flush=False)`` es el ``Savepoint`` llano."""
        environment, _message = pending_compute
        with savepoint(connections[DEFAULT_DB_ALIAS], flush=False):
            assert environment.fields_to_compute()
