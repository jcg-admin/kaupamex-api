r"""``report_type`` ofrece lo que este árbol sabe emitir, y sus tres referentes coinciden.

:ref:`h-api-931` midió que el campo tenía **tres referentes discordantes**: la
constante ofrecía un valor, el docstring del módulo decía dos y el ``help_text``
del campo decía tres. La exigencia que aquel hallazgo fijó no era un número sino
una **coincidencia**: los tres referentes dicen lo mismo, y lo que dicen es lo
que el árbol sabe emitir. Ese invariante no cambia; lo que cambia es la cifra.

**Por qué son tres y ya no uno (tarea #250).** ``html`` y ``text`` salieron del
enum en :ref:`h-api-291` con una condición de reingreso escrita, que
:ref:`h-api-935` amplió a cuatro exigencias: el valor entra con su
**renderizador**, su **serializador del descriptor**, su **declarante** y su
**test**. Medidas una por una hoy:

- renderizador — ``_render_qweb_html`` y ``_render_qweb_text`` existen desde el
  bloque C, porque el archivo se porta entero;
- serializador — ``descriptor_to_html`` y ``descriptor_to_text`` los construyó
  la tarea #196, que es lo que aquellos dos hallazgos nombraban como *trabajo a
  construir*, y no un símbolo que el stack trajera;
- test — es este archivo, más los casos de despacho de
  ``tests/integration/base/test_report_engine.py``;
- declarante — **era circular, y ésa es la corrección**. ``Selection`` es
  ``CharField(choices=…)`` (``orm/fields_selection.py:25``) y Django valida
  ``choices`` en ``full_clean``, así que ningún addon podía declarar un valor
  que el enum no ofrecía. Exigir declarante para abrir el enum, teniendo el
  enum cerrado, es una condición que no se puede cumplir por construcción.

Lo que **no** vuelve es el prefijo ``qweb-``: esa divergencia tiene su propio
motivo —aquí el intérprete no es QWeb— y sigue vigente. Ver
``REPORT_TYPE_CHOICES``.

*Métrica:* el enum declarado, la prosa de los dos referentes, y la salida real
de los tres serializadores sobre un mismo descriptor.
*Ciega a:* si un consumidor externo espera alguno de los tres formatos por
contrato HTTP — eso lo mide la superficie del endpoint, no este archivo.
"""
import inspect

import pytest

from addons.base import report_template
from addons.base.models import ir_actions_report as mod
from addons.base.models.ir_actions_report import (
    REPORT_TYPE_CHOICES,
    REPORT_TYPE_HTML,
    REPORT_TYPE_PDF,
    REPORT_TYPE_TEXT,
    IrActionsReport,
)

#: Los tres valores que ``odoo19c: odoo/addons/base/models/ir_actions_report.py:170-174``
#: declara, verbatim. Se escriben aquí y no se leen del árbol de referencia
#: para que el caso mida sin depender de que ``odoo-tools`` esté montado.
SOURCE_VALUES = ('qweb-html', 'qweb-pdf', 'qweb-text')

#: Un descriptor con las tres formas del vocabulario, para que la comparación
#: entre formatos no dependa de un solo campo plano.
DESCRIPTOR = {
    'bodies': [{
        'title': 'Factura',
        'issuer': {'name': 'Kaupamex'},
        'lines': [{'concept': 'Servicio'}],
    }],
    'html_ids': [7],
}


class TestTheThreeReferentsAgree:
    """El defecto que :ref:`h-api-931` registró: tres declaraciones, tres cifras."""

    def test_the_enum_offers_the_three_formats_of_the_source(self):
        assert [v for v, _ in REPORT_TYPE_CHOICES] == [
            REPORT_TYPE_HTML, REPORT_TYPE_PDF, REPORT_TYPE_TEXT]

    def test_and_they_are_the_source_values_minus_the_qweb_prefix(self):
        # El porte se mide contra la fuente, no contra sí mismo: cada valor
        # ofrecido es el de la referencia sin su prefijo, y no falta ninguno.
        offered = [v for v, _ in REPORT_TYPE_CHOICES]
        assert offered == [v.removeprefix('qweb-') for v in SOURCE_VALUES]

    def test_no_offered_value_carries_the_qweb_prefix(self):
        # La divergencia de :ref:`h-api-289` sigue vigente y es independiente
        # del conteo: el prefijo nombra un intérprete que este árbol no tiene.
        for value, _label in REPORT_TYPE_CHOICES:
            assert not value.startswith('qweb-'), value

    def test_the_labels_are_the_ones_of_the_source(self):
        # La etiqueta es lo que ve quien elige el formato; la fuente escribe
        # 'HTML', 'PDF' y 'Text', y el porte no las reescribe.
        assert [label for _v, label in REPORT_TYPE_CHOICES] == [
            'HTML', 'PDF', 'Text']

    def test_the_module_docstring_does_not_promise_a_single_format(self):
        # El referente que más lejos llega: quien lee el módulo entero se
        # queda con esa frase y no baja hasta la constante. Decía «su valor es
        # ``pdf``, **uno solo**», que hoy es falso.
        assert 'uno solo' not in mod.__doc__

    def test_the_field_help_names_the_three_formats_it_accepts(self):
        # El referente que ve el usuario final. La aserción NO es sobre el
        # número escrito en prosa —eso mediría el significante— sino sobre que
        # los tres formatos que el campo acepta estén nombrados en él.
        help_text = IrActionsReport._meta.get_field('report_type').help_text.lower()
        for value in (REPORT_TYPE_HTML, REPORT_TYPE_PDF, REPORT_TYPE_TEXT):
            assert value in help_text, value


