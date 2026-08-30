r"""``report_type`` ofrece lo que este árbol sabe emitir, y sus tres referentes coinciden.

Directiva del ejecutor 2026-08-30: cerrar las piezas que quedan del desmontaje
de QWeb con el mismo criterio de las dos categorías —*el stack lo trae hecho*
frente a *el stack tiene con qué construirlo*—. Pieza 7 de 8.

:ref:`h-api-931` midió que el campo tenía **tres referentes discordantes**: la
constante ofrecía un valor, el docstring del módulo decía dos y el ``help_text``
del campo decía tres. El desenlace elegido es el tercero de los que aquel
hallazgo enumeraba —**se queda sólo** ``pdf``— y su motivo no es de conteo:
:ref:`h-api-935` mide que los dos renderizadores portados **devuelven un dict**
en este árbol, no el texto ni el marcado que su nombre promete.

*Métrica:* el enum declarado, la prosa de los dos referentes, y el tipo que
``_render_template`` devuelve.
*Ciega a:* si un consumidor externo espera alguno de los dos formatos por
contrato HTTP — eso lo mide la superficie del endpoint, no este archivo.
"""
import inspect

import pytest

from addons.base import report_template
from addons.base.models import ir_actions_report as mod
from addons.base.models.ir_actions_report import (
    REPORT_TYPE_CHOICES,
    REPORT_TYPE_PDF,
    IrActionsReport,
)


class TestTheThreeReferentsAgree:
    """El defecto que :ref:`h-api-931` registró: tres declaraciones, tres cifras."""

    def test_the_enum_offers_exactly_one_format(self):
        assert [v for v, _ in REPORT_TYPE_CHOICES] == [REPORT_TYPE_PDF] == ['pdf']

    def test_the_module_docstring_does_not_promise_a_second_format(self):
        # El docstring decía «sus valores son ``pdf`` / ``text``». Es el
        # referente que más lejos llega: quien lee el módulo entero se queda
        # con esa frase y no baja hasta la constante.
        assert 'pdf`` / ``text' not in mod.__doc__

    def test_the_field_help_does_not_promise_the_three_of_the_source(self):
        # El ``help_text`` decía «Los tres de la fuente», que es lo que la
        # referencia ofrece —``qweb-html``/``qweb-pdf``/``qweb-text``— y no lo
        # que este campo acepta. Es el referente que ve el usuario final.
        #
        # La aserción NO es «la palabra tres no aparece»: la versión corregida
        # la usa para **explicar la divergencia** («la fuente, que ofrece
        # tres»), que es justo lo que se quiere que diga. Un emparejador de la
        # palabra suelta mediría el significante y marcaría en rojo la
        # redacción correcta — el sub-patrón A de
        # ``metrica-decide-la-conclusion.md``. Lo que se mide es la frase que
        # atribuía los tres valores a **este** campo.
        help_text = IrActionsReport._meta.get_field('report_type').help_text
        assert 'los tres de la fuente' not in help_text.lower()
        assert 'pdf' in help_text.lower()

    def test_and_the_help_names_the_reason_not_just_the_value(self):
        # Un help que dijera sólo «PDF» dejaría la reducción sin motivo, y el
        # siguiente que lea el campo volvería a preguntar por qué son tres allá
        # y uno aquí. Es la exigencia de `porte-completo-no-parcial`: el
        # símbolo que no se porta declara su desenlace donde se lee.
        help_text = IrActionsReport._meta.get_field('report_type').help_text.lower()
        assert 'descriptor' in help_text or 'divergencia' in help_text


class TestWhyTheOtherTwoAreNotOffered:
    """El motivo NO es «faltan declarantes»: es que su cuerpo no cumple aquí."""

    def test_the_two_renderers_are_ported_because_the_file_is_ported_whole(self):
        for ported in ('_render_qweb_html', '_render_qweb_text'):
            assert hasattr(IrActionsReport, ported), ported

    def test_but_their_body_returns_the_intermediate_of_the_descriptor(self):
        # Los dos cuerpos son el de la fuente, verbatim: componen y devuelven
        # ``_render_template(...)``. Allá eso es la representación HTML; aquí
        # ``_render_template`` devuelve ``{'bodies': …, 'html_ids': …}`` —el
        # intermedio que el helper de libharu consume—, así que el par que
        # sale de estos dos métodos lleva un **dict** donde su nombre promete
        # texto o marcado.
        for ported in ('_render_qweb_html', '_render_qweb_text'):
            body = inspect.getsource(getattr(IrActionsReport, ported))
            assert '_render_template(' in body, ported

        source = inspect.getsource(IrActionsReport._render_template)
        assert "return {'bodies': bodies, 'html_ids': html_ids}" in source

    def test_the_stack_would_have_to_build_the_two_serializers(self):
        # El criterio de las dos categorías, aplicado: ninguno de los dos es
        # TRAE. Lo que falta no es un símbolo instalado sino el recorrido que
        # aplana el descriptor a líneas (``text``) o a marcado (``html``) —el
        # mismo trabajo que ``tools/pdf`` ya hace para el papel. CONSTRUYE.
        #
        # El control que lo mide: no existe ningún serializador del descriptor
        # fuera del camino del PDF.
        exported = {n for n in dir(report_template) if not n.startswith('__')}
        assert 'interpret_descriptor' in exported
        assert not {n for n in exported if 'to_text' in n or 'to_html' in n}


@pytest.mark.django_db
class TestTheDispatchStaysAtOneFormat:
    """La derivación de la fuente sigue viva; lo que se acota es el enum."""

    def test_every_offered_value_has_its_renderer(self):
        # El invariante que el mapa ``RENDERER_BY_TYPE`` retirado protegía.
        for value, _ in REPORT_TYPE_CHOICES:
            renderer = mod.RENDERER_PREFIX + value.lower().replace('-', '_')
            assert hasattr(IrActionsReport, renderer), (value, renderer)
