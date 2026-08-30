r"""Los dos serializadores del descriptor — lo que la firma de cada formato promete.

Tarea **#196**, con el criterio de las dos categorías: *el stack lo trae hecho*
frente a *el stack tiene con qué construirlo*. Éste es el segundo caso — la
referencia no tiene serializador porque su intermedio **ya es HTML**
(``odoo19c: ir_actions_report.py:769-789``, ``:rtype: bytes``), mientras el
nuestro es el descriptor que dibuja el motor de libharu (ADR-017).

*Métrica:* la salida real de los dos serializadores y de los dos renderizadores
que los consumen, no el texto de sus cuerpos.
*Ciega a:* si el texto plano que sale es el que un lector humano prefiere —eso
es una decisión de presentación, no del serializador— y a lo que el motor de
papel haga después con el descriptor, que no pasa por aquí.
"""
import io
from decimal import Decimal

import pytest
from django.utils.safestring import mark_safe
from PIL import Image

from addons.base import report_template as rt


DESCRIPTOR = {
    'title': 'Factura',
    'issuer': {'name': 'Kaupamex', 'rfc': 'KAU010101AAA'},
    'lines': [
        {'concept': 'Servicio', 'amount': '100.00'},
        {'concept': 'Envio', 'amount': '50.00'},
    ],
}


class TestTheHtmlSerializerCarriesTheThreeShapes:
    """``field``, ``section`` y ``list`` — cada una con su etiqueta."""

    def test_a_plain_field_becomes_a_div_with_its_name_in_data_name(self):
        html = rt.descriptor_to_html({'title': 'Factura'}).decode()
        assert '<div class="field" data-name="title">Factura</div>' in html

    def test_a_section_nests_and_keeps_its_children(self):
        html = rt.descriptor_to_html(DESCRIPTOR).decode()
        assert '<div class="section" data-name="issuer">' in html
        assert '<div class="field" data-name="rfc">KAU010101AAA</div>' in html

    def test_a_list_wraps_each_item_so_two_items_are_not_read_as_one(self):
        # El control que discrimina la forma ``list``: sin el envoltorio por
        # elemento, dos elementos de dos campos se leen como uno de cuatro.
        html = rt.descriptor_to_html(DESCRIPTOR).decode()
        assert html.count('<div class="item">') == 2
        assert '<div class="list" data-name="lines">' in html

    def test_it_returns_bytes_as_the_signature_of_the_source_promises(self):
        assert isinstance(rt.descriptor_to_html(DESCRIPTOR), bytes)


class TestTheHtmlSerializerEscapesRawTextAndNotConverterMarkup:
    """``conditional_escape``, no ``escape`` — y la diferencia es medible."""

    def test_raw_dtl_output_is_escaped(self):
        # ``_render_text`` renderiza con ``autoescape=False``, así que lo que
        # llega de un ``<field>`` sin ``widget`` es ``str`` crudo: si no se
        # escapa aquí, no lo escapa nadie.
        html = rt.descriptor_to_html({'note': '<script>alert(1)</script>'}).decode()
        assert '<script>' not in html
        assert '&lt;script&gt;' in html

    def test_but_what_a_converter_already_marked_safe_is_left_alone(self):
        # El conversor ``ir.qweb.field.*`` devuelve ``SafeString`` vía
        # ``mark_safe``. Re-escaparlo publicaría ``&lt;img …&gt;`` en el papel.
        html = rt.descriptor_to_html({'logo': mark_safe('<img src="a.png"/>')}).decode()
        assert '<img src="a.png"/>' in html
        assert '&lt;img' not in html

    def test_and_the_name_is_escaped_too_because_it_lands_in_an_attribute(self):
        html = rt.descriptor_to_html({'a"b': 'x'}).decode()
        assert 'data-name="a&quot;b"' in html


class TestTheHtmlSerializerWritesThePairThatSplitsByRecord:
    """``data-oe-model``/``data-oe-id`` — el contrato que ``_prepare_html`` lee."""

    def test_with_model_and_ids_each_article_carries_both(self):
        html = rt.descriptor_to_html(
            {'bodies': [{'a': '1'}, {'a': '2'}], 'html_ids': [7, 8]},
            model='res.partner').decode()
        assert '<div class="article" data-oe-model="res.partner" data-oe-id="7">' in html
        assert 'data-oe-id="8"' in html

    def test_without_ids_the_article_opens_anyway(self):
        # Un reporte sin registros —una portada, un listado agregado— no tiene
        # id que escribir, y eso no puede impedir que el documento salga.
        html = rt.descriptor_to_html({'bodies': [{'a': '1'}], 'html_ids': [None]}).decode()
        assert '<div class="article">' in html
        assert 'data-oe-id' not in html


