"""Inferencia de formato de fecha/hora — ``addons.base_import``.

Ejercita la equivalencia con ``odoo19c: base_import/models/base_import.py``
en lo que el porte cubre: el catálogo generado, el compilador de patrón a
regex, y la regla de "todos o ninguno" de ``check_patterns``.

Sin base de datos a propósito: los tres símbolos son Python puro y no tocan
el ORM. Un test que exigiera ``django_db`` mediría el arranque, no la
heurística.
"""
import datetime

from addons.base_import.models.date_patterns import (
    DATE_FORMATS,
    DATE_PATTERNS,
    TIME_PATTERNS,
    check_patterns,
    to_re,
)


def test_catalog_has_the_reference_cardinality():
    """4 órdenes × 2 variantes de año = 8 formatos; × 5 separadores = 40."""
    assert len(DATE_FORMATS) == 8
    assert len(DATE_PATTERNS) == 40
    assert len(TIME_PATTERNS) == 6


def test_short_year_variant_is_generated_for_every_order():
    """Cada orden aporta su versión ``%Y`` y su versión ``%y``."""
    largos = [f for f in DATE_FORMATS if '%Y' in f]
    cortos = [f for f in DATE_FORMATS if '%y' in f]
    assert len(largos) == 4
    assert len(cortos) == 4


def test_compact_format_without_separator_is_included():
    """La cadena vacía de ``_SEPARATORS`` produce el formato compacto."""
    assert '%Y%m%d' in DATE_PATTERNS


def test_day_above_twelve_disambiguates_the_order():
    """Un 31 en primera posición sólo lo explica el orden día-mes-año."""
    assert check_patterns(DATE_PATTERNS, ['31/12/2026', '01/01/2026']) == '%d/%m/%Y'


def test_first_matching_pattern_wins_when_ambiguous():
    """Con un valor ambiguo gana el primero del catálogo, no un azar.

    Fija el orden como parte del contrato: la referencia declara
    ``('%m', '%d', '%Y')`` primero, así que ``12/07/2026`` se lee como 7 de
    diciembre mientras nada lo contradiga.
    """
    assert check_patterns(DATE_PATTERNS, ['12/07/2026']) == '%m/%d/%Y'


def test_one_contradicting_value_discards_the_pattern():
    """La regla es todos o ninguno: basta un valor que no case."""
    assert check_patterns(DATE_PATTERNS, ['31/12/2026', 'no soy fecha']) is None


def test_date_objects_and_blanks_do_not_veto_a_pattern():
    """Una celda ya tipada o vacía no dice nada sobre el formato del resto."""
    valores = [datetime.date(2026, 12, 31), '', '01/01/2026']
    assert check_patterns(DATE_PATTERNS, valores) == '%m/%d/%Y'


def test_impossible_component_is_rejected_by_the_range():
    """Un componente fuera de rango descarta el patrón — pero hay que
    descartarlos TODOS.

    ``32`` no es día en ningún orden, así que la primera línea es limpia. La
    segunda documenta la trampa: ``2026-13-01`` **sí** tiene explicación,
    ``%Y-%d-%m`` (día 13, mes 01), porque el catálogo de la referencia incluye
    el orden año-día-mes. Sólo un valor que ningún orden explique —aquí un 13
    en la posición de mes bajo las dos lecturas— devuelve ``None``.
    """
    assert check_patterns(DATE_PATTERNS, ['32/01/2026']) is None
    assert check_patterns(DATE_PATTERNS, ['2026-13-01']) == '%Y-%d-%m'
    assert check_patterns(DATE_PATTERNS, ['2026-13-13']) is None


def test_separator_dot_is_escaped_not_treated_as_wildcard():
    """``.`` en el patrón es un punto literal — si no, casaría cualquier cosa."""
    p = to_re('%d.%m.%Y')
    assert p.match('31.12.2026')
    assert not p.match('31x12x2026')


def test_pattern_is_anchored_at_both_ends():
    """Explicar el principio del valor no es explicar el valor."""
    p = to_re('%d/%m/%Y')
    assert not p.match('31/12/2026 y algo más')


def test_whitespace_is_tolerant():
    """El espacio del patrón admite espaciado irregular del archivo."""
    p = to_re('%d %m %Y')
    assert p.match('31  12   2026')


def test_twelve_hour_clock_needs_the_meridiem():
    """``%p`` es parte del patrón de 12 h; sin él, no casa."""
    assert check_patterns(TIME_PATTERNS, ['11:30 PM']) == '%I:%M %p'
    assert check_patterns(TIME_PATTERNS, ['23:30']) == '%H:%M'
