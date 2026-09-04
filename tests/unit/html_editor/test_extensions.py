"""``html_editor`` — las seis extensiones que ``ready()`` cuelga.

Cada archivo de modelo de la fuente con ``_inherit`` publica su
``apply_html_editor_extensions()``. Estos casos comprueban **que el símbolo
aterrizó en la clase ajena** y que hace lo que la fuente hace, que es lo que
un puerto por extensión puede perder en silencio: ``chain_method`` no falla si
nadie lo llama.
"""
import pytest
from addons.base.models import ir_field_converters as converters
from addons.base.models.ir_http import IrHttp
from addons.base.models.ir_model import Base
from addons.base.models.ir_ui_view import MOVABLE_BRANDING
from addons.base.models.ir_template_expressions import IrTemplateExpressions
from django.apps import apps
from lxml import etree, html
from orm.registry import model_by_name

from addons.html_editor.models import ir_attachment as he_attachment
from addons.html_editor.models import ir_http as he_http
from addons.html_editor.models import ir_qweb_fields as he_qweb
from addons.html_editor.models import ir_ui_view as he_view
from addons.html_editor.models import ir_websocket as he_ws
from addons.html_editor.models import models as he_models

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


class TestEveryApplyIsIdempotent:
    """``ready()`` puede correr dos veces (autoreloader) y un test las llama.

    Si una segunda invocación duplicara la cadena, un hook acumulativo
    devolvería entradas repetidas — el defecto que ``chain_method`` documenta
    haber medido con ``_get_available_qr_methods``.
    """

    @pytest.mark.parametrize('module', [
        he_models, he_attachment, he_http, he_qweb, he_view, he_ws])
    def test_calling_it_again_changes_nothing_observable(self, module):
        before = Base._get_view_field_attributes(Base)
        directives = list(IrTemplateExpressions()._directives_eval_order())
        module.apply_html_editor_extensions()
        assert Base._get_view_field_attributes(Base) == before
        assert IrTemplateExpressions()._directives_eval_order() == directives


class TestTheBaseModelPublishesTheTwoSanitizeAttributes:
    def test_both_names_are_in_the_view_field_attributes(self):
        keys = Base._get_view_field_attributes(Base)
        assert 'sanitize' in keys
        assert 'sanitize_tags' in keys


class TestTheAttachmentSpeaksTheEditorLanguage:
    """Las cuatro ``property`` de ``models/ir_attachment.py``."""

    def test_the_four_computed_names_are_properties_on_the_base_class(self):
        A = apps.get_model('base', 'IrAttachment')
        for name in ('local_url', 'image_src', 'image_width', 'image_height'):
            assert isinstance(A.__dict__.get(name), property), name

    def test_local_url_prefers_the_declared_url(self):
        A = apps.get_model('base', 'IrAttachment')
        assert A(url='/x/y.png', name='y.png').local_url == '/x/y.png'

    def test_local_url_falls_back_to_web_image_with_the_checksum(self):
        A = apps.get_model('base', 'IrAttachment')
        attachment = A(name='y.png', checksum='abc123')
        assert attachment.local_url == '/web/image/None?unique=abc123'

    def test_image_src_is_false_for_a_mimetype_the_editor_cannot_paint(self):
        A = apps.get_model('base', 'IrAttachment')
        assert A(name='x.pdf', mimetype='application/pdf').image_src is False

    def test_image_src_accepts_a_mimetype_with_parameters(self):
        # `image/svg+xml; charset=utf-8` es soportado: la fuente parte por ';'
        A = apps.get_model('base', 'IrAttachment')
        attachment = A(name='x.svg', mimetype='image/svg+xml; charset=utf-8',
                       checksum='0123456789abcdef', type='binary')
        assert attachment.image_src.startswith('/web/image/')

    def test_the_original_seam_returns_none_while_the_field_is_blocked(self):
        # Divergencia 1 de `models/ir_attachment.py`: el campo no está
        # instalado, y la costura lo dice sin reventar.
        A = apps.get_model('base', 'IrAttachment')
        assert he_attachment.original_attachment_of(A(name='x')) is None

    def test_the_seam_does_not_seed_the_key_while_the_field_is_blocked(self):
        A = apps.get_model('base', 'IrAttachment')
        values = he_attachment.set_original_attachment({}, A(name='x'))
        assert 'original_id' not in values

    def test_the_bypass_hook_says_no_by_default(self):
        """Es método de INSTANCIA, como en la fuente — no de clase.

        La fuente lo invoca sobre ``request.env['ir.attachment']``, que es un
        recordset vacío (una instancia). El puerto conserva esa firma, así que
        ``controllers/main.py`` lo llama sobre ``IrAttachment()``. El caso lo
        fija: llamarlo sobre la clase levanta ``TypeError``, y eso es lo que
        pasó al escribirlo la primera vez.
        """
        A = apps.get_model('base', 'IrAttachment')
        assert A()._can_bypass_rights_on_media_dialog(name='x') is False
        with pytest.raises(TypeError):
            A._can_bypass_rights_on_media_dialog(name='x')


