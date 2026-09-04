"""``controllers/main.image_shape`` — la forma SVG con la imagen dentro.

≙ ``odoo19c: addons/html_editor/controllers/main.py:604-641``.

Este método **estuvo declarado detenido y su causa había caducado**: su
docstring nombraba tres símbolos de ``odoo/tools/image.py`` *"que este árbol
no tiene"* cuando ``src/tools/image.py`` ya los declaraba los tres. Estos
casos existen para que el porte no se pueda volver a perder en silencio:
miden el tamaño derivado de la imagen, el URI insertado y las dos ramas que
la fuente distingue (``data-forced-size`` y el adjunto de tipo ``url``).

``_get_shape_svg`` se sustituye por un SVG en línea a propósito: lee del
``static/`` del addon con ``file_open`` confinado, que tiene sus propios casos
en ``tests/unit/html_editor/test_tools.py`` y en los de ``tools.misc``. Lo que
aquí se mide es el cuerpo que este puerto añadió, no el confinamiento.
"""
import io
from base64 import b64encode

import pytest
from addons.base.models.ir_attachment import IrAttachment
from django.core.files.base import ContentFile
from PIL import Image
from rest_framework.exceptions import NotFound

from addons.html_editor.controllers.main import _CONTROLLER

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

#: Un SVG de forma con el hueco donde la fuente inyecta la imagen. El
#: ``xmlns:xlink`` va declarado porque ``etree.fromstring`` rechaza un prefijo
#: sin espacio de nombres (``XMLSyntaxError``), y las formas reales de la
#: fuente lo declaran: sin él el caso mediría el parser, no el porte.
SHAPE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" '
    'xmlns:xlink="http://www.w3.org/1999/xlink" width="100" height="50">'
    '<image xlink:href=""/></svg>'
)

#: El mismo, con la marca que dispara el ajuste de altura de la fuente.
FORCED_SIZE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" '
    'xmlns:xlink="http://www.w3.org/1999/xlink" width="100" height="50" '
    'data-forced-size="1"><image xlink:href=""/></svg>'
)


def _png_bytes(width, height):
    buffer = io.BytesIO()
    Image.new('RGB', (width, height), (10, 20, 30)).save(buffer, format='PNG')
    return buffer.getvalue()


@pytest.fixture
def png_attachment(db):
    raw = _png_bytes(40, 20)
    attachment = IrAttachment.objects.create(
        name='forma.png', mimetype='image/png', res_model='ir.ui.view',
        res_id=0)
    attachment.datas.save('forma.png', ContentFile(raw), save=True)
    return attachment


@pytest.fixture
def shape(monkeypatch):
    """Sustituye la lectura del ``static/`` por un SVG conocido."""
    def _install(svg):
        monkeypatch.setattr(type(_CONTROLLER), '_get_shape_svg',
                            lambda self, module, *segments: svg)
    return _install


class TestTheRecordKeyIsResolvedInBothFormsOfTheSource:
    """``_find_image_record`` — ≙ los dos caminos de ``_find_record``."""

    def test_the_model_slash_id_pair_resolves(self, png_attachment):
        found = _CONTROLLER._find_image_record(
            'base.IrAttachment/%d' % png_attachment.pk)
        assert found == png_attachment

    def test_the_parenthesised_pair_resolves_too(self, png_attachment):
        found = _CONTROLLER._find_image_record(
            'base.IrAttachment(%d)' % png_attachment.pk)
        assert found == png_attachment

    def test_an_empty_key_resolves_to_nothing(self, db):
        assert _CONTROLLER._find_image_record('') is None
        assert _CONTROLLER._find_image_record(None) is None

    def test_an_unknown_model_resolves_to_nothing(self, db):
        assert _CONTROLLER._find_image_record('no.existe/1') is None

    def test_a_missing_row_resolves_to_nothing(self, db):
        assert _CONTROLLER._find_image_record(
            'base.IrAttachment/99999999') is None

    def test_an_unknown_xmlid_resolves_to_nothing(self, db):
        assert _CONTROLLER._find_image_record('modulo.no_existe') is None


