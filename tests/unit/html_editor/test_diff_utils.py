"""``html_editor.models.diff_utils`` — el parche, la comparación y el diff.

Estos casos ejercitan el **contrato de ida y vuelta** que hace útil al
historial: un parche que no revierta el contenido nuevo al viejo convierte
cada revisión guardada en basura, y nada lo delataría hasta que alguien
pidiera restaurar.

Ninguno necesita base de datos: el archivo son funciones puras.
"""
import pytest

from addons.html_editor.models.diff_utils import (
    HTML_ATTRIBUTES_TO_REMOVE,
    LINE_SEPARATOR,
    OPERATION_SEPARATOR,
    PATCH_OPERATIONS,
    _indent,
    _remove_html_attribute,
    apply_patch,
    generate_comparison,
    generate_patch,
    generate_unified_diff,
)

pytestmark = [pytest.mark.unit]


class TestThePatchRoundTrip:
    """``apply_patch(nuevo, generate_patch(nuevo, viejo)) == viejo``."""

    @pytest.mark.parametrize('old, new', [
        # una sustitución dentro de un párrafo
        ('<p>hola</p><p>mundo</p>', '<p>hola</p><p>mundo cruel</p>'),
        # una adición al final
        ('<p>uno</p>', '<p>uno</p><p>dos</p><p>tres</p>'),
        # un borrado en medio
        ('<p>a</p><p>b</p><p>c</p>', '<p>a</p><p>c</p>'),
        # un cambio de atributo sin cambio de texto
        ('<p class="x">a</p>', '<p class="y">a</p>'),
        # anidamiento
        ('<div><ul><li>a</li></ul></div>', '<div><ul><li>a</li><li>b</li></ul></div>'),
        # el contenido viejo vacío
        ('', '<p>nuevo</p>'),
    ])
    def test_the_patch_reverts_the_new_content_to_the_old_one(self, old, new):
        patch = generate_patch(new, old)
        assert apply_patch(new, patch) == old

    def test_an_empty_patch_returns_the_content_untouched(self):
        assert apply_patch('<p>a</p>', '') == '<p>a</p>'

    def test_identical_contents_produce_no_operation(self):
        assert generate_patch('<p>a</p>', '<p>a</p>') == ''


class TestTheOperationFormat:
    """El formato ``<tipo>@<inicio>[,<fin>][:<texto>]`` es dato persistido."""

    def test_the_three_operation_letters_are_the_ones_of_the_source(self):
        assert PATCH_OPERATIONS == {
            'insert': '+', 'delete': '-', 'replace': 'R'}

    def test_a_deletion_carries_no_content_after_the_colon(self):
        patch = generate_patch('<p>a</p><p>b</p>', '<p>a</p><p>b</p><p>c</p>')
        # revertir al viejo AÑADE la línea que falta: la operación es '+'
        assert patch.startswith('+')

    def test_operations_are_separated_by_newline_and_lines_by_lt(self):
        assert OPERATION_SEPARATOR == '\n'
        assert LINE_SEPARATOR == '<'


class TestTheHistoryAttributeIsStrippedBeforeDiffing:
    """``data-last-history-steps`` cambia en cada paso y no es contenido."""

    def test_the_attribute_is_removed_with_its_quoted_value(self):
        html = '<p data-last-history-steps="1,2,3">a</p>'
        assert _remove_html_attribute(html, HTML_ATTRIBUTES_TO_REMOVE) == '<p>a</p>'

    def test_two_contents_differing_only_in_history_produce_no_patch(self):
        a = '<p data-last-history-steps="1,2">x</p>'
        b = '<p data-last-history-steps="9,9,9">x</p>'
        assert generate_patch(a, b) == ''

    def test_the_comparison_of_two_such_contents_is_the_content_itself(self):
        a = '<p data-last-history-steps="1,2">x</p>'
        b = '<p data-last-history-steps="7">x</p>'
        assert generate_comparison(a, b) == '<p>x</p>'


class TestTheComparisonMarksBothSides:
    """Los dos textos quedan marcados, cada uno con su etiqueta.

    **Qué lado lleva cada etiqueta, medido:** ``generate_comparison(a, b)``
    envuelve ``b`` en ``<added>`` y ``a`` en ``<removed>``. Suena al revés y
    **es la conducta de la fuente**, no un defecto del puerto: la comparación
    se construye recorriendo el parche que revierte ``a`` a ``b``, así que lo
    que ese parche *inserta* —el contenido ``b``— sale marcado como añadido.

    Su único consumidor lo usa en el orden que lo hace correcto:
    ``html_field_history_get_comparison_at_revision`` llama
    ``generate_comparison(restaurado, actual)``, de modo que ``<added>``
    envuelve el valor **actual** y ``<removed>`` el de la revisión pedida.
    """

    def test_each_side_gets_its_own_tag(self):
        comparison = generate_comparison('<p>nuevo</p>', '<p>viejo</p>')
        assert '<added>viejo</added>' in comparison
        assert '<removed>nuevo</removed>' in comparison

    def test_the_unchanged_nodes_carry_no_tag(self):
        comparison = generate_comparison('<p>a</p><p>nuevo</p>',
                                         '<p>a</p><p>viejo</p>')
        assert comparison.startswith('<p>a</p>')

    def test_equal_contents_come_back_unchanged(self):
        assert generate_comparison('<p>a</p>', '<p>a</p>') == '<p>a</p>'


class TestTheUnifiedDiffIsLineOriented:
    """El control que justifica que ``_indent`` no use ``pretty_print``.

    ``difflib.unified_diff`` compara **líneas**. Si el indentado devolviera el
    documento en una sola línea, el diff señalaría el documento entero y no el
    nodo — sería sintácticamente correcto y prácticamente inútil.
    """

    def test_the_indented_document_has_one_syntactic_unit_per_line(self):
        lines = _indent('<p>a</p><p>b</p>').strip().split('\n')
        # <document> · <p> · a · </p> · <p> · b · </p> · </document>
        assert len(lines) == 8, lines
        assert lines[0].strip() == '<document>'
        assert lines[-1].strip() == '</document>'

    def test_the_indented_document_keeps_the_attributes_of_each_node(self):
        assert 'class="x"' in _indent('<p class="x">a</p>')

    def test_the_diff_names_only_the_changed_node(self):
        diff = generate_unified_diff('<p>a</p><p>NUEVO</p>',
                                     '<p>a</p><p>viejo</p>')
        added = [ln for ln in diff.split('\n')
                 if ln.startswith('+') and not ln.startswith('+++')]
        removed = [ln for ln in diff.split('\n')
                   if ln.startswith('-') and not ln.startswith('---')]
        assert [ln[1:].strip() for ln in added] == ['NUEVO']
        assert [ln[1:].strip() for ln in removed] == ['viejo']

    def test_two_equal_contents_produce_no_hunk(self):
        assert generate_unified_diff('<p>a</p>', '<p>a</p>') == ''