class TestTheEditorFlagsTravelInTheQueryString:
    def test_the_three_keys_are_the_ones_of_the_source(self):
        assert he_http.CONTEXT_KEYS == [
            'editable', 'edit_translations', 'translatable']

    def test_the_context_is_empty_without_a_request(self):
        assert IrHttp._get_editor_context() == {}

    def test_pre_dispatch_does_not_raise_without_a_request(self):
        assert IrHttp._pre_dispatch(None, {}) is None

    def test_the_prepend_combine_puts_the_own_value_first(self):
        assert he_http._prepend_previous(['a'], ['b']) == ['a', 'b']


class TestTheConvertersLearnedTheWayBack:
    """``base`` porta la ida (``value_to_html``); esto es la vuelta."""

    def test_the_base_converter_gained_from_html_and_value_from_string(self):
        assert callable(converters.IrFieldConverter.from_html)
        assert converters.IrFieldConverter.value_from_string('x') == 'x'

    def test_from_html_reads_the_text_content_of_the_node(self):
        node = html.fromstring('<span>  hola  </span>')
        assert converters.IrFieldConverter.from_html(None, None, node) == 'hola'

    def test_an_empty_node_gives_false_not_the_empty_string(self):
        # La fuente escribe `or False`: un campo sin valor se limpia.
        node = html.fromstring('<span>   </span>')
        assert converters.IrFieldConverter.from_html(None, None, node) is False

    def test_the_text_converter_collapses_block_tags_into_newlines(self):
        node = html.fromstring('<div><p>uno</p><p>dos</p></div>')
        assert converters.IrFieldConverterText.from_html(
            None, None, node) == 'uno\n\ndos'

    def test_br_becomes_a_single_newline(self):
        node = html.fromstring('<div>uno<br/>dos</div>')
        assert converters.IrFieldConverterText.from_html(
            None, None, node) == 'uno\ndos'

    def test_the_html_converter_keeps_the_children_serialized(self):
        node = html.fromstring('<div>texto<b>fuerte</b></div>')
        out = converters.IrFieldConverterHtml.from_html(None, None, node)
        assert 'texto' in out
        assert '<b>fuerte</b>' in out

    def test_the_selection_converter_maps_the_label_back_to_its_key(self):
        field = type('F', (), {'choices': [('A', 'Alfa'), ('B', 'Beta')]})()
        node = html.fromstring('<span>Beta</span>')
        assert converters.IrFieldConverterSelection.from_html(
            None, field, node) == 'B'

    def test_an_unknown_label_raises_instead_of_writing_a_wrong_key(self):
        field = type('F', (), {'choices': [('A', 'Alfa')]})()
        node = html.fromstring('<span>Zeta</span>')
        with pytest.raises(ValueError):
            converters.IrFieldConverterSelection.from_html(None, field, node)

    def test_the_duration_converter_reads_a_non_localised_float(self):
        node = html.fromstring('<span> 2.5 </span>')
        assert converters.IrFieldConverterDuration.from_html(
            None, None, node) == 2.5

    def test_the_image_converter_carries_the_two_class_attributes(self):
        assert converters.IrFieldConverterImage.local_url_re is not None
        assert converters.IrFieldConverterImage.redirect_url_re is not None

    def test_load_remote_url_refuses_a_data_uri(self):
        assert converters.IrFieldConverterImage.load_remote_url(
            'data:image/png;base64,AAAA') is None


