"""``_build_wkhtmltopdf_args`` — las catorce reglas de precedencia del papel.

El símbolo que ``_run_wkhtmltopdf`` resolvía a ojo: atendía dos reglas
—orientación y lienzo— y callaba las otras doce. La declaración anterior lo
daba por fuera «porque el motor es nuestro»; medido, lo único de la source que
no tiene receptor aquí es la **codificación** (una lista de argumentos de línea
de comandos frente a un diccionario), no las reglas.

Cada caso mide **quién gana** cuando el documento y el paperformat dicen cosas
distintas, que es la substancia del método.
"""
import inspect
import io

import pytest
from PIL import Image

from addons.base.models.ir_actions_report import IrActionsReport
from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.report_paperformat import ReportPaperformat
from addons.base.report_template import UnknownImageFormat

pytestmark = pytest.mark.django_db


def _paperformat(**model_fields):
    model_fields.setdefault('name', 'A4 de prueba')
    model_fields.setdefault('format', 'A4')
    return ReportPaperformat.objects.create(**model_fields)


def _args(paperformat=None, landscape=False, **kwargs):
    return IrActionsReport()._build_wkhtmltopdf_args(
        paperformat, landscape, **kwargs)


class TestTheDocumentWinsOverTheReportFormat:
    """``data-report-*`` gana sobre el campo del ``report.paperformat``."""

    @pytest.mark.parametrize('key, out_key', [
        ('data-report-margin-top', 'margin_top'),
        ('data-report-margin-bottom', 'margin_bottom'),
        ('data-report-header-spacing', 'header_spacing'),
    ])
    def test_the_override_wins(self, key, out_key):
        paperformat = _paperformat(margin_top=40, margin_bottom=20, header_spacing=35)
        args = _args(paperformat, False, specific_paperformat_args={key: 99})
        assert args[out_key] == '99'

    def test_without_an_override_the_format_wins(self):
        paperformat = _paperformat(margin_top=40, margin_bottom=20)
        args = _args(paperformat, False)
        assert args['margin_top'] == '40'
        assert args['margin_bottom'] == '20'

    def test_the_dpi_override_wins_and_is_read_as_an_integer(self):
        paperformat = _paperformat(dpi=90)
        args = _args(paperformat, False,
                     specific_paperformat_args={'data-report-dpi': '150'})
        assert args['dpi'] == '150'


class TestTheMarginsWithoutOverrideAreAlwaysEmitted:
    """``margin-left`` y ``margin-right`` no tienen rama de anulación."""

    def test_both_sides_come_from_the_format(self):
        args = _args(_paperformat(margin_left=7, margin_right=11), False)
        assert args['margin_left'] == '7'
        assert args['margin_right'] == '11'


class TestTheCustomSizeOnlyAppliesWhenTheFormatSaysCustom:
    """``page-size`` o ``page-width``/``page-height``, nunca los dos."""

    def test_a_named_format_emits_its_name(self):
        args = _args(_paperformat(format='A4'), False)
        assert args['page_size'] == 'A4'
        assert 'page_width' not in args

    def test_custom_with_both_sides_emits_millimetres(self):
        args = _args(
            _paperformat(format='custom', page_width=210, page_height=297), False)
        assert (args['page_width'], args['page_height']) == ('210mm', '297mm')
        assert 'page_size' not in args

    def test_custom_without_both_sides_emits_neither(self):
        args = _args(_paperformat(format='custom', page_width=210), False)
        assert 'page_width' not in args and 'page_size' not in args


class TestTheOrientationHasThreeSources:
    """El argumento, la anulación del documento y el campo del paperformat."""

    def test_landscape_forced_wins_over_the_format(self):
        args = _args(_paperformat(orientation='Portrait'), True)
        assert args['orientation'] == 'landscape'

    def test_without_forcing_the_format_orientation_is_used(self):
        args = _args(_paperformat(orientation='Portrait'), False)
        assert args['orientation'] == 'Portrait'

    def test_landscape_none_is_taken_from_the_document(self):
        # ``landscape is None`` es la única puerta por la que el documento
        # puede imponer la orientación.
        args = _args(_paperformat(orientation='Portrait'), None,
                     specific_paperformat_args={'data-report-landscape': True})
        assert args['orientation'] == 'landscape'


