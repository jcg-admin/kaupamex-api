"""El mecanismo de secuencia editable (#140, :ref:`h-api-339`).

Espeja ``odoo19c: account/tests/test_sequence_mixin.py`` en lo que aplica al
porte. Lo que se fija aquí es el **contrato del mecanismo**, no el de
``AccountMove``: deducir la periodicidad de un nombre, partirlo en sus dos
mitades consultables, y responder cuál es el último de la serie.

La razón de ser de las dos columnas está en :ref:`h-api-339`: ordenar por
``name`` es un orden de cadena que se rompe a los 100 000 documentos.
"""
import pytest

from addons.account.models.sequence_mixin import SequenceMixin
from exceptions import ValidationError

pytestmark = [pytest.mark.unit]


class TestDeduceSequenceNumberReset:
    """La periodicidad se deduce del nombre anterior, no de una configuración."""

    @pytest.mark.parametrize('name,expected', [
        ('INV/2026/00042', 'year'),
        ('INV/2026/01/00042', 'month'),
        ('INV/26/00042', 'year'),
        ('FACT-00042', 'never'),
        ('00042', 'never'),
    ])
    def test_deduces_the_periodicity(self, name, expected):
        assert SequenceMixin.deduce_sequence_number_reset(name) == expected

    def test_a_year_range_needs_consecutive_years(self):
        """``2026/2027`` es un rango; ``2026/2030`` no lo es.

        Sin este guard, cualquier par de años se leería como rango y la
        periodicidad deducida sería falsa.
        """
        assert SequenceMixin.deduce_sequence_number_reset('INV/2026/2027/00042') == 'year_range'
        assert SequenceMixin.deduce_sequence_number_reset('INV/2026/2030/00042') != 'year_range'

    def test_a_name_without_digits_is_never(self):
        """Un nombre sin dígitos NO es un error: es periodicidad ``never``.

        El patrón fijo acepta cero dígitos (``\\d{0,9}``), así que siempre
        casa. Es deliberado en la referencia: una serie puede no llevar número
        todavía —un borrador con ``'/'``— y eso no debe romper la deducción.

        Este test se escribió primero afirmando ``ValidationError`` porque era
        lo que yo esperaba; la referencia dice otra cosa y manda ella.
        """
        assert SequenceMixin.deduce_sequence_number_reset('SIN-NUMERO/') == 'never'
        assert SequenceMixin.deduce_sequence_number_reset('') == 'never'

    def test_a_pattern_without_the_seq_group_is_rejected(self):
        """El ValidationError protege a la SUBCLASE, no al nombre.

        Salta cuando alguien redefine los patrones sin el grupo ``seq``: sin
        él no hay número que incrementar y la serie no se puede continuar.
        """
        class BadlyConfigured(SequenceMixin):
            sequence_year_range_monthly_regex = r'^nada$'
            sequence_year_range_regex = r'^nada$'
            sequence_monthly_regex = r'^nada$'
            sequence_yearly_regex = r'^nada$'
            sequence_fixed_regex = r'^nada$'

            class Meta:
                abstract = True

        with pytest.raises(ValidationError):
            BadlyConfigured.deduce_sequence_number_reset('INV/2026/00042')


class TestNonCapturing:
    def test_named_groups_become_non_capturing(self):
        assert SequenceMixin._non_capturing(r'^(?P<prefix1>.*?)(?P<seq>\d*)$') == r'^(?:.*?)(?:\d*)$'
