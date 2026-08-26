"""``get_next_char`` visto desde ``account_check_printing`` — el "peek".

≙ ``odoo19c: addons/account_check_printing/models/account_journal.py:53``
(``journal.check_next_number = sequence.get_next_char(
sequence.number_next_actual)``) — leer el folio que saldría **sin gastarlo**.

Estos casos vivían aquí porque el método lo colgaba este addon. Ya no: la
referencia **no declara** ``ir_sequence.py`` en ``account_check_printing``
—lo consume, no lo extiende— y ``get_next_char`` es API de ``base`` desde el
porte completo de ``src/addons/base/models/ir_sequence.py``. Ver H-API-792.

La suite se conserva en este addon porque lo que mide es **su** contrato de
consumo: que el peek no consuma y que coincida con lo que ``next_by_id``
habría dado. El método portado se prueba en
``tests/unit/base/test_ir_sequence_date_range.py``.
"""
import pytest

from addons.base.models import IrSequence

pytestmark = pytest.mark.django_db


class TestGetNextChar:
    def test_peek_does_not_consume(self):
        sequence = IrSequence.objects.create(name='Test', padding=5, number_next=1)
        first_peek = sequence.get_next_char(sequence.number_next)
        second_peek = sequence.get_next_char(sequence.number_next)
        assert first_peek == second_peek == '00001'
        sequence.refresh_from_db()
        assert sequence.number_next == 1

    def test_matches_the_format_next_by_id_would_produce(self):
        sequence = IrSequence.objects.create(name='Test', padding=3, number_next=41)
        peeked = sequence.get_next_char(sequence.number_next)
        consumed = sequence.next_by_id()
        assert peeked == consumed == '041'

    def test_it_applies_prefix_and_suffix(self):
        sequence = IrSequence.objects.create(
            name='Test', padding=4, number_next=7, prefix='CHK-', suffix='-END')
        assert sequence.get_next_char(sequence.number_next) == 'CHK-0007-END'

    def test_it_pads_without_prefix(self):
        sequence = IrSequence.objects.create(name='Test', padding=5, number_next=1)
        assert sequence.get_next_char(999) == '00999'
