r"""Sonda: las 20 directivas ``t-*``, ¿qué mecanismo nativo hace cada una?

Directiva del ejecutor 2026-08-29: *"si es que no, entonces analiza los
binarios de nuestro stack, genera los documentos de pruebas, y documenta"*.

El análisis :doc:`docs: analisis-construir-lo-que-qweb-hace-con-nuestro-stack`
publicó una tabla que reparte las 20 directivas entre DTL, ``lxml`` y política
del ORM. **Esa tabla era prosa**: afirmaba que el stack «lo trae hecho» sin
ejercer ninguno de los mecanismos. Esta sonda la mide, uno por uno, contra los
binarios instalados.

La lista de directivas **no se teclea**: sale de
``IrTemplateExpressions._directives_eval_order()``, así que si la fuente gana
una, este archivo la ve faltar en vez de quedarse callado.

*Métrica:* la conducta observada de ``django.template`` 6.0.5 y de ``lxml``
sobre el mismo material, más la presencia del símbolo en el registro de tags
y filtros instalado.
*Ciega a:* si el mecanismo nativo cubre **todos** los casos de borde de su
directiva — mide que existe y que hace lo que la tabla dice, no que sea
equivalente al último detalle. Y ciega al coste por render.
"""
import pytest
from django.template import Context, Engine
from django.template import defaultfilters, defaulttags, loader_tags
from django.test import override_settings
from django.utils import formats, timesince, translation
from lxml import etree

from addons.authz.permissions import HasCapability
from addons.base.models.ir_template_expressions import IrTemplateExpressions
from addons.base.models.ir_ui_view import IrUiView

DTL = Engine(autoescape=False)
DTL_ESCAPING = Engine(autoescape=True)


def render(source, context, engine=DTL, autoescape=False):
    return engine.from_string(source).render(Context(context, autoescape=autoescape))


#: El reparto que el análisis declara. La clave es la directiva tal como la
#: nombra ``_directives_eval_order``; el valor, la familia de mecanismo.
MECHANISM_BY_DIRECTIVE = {
    'if': 'dtl', 'elif': 'dtl', 'else': 'dtl',
    'foreach': 'dtl', 'as': 'dtl',
    'esc': 'dtl', 'raw': 'dtl', 'out': 'dtl',
    'set': 'dtl',
    'call': 'dtl', 'call-assets': 'dtl',
    'field': 'converters',
    'att': 'lxml', 'tag-open': 'lxml', 'tag-close': 'lxml', 'inner-content': 'lxml',
    'lang': 'orm-policy',
    'groups': 'orm-policy',
    'options': 'orm-policy', 'debug': 'orm-policy',
}


class TestTheListItselfIsNotTyped:
    """El control que impide que esta sonda envejezca en silencio."""

    def test_every_directive_of_the_engine_has_a_declared_mechanism(self):
        declared = set(IrTemplateExpressions()._directives_eval_order())
        assert declared == set(MECHANISM_BY_DIRECTIVE), (
            'la lista del motor y el reparto de esta sonda divergieron: '
            f'sólo en el motor {sorted(declared - set(MECHANISM_BY_DIRECTIVE))}, '
            f'sólo aquí {sorted(set(MECHANISM_BY_DIRECTIVE) - declared)}')

    def test_there_are_twenty_of_them(self):
        assert len(IrTemplateExpressions()._directives_eval_order()) == 20


