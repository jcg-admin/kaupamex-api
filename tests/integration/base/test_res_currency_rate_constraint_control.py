"""Control — el caso de ``rate > 0`` cae si la restricción no está.

Mismo instrumento que ``test_res_currency_constraint_control.py``, por la misma
razón medida: una mutación del ``Meta.constraints`` **es invisible** con
``--reuse-db``, porque la restricción vive en la base ya migrada y no en la
declaración. El control que sí discrimina la retira de la base.

Vive en el árbol —no en un turno— para que se pueda volver a correr.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError, connection, transaction

from addons.base.models import ResCurrency
from addons.base.models.res_currency_rate import ResCurrencyRate

pytestmark = pytest.mark.integration

CONSTRAINT = 'res_currency_rate_currency_rate_check'


@pytest.fixture
def currency(db):
    return ResCurrency.objects.create(name='XCC', symbol='c', rounding='0.01')


@pytest.fixture
def without_the_constraint(db):
    """Retira la restricción, cede el control, y la restaura pase lo que pase."""
    with connection.cursor() as cursor:
        cursor.execute(f'ALTER TABLE res_currency_rate '
                       f'DROP CONSTRAINT IF EXISTS {CONSTRAINT}')
    try:
        yield
    finally:
        # Las filas creadas sin la restricción la violarían al reponerla:
        # restaurar la restricción es restaurar el invariante, no sólo la
        # declaración. El DELETE deja disparadores de FK diferidos y PostgreSQL
        # rechaza ALTER TABLE con eventos pendientes, así que se fuerzan antes.
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM res_currency_rate WHERE rate <= 0')
            cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
            cursor.execute(
                f'ALTER TABLE res_currency_rate ADD CONSTRAINT {CONSTRAINT} '
                f'CHECK (rate > 0)')


def test_the_constraint_is_what_refuses_a_zero_rate(currency):
    """Con la restricción puesta: la fila se rechaza."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ResCurrencyRate.objects.create(
                currency=currency, name=date(2026, 3, 1), rate=Decimal('0'))


def test_without_the_constraint_a_zero_rate_is_stored(
        without_the_constraint, currency):
    """Sin ella: la fila **entra**, y ése es el hecho que la restricción cubre.

    Si este caso fallara, el rechazo del anterior vendría de otra parte —una
    validación del modelo, un default— y la restricción no mediría nada.
    """
    row = ResCurrencyRate.objects.create(
        currency=currency, name=date(2026, 3, 1), rate=Decimal('0'))
    row.refresh_from_db()
    assert row.rate == 0