class TestTheShapeCarriesTheImageAndItsSize:
    def test_the_size_comes_from_the_image_not_from_the_svg(
            self, png_attachment, shape):
        shape(SHAPE_SVG)
        response = _CONTROLLER.image_shape(
            None, 'html_builder', 'x.svg',
            'base.IrAttachment/%d' % png_attachment.pk)
        body = response.content.decode()
        assert response['Content-Type'] == 'image/svg+xml'
        assert 'width="40"' in body
        assert 'height="20"' in body

    def test_the_image_is_embedded_as_a_data_uri(self, png_attachment, shape):
        shape(SHAPE_SVG)
        response = _CONTROLLER.image_shape(
            None, 'html_builder', 'x.svg',
            'base.IrAttachment/%d' % png_attachment.pk)
        body = response.content.decode()
        expected = b64encode(_png_bytes(40, 20)).decode()
        assert 'data:image/png;base64,' in body
        assert expected in body

    def test_the_response_is_cacheable_for_a_year(self, png_attachment, shape):
        shape(SHAPE_SVG)
        response = _CONTROLLER.image_shape(
            None, 'html_builder', 'x.svg',
            'base.IrAttachment/%d' % png_attachment.pk)
        assert response['Cache-Control'] == 'max-age=31536000'

    def test_forced_size_derives_the_height_from_the_svg_ratio(
            self, png_attachment, shape):
        # ratio del SVG = 100/50 = 2 · ancho de la imagen = 40 → alto 20.0
        shape(FORCED_SIZE_SVG)
        response = _CONTROLLER.image_shape(
            None, 'html_builder', 'x.svg',
            'base.IrAttachment/%d' % png_attachment.pk)
        body = response.content.decode()
        assert 'width="40"' in body
        assert 'height="20.0"' in body


class TestTheTwoRefusalsOfTheSource:
    def test_an_unresolvable_key_is_a_404(self, db, shape):
        shape(SHAPE_SVG)
        with pytest.raises(NotFound):
            _CONTROLLER.image_shape(None, 'html_builder', 'x.svg',
                                    'base.IrAttachment/99999999')

    def test_a_record_without_bytes_is_a_404(self, db, shape):
        shape(SHAPE_SVG)
        empty = IrAttachment.objects.create(
            name='vacio.png', mimetype='image/png', res_model='ir.ui.view',
            res_id=0)
        with pytest.raises(NotFound):
            _CONTROLLER.image_shape(None, 'html_builder', 'x.svg',
                                    'base.IrAttachment/%d' % empty.pk)


class TestTheUrlAttachmentIsRedirectedInsteadOfEmbedded:
    """≙ ``if stream.type == 'url': return stream.get_response()``."""

    def test_the_response_points_at_the_origin(self, db, shape):
        shape(SHAPE_SVG)
        remote = IrAttachment.objects.create(
            name='remota.png', mimetype='image/png', type='url',
            url='https://ejemplo.test/remota.png', res_model='ir.ui.view',
            res_id=0)
        response = _CONTROLLER.image_shape(
            None, 'html_builder', 'x.svg',
            'base.IrAttachment/%d' % remote.pk)
        assert response.status_code == 302
        assert response['Location'] == 'https://ejemplo.test/remota.png'


class TestTheLegacyModuleNameIsTranslated:
    """≙ ``if module == 'web_editor': module = 'html_builder'``."""

    def test_web_editor_is_served_as_html_builder(self, png_attachment,
                                                  monkeypatch):
        seen = []

        def _spy(self, module, *segments):
            seen.append(module)
            return SHAPE_SVG

        monkeypatch.setattr(type(_CONTROLLER), '_get_shape_svg', _spy)
        _CONTROLLER.image_shape(None, 'web_editor', 'x.svg',
                                'base.IrAttachment/%d' % png_attachment.pk)
        assert seen == ['html_builder']