class TestTheHtmlToTextHelpers:
    def test_whitespace_runs_collapse_to_one_space(self):
        assert he_qweb._collapse_whitespace('a  \n\t b') == 'a b'

    def test_padding_requests_fold_into_the_largest(self):
        assert list(he_qweb._realize_padding(['a', 1, 2, 'b'])) == [
            'a', '\n\n', 'b']

    def test_the_two_block_sets_are_disjoint(self):
        assert not (he_qweb._PADDED_BLOCK & he_qweb._MISC_BLOCK)


class TestThePosixToLdmlConversion:
    """``posix_to_ldml`` se construyó aquí (divergencia 2 de ese módulo)."""

    def test_the_table_is_the_one_of_the_source(self):
        assert he_qweb.POSIX_TO_LDML['Y'] == 'yyyy'
        assert he_qweb.POSIX_TO_LDML['-d'] == 'd'

    def test_a_plain_date_format_converts_to_its_ldml_pattern(self):
        locale = he_qweb._babel_locale_parse('en_US')
        assert he_qweb._posix_to_ldml('%d/%m/%Y', locale) == 'dd/MM/yyyy'

    def test_letters_outside_a_directive_are_quoted(self):
        locale = he_qweb._babel_locale_parse('en_US')
        assert he_qweb._posix_to_ldml('%Y a', locale) == "yyyy 'a'"

    def test_an_unknown_locale_falls_back_instead_of_raising(self):
        assert he_qweb._babel_locale_parse('no-existe-xx') is not None


class TestTheViewLearnedToSaveWhatWasEdited:
    def test_save_from_html_is_installed_and_django_save_survives(self):
        View = model_by_name('ir.ui.view')
        assert callable(View.save_from_html)
        # La divergencia 2 de `models/ir_ui_view.py`: los dos coexisten.
        assert View.save_from_html is not View.save

    def test_the_editing_attributes_include_the_movable_branding(self):
        for attr in MOVABLE_BRANDING:
            assert attr in he_view.EDITING_ATTRIBUTES
        assert 'data-oe-type' in he_view.EDITING_ATTRIBUTES

    def test_cleaning_drops_the_editing_attributes_and_the_editable_class(self):
        View = model_by_name('ir.ui.view')
        cleaned = View._get_cleaned_non_editing_attributes(
            View(), [('data-oe-type', 'char'), ('class', 'a o_editable b'),
                     ('contenteditable', 'true'), ('id', 'keep')])
        assert cleaned == {'class': 'a b', 'id': 'keep'}

    def test_two_archs_with_the_attributes_in_another_order_are_equal(self):
        View = model_by_name('ir.ui.view')
        a = etree.fromstring('<div a="1" b="2"><p>x</p></div>')
        b = etree.fromstring('<div b="2" a="1"><p>x</p></div>')
        assert View._are_archs_equal(View(), a, b) is True

    def test_a_different_text_makes_them_unequal(self):
        View = model_by_name('ir.ui.view')
        a = etree.fromstring('<div><p>x</p></div>')
        b = etree.fromstring('<div><p>y</p></div>')
        assert View._are_archs_equal(View(), a, b) is False

    def test_the_available_name_grows_a_counter_only_when_taken(self):
        View = model_by_name('ir.ui.view')
        assert View._find_available_name(View(), 'Bloque', set()) == 'Bloque'
        assert View._find_available_name(
            View(), 'Bloque', {'Bloque'}) == 'Bloque (2)'
        assert View._find_available_name(
            View(), 'Bloque', {'Bloque', 'Bloque (2)'}) == 'Bloque (3)'

    def test_to_field_ref_drops_the_branding_and_restores_the_t_field(self):
        View = model_by_name('ir.ui.view')
        el = html.fromstring(
            '<span data-oe-model="res.partner" data-oe-id="1" '
            'data-oe-expression="o.name" class="k">Ana</span>')
        out = View.to_field_ref(View(), el)
        assert out.get('t-field') == 'o.name'
        assert out.get('class') == 'k'
        assert not [k for k in out.attrib if k.startswith('data-oe-')]

    def test_the_blocked_translation_copy_names_its_successor(self):
        View = model_by_name('ir.ui.view')
        with pytest.raises(NotImplementedError) as excinfo:
            View._copy_field_terms_translations(View(), None, 'a', None, 'b')
        assert 'get_translation_dictionary' in str(excinfo.value)

    def test_the_xpath_hasclass_helper_compiles_the_reference_predicate(self):
        assert he_view._hasclass('oe_structure') == (
            "contains(concat(' ', normalize-space(@class), ' '), "
            "' oe_structure ')")