class TestEachOfferedFormatHasWhatItsReentryDemanded:
    """Las cuatro exigencias de :ref:`h-api-291` + :ref:`h-api-935`, medidas."""

    def test_every_offered_value_reaches_its_renderer(self):
        # El invariante que el mapa ``RENDERER_BY_TYPE`` retirado protegía.
        # Qué lo haría fallar: añadir un valor al enum sin su renderizador.
        for value, _label in REPORT_TYPE_CHOICES:
            renderer = mod.RENDERER_PREFIX + value.lower().replace('-', '_')
            assert hasattr(IrActionsReport, renderer), (value, renderer)

    def test_the_intermediate_is_still_the_descriptor_and_not_html(self):
        # La divergencia de ADR-017 que NO se retira: ``_render_template``
        # sigue devolviendo el intermedio que el helper de libharu consume.
        # Si esto cambiara, los serializadores sobrarían y el motivo de todo
        # este archivo dejaría de ser cierto.
        source = inspect.getsource(IrActionsReport._render_template)
        assert "return {'bodies': bodies, 'html_ids': html_ids}" in source

    def test_the_two_serializers_the_reentry_demanded_are_built(self):
        for serializer in ('descriptor_to_html', 'descriptor_to_text'):
            assert hasattr(report_template, serializer), serializer


class TestTheThreeFormatsProduceThreeDifferentDocuments:
    """Conducta, no nombres: el mismo descriptor sale distinto por cada camino.

    Un caso que sólo afirmara «devuelve algo» pasaría aunque los tres
    serializadores devolvieran el mismo dict crudo, que es exactamente el
    defecto que :ref:`h-api-935` midió. Lo que discrimina es que las salidas
    **difieran entre sí** y que cada una lleve la marca de su formato.
    """

    def test_html_and_text_are_pairwise_distinct_over_one_descriptor(self):
        html = report_template.descriptor_to_html(DESCRIPTOR)
        text = report_template.descriptor_to_text(DESCRIPTOR)
        assert html != text

    def test_both_return_bytes_as_the_signature_of_the_source_promises(self):
        # ``odoo19c: ir_actions_report.py:774`` declara ``:rtype: bytes`` para
        # el paso que comparten los tres formatos.
        assert isinstance(report_template.descriptor_to_html(DESCRIPTOR), bytes)
        assert isinstance(report_template.descriptor_to_text(DESCRIPTOR), bytes)

    def test_html_carries_the_markup_contract_and_text_carries_none_of_it(self):
        # El par ``data-oe-model``/``data-oe-id`` es lo que la fuente busca al
        # partir el documento por registro (``_prepare_html``, ``:383-463``).
        html = report_template.descriptor_to_html(
            DESCRIPTOR, model='sale.SaleOrder').decode()
        text = report_template.descriptor_to_text(DESCRIPTOR).decode()
        assert 'data-oe-model="sale.SaleOrder"' in html
        assert 'data-oe-id="7"' in html
        assert '<div' not in text

    def test_text_carries_the_id_rule_that_separates_two_records(self):
        # El equivalente en texto del ``data-oe-id``: sin él, dos registros
        # seguidos se leen como un documento de campos repetidos.
        text = report_template.descriptor_to_text(DESCRIPTOR).decode()
        assert '--- 7 ---' in text

    def test_the_three_shapes_of_the_vocabulary_survive_both_paths(self):
        # ``field``, ``section`` y ``list``: si un serializador aplanara la
        # anidación, este caso caería aunque el anterior siguiera verde.
        html = report_template.descriptor_to_html(DESCRIPTOR).decode()
        text = report_template.descriptor_to_text(DESCRIPTOR).decode()
        assert '<div class="section" data-name="issuer">' in html
        assert '<div class="list" data-name="lines">' in html
        assert 'issuer:' in text and 'lines:' in text


class TestTheDispatchStillRefusesWhatItCannotEmit:
    """Abrir el enum a tres no lo abre a cualquiera — el control negativo."""

    def test_a_value_outside_the_enum_has_no_renderer_to_derive(self):
        # Control positivo del sub-patrón D: el caso apunta a un valor **real**
        # —``qweb-pdf`` es el que la migración 0005 convirtió— y no a una
        # cadena inventada. La derivación antepone ``RENDERER_PREFIX``, así que
        # buscaría ``_render_qweb_qweb_pdf``, que no existe.
        assert 'qweb-pdf' not in {v for v, _ in REPORT_TYPE_CHOICES}
        renderer = mod.RENDERER_PREFIX + 'qweb-pdf'.replace('-', '_')
        assert not hasattr(IrActionsReport, renderer)

    def test_the_image_format_stays_out_because_the_source_leaves_it_out(self):
        # ``descriptor_to_image`` existe (tarea #203) y aun así ``image`` no
        # entra: el enum porta el catálogo de la fuente, y allá el raster es
        # ``_run_wkhtmltoimage``, no un ``report_type``. Portar completo no es
        # ofrecer todo lo que se sabe hacer.
        assert hasattr(report_template, 'descriptor_to_image')
        assert 'image' not in {v for v, _ in REPORT_TYPE_CHOICES}
