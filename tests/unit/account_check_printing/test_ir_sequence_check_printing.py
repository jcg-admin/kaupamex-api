"""Contrato de ``get_next_char`` — ≙ Odoo ``ir.sequence.get_next_char``,
colgado por ``account_check_printing`` sobre ``base.IrSequence`` (ver
``models/ir_sequence.py``).
"""
import pytest

from addons.account_check_printing.models.ir_sequence import (
    apply_account_check_printing_ir_sequence_extensions,
)
from addons.base.models import IrSequence

apply_account_check_printing_ir_sequence_extensions()

pytestmark = pytest.mark.django_db


class TestGetNextChar:
    def test_peek_does_not_consume(self):
        sequence = IrSequence.objects.create(name='Test', padding=5, number_next=1)
        first_peek = sequence.get_next_char(sequence.number_next)
        second_peek = sequence.get_next_char(sequence.number_next)
        assert first_peek == second_peek == '00001'
        sequence.refresh_from_db()
        assert sequence.number_next == 1

    def test_matches_the_format_get_next_would_produce(self):
        sequence = IrSequence.objects.create(name='Test', padding=3, number_next=41)
        peeked = sequence.get_next_char(sequence.number_next)
        consumed = sequence.get_next()
        assert peeked == consumed == '041'

    def test_with_prefix_and_suffix(self):
        sequence = IrSequence.objects.create(
            name='Test', padding=4, number_next=7, prefix='CHK-', suffix='-END')
        assert sequence.get_next_char(sequence.number_next) == 'CHK-0007-END'

    def test_formats_an_arbitrary_number_not_the_current_one(self):
        sequence = IrSequence.objects.create(name='Test', padding=5, number_next=1)
        assert sequence.get_next_char(999) == '00999'