class TestTheViewportFollowsTheOrientation:
    """``1024x1280`` apaisado, ``1280x1024`` vertical."""

    def test_landscape_gives_the_tall_viewport(self):
        assert _args(None, True, set_viewport_size=True)[
            'viewport_size'] == '1024x1280'

    def test_portrait_gives_the_wide_viewport(self):
        assert _args(None, False, set_viewport_size=True)[
            'viewport_size'] == '1280x1024'

    def test_without_asking_there_is_no_viewport(self):
        assert 'viewport_size' not in _args(None, False)


class TestTheBooleanFlagsAreOnlyEmittedWhenTrue:
    """``header-line`` y ``disable-smart-shrinking`` son banderas."""

    def test_both_appear_when_the_format_declares_them(self):
        args = _args(_paperformat(header_line=True, disable_shrinking=True), False)
        assert args['header_line'] is True
        assert args['disable_smart_shrinking'] is True

    def test_neither_appears_when_the_format_denies_them(self):
        args = _args(_paperformat(header_line=False, disable_shrinking=False), False)
        assert 'header_line' not in args
        assert 'disable_smart_shrinking' not in args


class TestTheRenderDelayComesFromConfiguration:
    """``report.print_delay`` — un parámetro de sistema, no una constante."""

    def test_without_the_parameter_it_is_a_thousand(self):
        assert _args(None, False)['javascript_delay'] == '1000'

    def test_the_stored_parameter_wins(self):
        SystemParameter.set_param('report.print_delay', '2500')
        assert _args(None, False)['javascript_delay'] == '2500'


class TestWithoutFormatOnlyTheUniversalArgumentsSurvive:
    """La rama ``if paperformat_id`` cubre todo lo del paperformat."""

    def test_no_format_leaves_no_margin_and_no_page_size(self):
        args = _args(None, False)
        assert set(args) == {'javascript_delay'}


class TestRunWkhtmltopdfDelegatesTheResolution:
    """La regla no se resuelve dos veces: ``_run_wkhtmltopdf`` llama aquí."""

    def test_the_engine_calls_the_resolver(self):
        source = inspect.getsource(IrActionsReport._run_wkhtmltopdf)
        assert 'self._build_wkhtmltopdf_args(' in source


class TestTheHtmlRasterDrawsFromTheDescriptor:
    """``_run_wkhtmltoimage`` — el nombre es el contrato, el cuerpo es nuestro.

    Estuvo bloqueado declarando que faltaba «un motor de maquetación HTML».
    La directiva del ejecutor cerró esa premisa: no usamos ni queremos
    wkhtmltoimage ni QtWebKit. Y el motor no hacía falta — el cuerpo que este
    árbol pasa **es el descriptor**, igual que en el camino del papel, así que
    la imagen se dibuja de él con Pillow (tarea **#203**).
    """

    def test_it_returns_one_image_per_body(self):
        images = IrActionsReport()._run_wkhtmltoimage(
            [{'title': 'A'}, {'title': 'B'}], 160, 90, image_format='png')
        assert len(images) == 2
        assert all(Image.open(io.BytesIO(raw)).size == (160, 90)
                   for raw in images)

    def test_a_string_body_is_wrapped_like_the_paper_path_does(self):
        # ``_run_wkhtmltopdf`` acepta las dos formas; ésta no puede ser más
        # estricta, o un llamador de la fuente rompería aquí y no allá.
        images = IrActionsReport()._run_wkhtmltoimage(
            ['<p>x</p>'], 120, 60, image_format='png')
        assert Image.open(io.BytesIO(images[0])).size == (120, 60)

    def test_a_body_that_cannot_be_drawn_becomes_none_and_the_batch_survives(
            self):
        class Intratable:
            def __str__(self):
                raise ValueError('este valor no se deja escribir')

        images = IrActionsReport()._run_wkhtmltoimage(
            [{'title': 'A'}, {'title': Intratable()}, {'title': 'C'}],
            120, 60, image_format='png')
        assert images[1] is None
        assert images[0] is not None and images[2] is not None

    def test_an_unknown_format_aborts_the_batch_instead_of_nulling_it(self):
        # Es una precondición de la tanda, como la versión del binario en la
        # fuente — no el fallo de un cuerpo suelto.
        with pytest.raises(UnknownImageFormat):
            IrActionsReport()._run_wkhtmltoimage([{'t': 'x'}], 10, 10,
                                                 image_format='webp')

    def test_its_signature_matches_the_source(self):
        signature = inspect.signature(IrActionsReport._run_wkhtmltoimage)
        assert list(signature.parameters) == [
            'self', 'bodies', 'width', 'height', 'image_format']
        assert signature.parameters['image_format'].default == 'jpg'


