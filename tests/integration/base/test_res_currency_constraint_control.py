"""Control — los casos de la restricción caen si la restricción no está.

Una mutación del ``Meta.constraints`` **es invisible** con ``--reuse-db``: la
restricción vive en la base ya migrada, no en la declaración. Medido: cambiar
``__gt=0`` por ``__gte=0`` en el modelo deja los 9 casos en verde.

Eso no significa que los casos no discriminen — significa que el instrumento
correcto para probarlos no es la mutación del código, sino **retirar la
restricción de la base**. Este archivo lo hace y lo mide, y por eso vive en el
árbol en vez de en un turno: el control tiene que poder volver a correrse.
"""
import pytest

from django.db import IntegrityError, connection, transaction

from addons.base.models import ResCurrency

pytestmark = pytest.mark.integration

CONSTRAINT = 'res_currency_rounding_gt_zero'


@pytest.fixture
def without_the_constraint(db):
    """Retira la restricción, cede el control, y la restaura pase lo que pase."""
    with connection.cursor() as cursor:
        cursor.execute(
            f'ALTER TABLE res_currency DROP CONSTRAINT IF EXISTS {CONSTRAINT}')
    try:
        yield
    finally:
        # Las filas que el caso creó mientras la restricción no estaba la
        # violarían al volver a ponerla. Se retiran primero: restaurar la
        # restricción es restaurar el invariante, no sólo la declaración.
        #
        # pytest-django deshace la transacción del caso DESPUÉS del teardown,
        # así que aquí las filas todavía están.
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM res_currency WHERE rounding <= 0')
            # El DELETE deja disparadores de FK diferidos, y PostgreSQL no
            # admite ALTER TABLE con eventos pendientes. Se fuerzan antes.
            cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
            cursor.execute(
                f'ALTER TABLE res_currency ADD CONSTRAINT {CONSTRAINT} '
                f'CHECK (rounding > 0)')


def test_the_constraint_is_what_refuses_a_zero_rounding(db):
    """Con la restricción puesta: la fila se rechaza."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ResCurrency.objects.create(name='ZC1', symbol='z', rounding='0')


def test_without_the_constraint_a_zero_rounding_is_stored(
        without_the_constraint):
    """Sin ella: la fila **entra**, y ése es el hecho que la restricción cubre.

    Es el control que la mutación del código no puede dar. Si este caso
    fallara, el rechazo del caso anterior vendría de otra parte —una validación
    del modelo, un default— y la restricción no estaría midiendo nada.
    """
    currency = ResCurrency.objects.create(name='ZC2', symbol='z', rounding='0')
    currency.refresh_from_db()
    assert currency.rounding == 0