class TestTheTextSerializerFlattensWithoutLosingTheStructure:

    def test_a_field_is_one_line_of_name_and_value(self):
        assert rt.descriptor_to_text({'title': 'Factura'}) == b'title: Factura'

    def test_a_section_indents_its_children_under_its_name(self):
        text = rt.descriptor_to_text({'issuer': {'name': 'Kaupamex'}}).decode()
        assert text == 'issuer:\n  name: Kaupamex'

    def test_a_list_marks_where_each_item_starts(self):
        # Mismo control que en HTML, sobre el otro formato: el guion es lo que
        # impide leer dos elementos de dos campos como uno de cuatro.
        text = rt.descriptor_to_text(DESCRIPTOR).decode()
        assert text.count('- concept:') == 2

    def test_the_record_rule_carries_the_id_when_there_is_one(self):
        text = rt.descriptor_to_text(
            {'bodies': [{'a': '1'}, {'a': '2'}], 'html_ids': [7, 8]}).decode()
        assert text.splitlines()[0] == '--- 7 ---'
        assert '--- 8 ---' in text

    def test_it_returns_bytes_too(self):
        assert isinstance(rt.descriptor_to_text(DESCRIPTOR), bytes)


class TestBothAcceptTheIntermediateAndABareDescriptor:
    """``_bodies_and_ids`` — la misma tolerancia que ``_prepare_html``."""

    def test_the_intermediate_and_the_bare_descriptor_agree(self):
        bare = rt.descriptor_to_html({'a': '1'})
        wrapped = rt.descriptor_to_html({'bodies': [{'a': '1'}], 'html_ids': [None]})
        assert bare == wrapped

    def test_a_decimal_value_survives_both_serializers(self):
        # El camino del API entrega decimal crudo (pieza 4); el serializador no
        # es quien lo formatea, así que tiene que dejarlo pasar tal cual.
        assert b'1234.50' in rt.descriptor_to_text({'total': Decimal('1234.50')})
        assert b'1234.50' in rt.descriptor_to_html({'total': Decimal('1234.50')})


class TestTheRasterSerializerDrawsWhatTheDescriptorSays:
    """``descriptor_to_image`` — el tercer formato, tarea **#203**.

    La fuente no lo tiene porque su raster lo produce ``wkhtmltoimage``, un
    binario externo que maqueta HTML con QtWebKit. Este árbol no lo usa ni lo
    quiere (directiva del ejecutor), y no le hace falta: el intermedio de aquí
    es el descriptor, y el descriptor ya dice todo lo que la imagen tiene que
    mostrar.
    """

    def _colours(self, raw):
        return len(Image.open(io.BytesIO(raw)).convert('RGB').getcolors(1 << 16))

    def test_the_image_has_the_size_that_was_asked_for(self):
        raw = rt.descriptor_to_image(DESCRIPTOR, 320, 240)
        assert Image.open(io.BytesIO(raw)).size == (320, 240)

    def test_png_comes_out_as_png_and_jpg_as_jpeg(self):
        png = rt.descriptor_to_image(DESCRIPTOR, 200, 120, image_format='png')
        jpg = rt.descriptor_to_image(DESCRIPTOR, 200, 120, image_format='jpg')
        assert Image.open(io.BytesIO(png)).format == 'PNG'
        assert Image.open(io.BytesIO(jpg)).format == 'JPEG'

    def test_an_unknown_format_fails_loudly(self):
        # Devolver un PNG donde se pidió otra cosa sería el verde que no
        # discrimina: quien lo guarde con la extensión pedida sirve un archivo
        # cuyo contenido no coincide con su tipo.
        with pytest.raises(rt.UnknownImageFormat, match='webp'):
            rt.descriptor_to_image(DESCRIPTOR, 200, 120, image_format='webp')

    def test_the_canvas_is_not_blank_because_the_content_is_drawn(self):
        # El control que discrimina: un lienzo en blanco del tamaño pedido
        # pasaría los dos casos anteriores sin dibujar nada.
        assert self._colours(rt.descriptor_to_image(DESCRIPTOR, 320, 240,
                                                    image_format='png')) > 1

    def test_two_different_descriptors_do_not_draw_the_same_pixels(self):
        one = rt.descriptor_to_image({'title': 'Factura'}, 320, 240,
                                     image_format='png')
        another = rt.descriptor_to_image({'title': 'Nota de credito'}, 320, 240,
                                         image_format='png')
        assert one != another

    def test_the_record_rule_reaches_the_drawing_like_it_does_the_text(self):
        with_id = rt.descriptor_to_image(
            {'bodies': [{'title': 'F'}], 'html_ids': ['7']}, 320, 240,
            image_format='png')
        without_id = rt.descriptor_to_image(
            {'bodies': [{'title': 'F'}], 'html_ids': [None]}, 320, 240,
            image_format='png')
        assert with_id != without_id

    def test_a_descriptor_taller_than_the_canvas_still_draws_what_fits(self):
        tall = {f'field_{i}': str(i) for i in range(200)}
        raw = rt.descriptor_to_image(tall, 200, 60, image_format='png')
        assert Image.open(io.BytesIO(raw)).size == (200, 60)
        assert self._colours(raw) > 1