class TestTheElevenThatDjangoBringsDone:
    """DTL las trae hechas: el símbolo está en el registro instalado."""

    @pytest.mark.parametrize('tag', ['if', 'for', 'with', 'autoescape', 'filter'])
    def test_the_tag_is_registered_in_the_installed_django(self, tag):
        assert tag in defaulttags.register.tags

    def test_include_lives_in_loader_tags_not_in_defaulttags(self):
        # La distinción importa: `call` se construye con `{% include %}`, y ese
        # no viene del mismo módulo que los demás.
        assert 'include' in loader_tags.register.tags
        assert 'include' not in defaulttags.register.tags

    def test_if_elif_else_are_one_tag_with_three_branches(self):
        # QWeb las cuenta como tres directivas porque son tres atributos; DTL
        # las resuelve con un solo tag. Por eso `elif`/`else` no aparecen en el
        # registro y su ausencia NO es un hueco.
        assert render('{% if n > 2 %}alto{% elif n > 0 %}bajo{% else %}cero{% endif %}',
                      {'n': 1}) == 'bajo'
        assert 'elif' not in defaulttags.register.tags

    def test_foreach_and_as_are_the_for_tag_with_its_loop_variable(self):
        assert render('{% for row in rows %}{{ row }}{% endfor %}',
                      {'rows': [1, 2, 3]}) == '123'

    @pytest.mark.parametrize('expr,expected', [
        ('{{ forloop.counter }}', '123'),
        ('{{ forloop.counter0 }}', '012'),
        ('{{ forloop.first }}', 'TrueFalseFalse'),
        ('{{ forloop.last }}', 'FalseFalseTrue'),
        ('{{ forloop.revcounter }}', '321'),
    ])
    def test_the_loop_exposes_index_and_position_like_the_directive_does(self, expr, expected):
        # `t-foreach` expone `_index`, `_first`, `_last`, `_size`; el `forloop`
        # de DTL expone lo mismo con otros nombres.
        assert render('{%% for row in rows %%}%s{%% endfor %%}' % expr,
                      {'rows': ['a', 'b', 'c']}) == expected

    def test_parity_needs_a_filter_because_the_loop_does_not_expose_it(self):
        # El hueco honesto: `_odd`/`_even` de la directiva NO tienen atributo
        # equivalente en `forloop`. Se construyen con el filtro `divisibleby`,
        # que sí está instalado.
        assert 'divisibleby' in defaultfilters.register.filters
        assert render(
            '{% for row in rows %}'
            '{% if forloop.counter0|divisibleby:2 %}par{% else %}impar{% endif %}'
            '{% endfor %}', {'rows': ['a', 'b', 'c']}) == 'parimparpar'

    def test_esc_and_raw_are_the_two_sides_of_autoescape(self):
        # `t-esc` escapa y `t-raw` no. En DTL es la misma distinción, y opera
        # en dos niveles: el motor y el filtro.
        assert render('{{ v }}', {'v': 'a & b'}, DTL_ESCAPING, autoescape=True) == 'a &amp; b'
        assert render('{{ v }}', {'v': 'a & b'}) == 'a & b'
        assert render('{{ v|safe }}', {'v': 'a & b'}, DTL_ESCAPING, autoescape=True) == 'a & b'

    def test_out_is_esc_with_a_fallback_and_the_fallback_is_a_filter(self):
        # `t-out` emite el valor y, si es falso, el contenido del nodo. El
        # filtro `default` es exactamente eso.
        assert render('{{ v|default:"vacio" }}', {'v': ''}) == 'vacio'
        assert render('{{ v|default:"vacio" }}', {'v': 'x'}) == 'x'

    def test_set_is_the_with_tag(self):
        assert render('{% with total=a %}{{ total }}{% endwith %}', {'a': 7}) == '7'

    def test_call_is_include_and_it_needs_a_loader(self):
        # El caveat medido: `{% include %}` resuelve por nombre contra un
        # loader, así que el descriptor tendría que declarar uno. No es un
        # hueco del stack: es una precondición del mecanismo.
        engine = Engine(autoescape=False, loaders=[
            ('django.template.loaders.locmem.Loader', {'trozo.txt': 'HOLA'})])
        assert engine.from_string('{% include "trozo.txt" %}').render(Context({})) == 'HOLA'


class TestTheFourThatLxmlBringsDone:
    """Construir el nodo pieza a pieza es la API nativa de ``lxml``."""

    def test_tag_open_and_tag_close_are_one_element(self):
        node = etree.Element('linea')
        assert etree.tostring(node) == b'<linea/>'

    def test_att_is_set(self):
        node = etree.Element('linea')
        node.set('importe', '21.00')
        assert etree.tostring(node) == b'<linea importe="21.00"/>'

    def test_inner_content_is_text_and_subelements(self):
        node = etree.Element('doc')
        node.text = 'antes'
        etree.SubElement(node, 'linea').text = 'dentro'
        assert etree.tostring(node) == b'<doc>antes<linea>dentro</linea></doc>'

    def test_lxml_escapes_on_serialisation_so_esc_is_free_in_this_path(self):
        # Por eso la tabla dice que para XML el escapado «lo da lxml al
        # serializar»: no hay que elegir entre `t-esc` y `t-raw`.
        node = etree.Element('v')
        node.text = 'a & b'
        assert etree.tostring(node) == b'<v>a &amp; b</v>'


class TestTheFourThatAreOrmPolicyNotTemplateSyntax:
    """No las trae el motor de plantillas, y no debería traerlas."""

    def test_lang_is_the_translation_override_of_django(self):
        assert hasattr(translation, 'override')
        with translation.override('es'):
            assert translation.get_language() == 'es'
        # Y su catálogo es la tarea #185: `override` cambia el idioma activo,
        # no garantiza que haya traducciones que servir.

    def test_groups_is_the_capability_model_not_a_template_attribute(self):
        assert hasattr(HasCapability, 'has_permission')

    def test_options_and_debug_are_context_of_the_render_not_syntax(self):
        """El homónimo de DTL existe y NO es la misma directiva.

        Medido, no supuesto: la primera versión de este caso afirmaba que
        ``{% debug %}`` vuelca el contexto, y salió **cadena vacía**. El
        binario instalado lo explica —``DebugNode.render`` abre con
        ``if not settings.DEBUG: return ""``—, así que su salida depende de un
        ajuste global y no del nodo.

        ``t-debug`` de la fuente hace otra cosa: abre un depurador
        interactivo. Ninguna de las dos produce contenido del documento, que
        es lo que la tabla afirma: son contexto del render, no sintaxis.
        """
        assert 'debug' in defaulttags.register.tags
        assert render('{% debug %}', {}) == ''       # con DEBUG apagado
        with override_settings(DEBUG=True):
            assert render('{% debug %}', {'a': 1}) != ''
        # `t-options` no tiene homónimo: pasa opciones al conversor de campo,
        # que es la pieza 4 y no el motor.


class TestTheOneThatIsNotOfTheEngine:
    """``field`` es la pieza 4, y su sustrato también está instalado."""

    @pytest.mark.parametrize('symbol', ['date_format', 'time_format',
                                        'number_format', 'localize', 'get_format'])
    def test_django_brings_the_locale_formatting(self, symbol):
        assert hasattr(formats, symbol)

    def test_django_brings_the_relative_converter(self):
        assert hasattr(timesince, 'timesince')
        assert hasattr(timesince, 'timeuntil')

    def test_the_selection_label_comes_from_the_orm_not_from_a_converter(self):
        assert IrUiView(type='qweb').get_type_display() == 'QWeb'