class TestTheConverterChainCombinesInsteadOfReplacing:
    """``attributes`` de un conversor derivado FUNDE lo del eslabon base.

    La fuente abre cada uno de los ocho con
    ``attrs = super().attributes(...)`` — el derivado anade a lo que la clase
    base ya puso. Aqui el idioma de extension es ``chain_method``, cuyo relevo
    por defecto sólo invoca al eslabon previo si el nuevo devolvio ``None``; y
    un diccionario vacio **no** es ``None``. Sin ``combine=merge_dict`` lo que
    aporta la base se descarta en silencio, y ningun gate estatico lo ve.

    El control esta medido con la guarda anulada
    (``scripts/evidence/control_303_combine_merge.py``): con ``combine=`` la
    llamada devuelve ``['placeholder']``; sin el, ``[]``.
    """

    @pytest.fixture
    def partner(self):
        Partner = apps.get_model('base', 'ResPartner')
        return Partner(name='cadena de conversores')

    def test_the_derived_converter_keeps_what_the_base_link_contributes(
            self, partner):
        """El ``placeholder`` lo pone el eslabon base; el derivado no lo toca.

        Es lo que cae al retirar ``combine=``: el derivado empieza con
        ``attrs = {}`` y su diccionario vacio gana al del eslabon previo.
        """
        attrs = converters.IrFieldConverterMany2one.attributes(
            partner, 'parent', {'placeholder': 'nombre del padre'}, None)
        assert attrs['placeholder'] == 'nombre del padre'

    def test_the_derived_converter_still_contributes_its_own(self, partner):
        """El control que separa «funde» de «sólo corre la base».

        Sin este caso, un ``combine`` que descartara al eslabon nuevo pasaria
        el de arriba sin distinguirse.
        """
        attrs = converters.IrFieldConverterMany2one.attributes(
            partner, 'parent',
            {'placeholder': 'nombre del padre', 'inherit_branding': True,
             'null_text': 'sin padre'},
            None)
        assert attrs['placeholder'] == 'nombre del padre'
        assert attrs['data-oe-many2one-allowreset'] == 1
        assert 'data-oe-many2one-domain' in attrs

    def test_a_converter_without_a_previous_link_is_unaffected(self, partner):
        """El eslabon base no tiene previo: su ``combine=`` no cambia nada.

        ``IrFieldConverter.attributes`` es el PRIMER eslabon —``base`` no
        declara ``attributes``— asi que aqui ``combine=merge_dict`` no puede
        fundir con nada. El caso fija que eso no lo rompe.
        """
        attrs = converters.IrFieldConverter.attributes(
            partner, 'parent', {'placeholder': 'nombre del padre'}, None)
        assert attrs == {'placeholder': 'nombre del padre'}