class TestTheGeometryReachesTheHelperInMillimetres:
    """``_paperformat_geometry`` — las 31 claves, no las 12 de libharu."""

    def _geometry(self, paperformat, landscape=False, **kwargs):
        report = IrActionsReport()
        args = report._build_wkhtmltopdf_args(paperformat, landscape, **kwargs)
        return report._paperformat_geometry(paperformat, args)

    def test_without_a_format_there_is_no_geometry(self):
        # El helper conserva sus constantes: no se mueve lo que hoy sale bien.
        assert IrActionsReport()._paperformat_geometry(None, {}) == {}

    def test_a4_portrait_gives_its_millimetres(self):
        geometry = self._geometry(_paperformat(format='A4',
                                               orientation='Portrait'))
        assert (geometry['page_width_mm'],
                geometry['page_height_mm']) == (210, 297)

    def test_landscape_swaps_the_sides(self):
        geometry = self._geometry(_paperformat(format='A4',
                                               orientation='Landscape'))
        assert (geometry['page_width_mm'],
                geometry['page_height_mm']) == (297, 210)

    def test_forcing_landscape_swaps_a_portrait_format(self):
        # La orientación que manda es la resuelta, no el campo del modelo.
        geometry = self._geometry(
            _paperformat(format='A4', orientation='Portrait'), landscape=True)
        assert (geometry['page_width_mm'],
                geometry['page_height_mm']) == (297, 210)

    def test_a_format_outside_the_twelve_of_libharu_still_resolves(self):
        # ``B0`` no está en HPDF_PageSizes; por eso la resolución vive aquí.
        geometry = self._geometry(_paperformat(format='B0',
                                               orientation='Portrait'))
        assert geometry['page_width_mm'] > 0
        assert geometry['page_height_mm'] > geometry['page_width_mm']

    def test_custom_carries_its_own_measurements(self):
        geometry = self._geometry(_paperformat(
            format='custom', page_width=80, page_height=200,
            orientation='Portrait'))
        assert (geometry['page_width_mm'],
                geometry['page_height_mm']) == (80, 200)

    def test_the_margins_come_from_the_resolved_arguments(self):
        geometry = self._geometry(_paperformat(
            margin_top=40, margin_bottom=20, margin_left=7, margin_right=7))
        assert geometry['margin_top_mm'] == '40'
        assert geometry['margin_bottom_mm'] == '20'
        assert geometry['margin_left_mm'] == '7'
        assert geometry['margin_right_mm'] == '7'

    def test_the_document_override_wins_over_the_format_margin(self):
        # Releer el margen del modelo ignoraría esta anulación.
        geometry = self._geometry(
            _paperformat(margin_top=40),
            specific_paperformat_args={'data-report-margin-top': 99})
        assert geometry['margin_top_mm'] == '99'
