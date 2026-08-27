"""Las columnas de auditoría de ``ir.sequence`` y su rango (tarea #40).

La fuente **no** declara ``_log_access = False`` en ninguna de sus dos clases
(``odoo19c: odoo/addons/base/models/ir_sequence.py``), así que su ORM les añade
las columnas de auditoría. Aquí ninguna de las dos las llevaba: se declaró como
divergencia heredada con sucesor, porque añadir una columna con ``auto_now_add``
a una tabla viva bloquea ``makemigrations`` en su cuestionario y la conducta
correcta es una migración escrita a mano, no responderlo.

Qué se mide, y qué NO
----------------------

La forma del log-access adoptada en este árbol es ``TimeStampedModel``, con
**dos** columnas —``created_at``/``updated_at``, ≙ ``create_date``/
``write_date``— y no cuatro. Las de *quién* (``create_uid``/``write_uid``) no
existen en **ningún** modelo del proyecto: medido,
``grep -rln "create_uid = fields" src/ addons/`` da 0. Es una divergencia del
mixin, ya declarada como alternativa diferida en DEC-09, no de estas dos tablas.

Así que estos casos miden que las dos tablas dejaron de ser la excepción, no
que el proyecto tenga las cuatro.

El control que puede fallar
---------------------------

Quitando ``TimeStampedModel`` de las dos clases, los cuatro casos caen: los dos
de existencia de columna por ``FieldDoesNotExist`` y los dos de poblado por
``AttributeError``. Ninguno sobrevive, porque los cuatro preguntan por el mismo
mixin.

*Métrica:* columnas declaradas en ``_meta`` y su valor tras crear la fila.
*Ciega a:* si la migración se aplicó sobre una base **con filas previas** — el
banco de pruebas construye la tabla desde cero, así que el ``default`` de la
migración no se ejerce aquí. Eso lo mide la creación desde cero de #61.
"""
import pytest

from addons.base.models.ir_sequence import IrSequence, IrSequenceDateRange

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.mark.parametrize('model', [IrSequence, IrSequenceDateRange])
@pytest.mark.parametrize('column', ['created_at', 'updated_at'])
def test_the_audit_column_is_declared(db, model, column):
    """≙ las que el ORM de la fuente añade sin ``_log_access = False``."""
    assert model._meta.get_field(column) is not None


def test_a_sequence_records_when_it_was_created(db):
    sequence = IrSequence.objects.create(name='Folio', code='folio.test')
    assert sequence.created_at is not None
    assert sequence.updated_at is not None


def test_a_date_range_records_when_it_was_created(db):
    sequence = IrSequence.objects.create(name='Folio', code='folio.range')
    date_range = IrSequenceDateRange.objects.create(
        sequence=sequence, date_from='2026-01-01', date_to='2026-12-31')
    assert date_range.created_at is not None
    assert date_range.updated_at is not None
