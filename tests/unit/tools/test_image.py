"""``tools.image`` — la tubería de imagen de la referencia (tarea #285).

Adaptación de ``odoo19c: odoo/tools/image.py`` (LGPL-3) — atribución y
aviso de licencia preservados (DEC-KX-03). Las imágenes de prueba se
fabrican con Pillow en memoria: no hay fixtures binarias en el repo.
"""
import base64
import io

import pytest
from PIL import Image, ImageDraw

from exceptions import UserError
from tools.image import (
    IMAGE_MAX_RESOLUTION, ImageProcess, average_dominant_color,
    base64_to_image, binary_to_image, get_lightness, get_saturation,
    get_webp_size, hex_to_rgb, image_apply_opt, image_fix_orientation,
    image_guess_size_from_field_name, image_process, image_to_base64,
    is_image_size_above, rgb_to_hex,
)


def _png(width=64, height=32, mode='RGB', color=(200, 30, 30)):
    stream = io.BytesIO()
    Image.new(mode, (width, height), color).save(stream, format='PNG')
    return stream.getvalue()


def _png_with_ellipse(width=640, height=360):
    """Un PNG con contenido no trivial: la paleta WEB sí lo encoge."""
    image = Image.new('RGB', (width, height), (30, 60, 200))
    ImageDraw.Draw(image).ellipse(
        [(100, 20), (width - 100, height - 20)],
        fill=(250, 220, 30), outline=(240, 25, 40), width=10)
    stream = io.BytesIO()
    image.save(stream, format='PNG')
    return stream.getvalue()


def _jpeg(width=64, height=32):
    stream = io.BytesIO()
    Image.new('RGB', (width, height), (10, 200, 10)).save(
        stream, format='JPEG', quality=90)
    return stream.getvalue()


def _webp_vp8_header(width, height):
    """Un contenedor RIFF/WEBP con cabecera VP8 (``' '``) y el tamaño en los
    16 bits del desplazamiento 26 — lo justo para ``get_webp_size``."""
    head = b'RIFF' + b'\x00\x00\x00\x00' + b'WEBPVP8 ' + bytes(10)
    return head + bytes([width & 0xFF, width >> 8, height & 0xFF, height >> 8])


class TestImageProcessOpensTheSource:
    def test_empty_source_is_not_processed(self):
        assert ImageProcess(b'').image is False
        assert ImageProcess(b'').source is False

    def test_svg_is_not_processed_and_comes_back_untouched(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"/>'
        image = ImageProcess(svg)
        assert image.image is False
        assert image.image_quality() == svg

    def test_garbage_raises_the_user_error_of_the_source(self):
        with pytest.raises(UserError):
            ImageProcess(b'not an image at all')

    def test_the_original_format_is_kept_before_any_operation(self):
        assert ImageProcess(_png()).original_format == 'PNG'
        assert ImageProcess(_jpeg()).original_format == 'JPEG'

    def test_too_large_resolution_is_refused_when_verified(self):
        # Sin decodificar 50 Mpx: un WEBP con sólo la cabecera y un tamaño
        # que supera el límite ejerce la misma guarda por la rama VP8.
        big = _webp_vp8_header(8000, 8000)
        assert 8000 * 8000 > IMAGE_MAX_RESOLUTION
        with pytest.raises(UserError):
            ImageProcess(big, verify_resolution=True)
        assert ImageProcess(big, verify_resolution=False).image is False


class TestResize:
    def test_shrinks_keeping_the_ratio(self):
        image = ImageProcess(_png(64, 32)).resize(max_width=32)
        assert image.image.size == (32, 16)
        assert image.operationsCount == 1

    def test_never_grows_without_expand(self):
        image = ImageProcess(_png(64, 32)).resize(max_width=128)
        assert image.image.size == (64, 32)
        assert image.operationsCount == 0

    def test_grows_with_expand(self):
        image = ImageProcess(_png(64, 32)).resize(max_width=128, expand=True)
        assert image.image.size == (128, 64)

    def test_no_dimensions_means_no_operation(self):
        image = ImageProcess(_png()).resize()
        assert image.operationsCount == 0


class TestCropResize:
    def test_forces_the_asked_ratio(self):
        image = ImageProcess(_png(64, 32)).crop_resize(20, 20)
        assert image.image.size == (20, 20)

    def test_center_top_keeps_the_top_rows(self):
        # Mitad superior blanca, inferior negra: recortar por arriba deja
        # sólo blanco.
        canvas = Image.new('RGB', (10, 20), (0, 0, 0))
        canvas.paste((255, 255, 255), (0, 0, 10, 10))
        stream = io.BytesIO(); canvas.save(stream, format='PNG')
        image = ImageProcess(stream.getvalue()).crop_resize(
            10, 10, center_y=0)
        assert image.image.getpixel((5, 5)) == (255, 255, 255)
        assert image.image.getpixel((5, 9)) == (255, 255, 255)


class TestColorizeAndPadding:
    def test_colorize_replaces_transparency_with_the_color(self):
        source = _png(8, 8, mode='RGBA', color=(0, 0, 0, 0))
        image = ImageProcess(source).colorize((1, 2, 3))
        assert image.image.mode == 'RGB'
        assert image.image.getpixel((4, 4)) == (1, 2, 3)

    def test_add_padding_keeps_the_size_and_counts_an_operation(self):
        image = ImageProcess(_png(20, 20)).add_padding(2)
        assert image.image.size == (20, 20)
        assert image.operationsCount == 1


class TestImageQuality:
    def test_untouched_image_comes_back_as_the_source(self):
        source = _png()
        assert ImageProcess(source).image_quality() == source

    def test_unknown_format_falls_to_jpeg_and_bmp_to_png(self):
        out = ImageProcess(_png()).image_quality(output_format='TIFF')
        assert Image.open(io.BytesIO(out)).format == 'JPEG'
        out = ImageProcess(_png()).image_quality(output_format='BMP')
        assert Image.open(io.BytesIO(out)).format == 'PNG'

    def test_png_with_quality_is_paletted_when_that_shrinks_it(self):
        """≙ la rama ``convert('P', palette=Palette.WEB)`` (``:150-152``).

        El contenido tiene que ser no trivial —mismo criterio que
        ``test_13_image_process_quality`` de la fuente, que dibuja una elipse
        «so that optimization matters»—: sobre un PNG plano la paleta pesa
        más que el original y entra la rama de abajo, no ésta.
        """
        source = _png_with_ellipse()
        out = ImageProcess(source).image_quality(quality=80)
        assert len(out) < len(source)
        assert Image.open(io.BytesIO(out)).mode == 'P'

    def test_png_whose_paletted_form_is_bigger_returns_the_source(self):
        """≙ ``if len(output_bytes) >= len(self.source) and … not
        self.operationsCount: return self.source`` (``:164-167``) —
        «Original should be returned if size increased». Un PNG plano de
        64x32 cabe en menos bytes que su versión en paleta."""
        source = _png()
        assert ImageProcess(source).image_quality(quality=80) is source


class TestImageProcessEntryPoint:
    def test_nothing_asked_returns_the_source_untouched(self):
        source = _png()
        assert image_process(source) is source
        assert image_process(b'') == b''

    def test_size_and_crop_top_dispatch_to_crop_resize(self):
        out = image_process(_png(64, 32), size=(16, 16), crop='top')
        assert Image.open(io.BytesIO(out)).size == (16, 16)

    def test_colorize_true_picks_a_random_color(self):
        source = _png(8, 8, mode='RGBA', color=(0, 0, 0, 0))
        out = image_process(source, colorize=True)
        pixel = Image.open(io.BytesIO(out)).convert('RGB').getpixel((4, 4))
        assert pixel != (0, 0, 0)


class TestFixOrientation:
    def test_orientation_six_rotates_the_image(self):
        canvas = Image.new('RGB', (40, 20))
        exif = canvas.getexif(); exif[0x112] = 6
        stream = io.BytesIO(); canvas.save(stream, format='JPEG', exif=exif)
        fixed = image_fix_orientation(Image.open(stream))
        assert fixed.size == (20, 40)

    def test_no_exif_leaves_the_image_alone(self):
        image = Image.new('RGB', (40, 20))
        assert image_fix_orientation(image) is image


class TestConversions:
    def test_binary_and_base64_to_image_and_back(self):
        source = _png(8, 8)
        assert binary_to_image(source).size == (8, 8)
        assert base64_to_image(base64.b64encode(source)).size == (8, 8)
        b64 = image_to_base64(binary_to_image(source), 'PNG')
        assert base64.b64decode(b64)[:8] == b'\x89PNG\r\n\x1a\n'

    def test_image_apply_opt_converts_rgba_to_rgb_for_jpeg(self):
        out = image_apply_opt(Image.new('RGBA', (4, 4)), 'JPEG')
        assert Image.open(io.BytesIO(out)).mode == 'RGB'

    def test_garbage_base64_raises_user_error(self):
        with pytest.raises(UserError):
            base64_to_image(b'!!!not base64!!!')


class TestWebpSize:
    def test_vp8_simple_header(self):
        assert get_webp_size(_webp_vp8_header(300, 150)) == (300, 150)

    def test_vp8x_extended_header(self):
        head = b'RIFF' + bytes(4) + b'WEBPVP8X' + bytes(8)
        # ancho-1 = 299, alto-1 = 149, en 24 bits little-endian
        head += bytes([299 & 0xFF, 299 >> 8, 0, 149 & 0xFF, 149 >> 8, 0])
        assert get_webp_size(head) == (300, 150)

    def test_vp8l_lossless_header(self):
        head = b'RIFF' + bytes(4) + b'WEBPVP8L' + bytes(4) + b'\x2f'
        w, h = 300 - 1, 150 - 1
        ab, cd = w & 0xFF, (w >> 8) | ((h & 0x3) << 6)
        ef, gh = (h >> 2) & 0xFF, h >> 10
        head += bytes([ab, cd, ef, gh])
        assert get_webp_size(head) == (300, 150)

    def test_not_a_webp_raises(self):
        with pytest.raises(UserError):
            get_webp_size(b'\x89PNG')

    def test_unknown_chunk_is_none(self):
        payload = b'RIFF' + bytes(4) + b'WEBPVP8Z' + bytes(20)
        assert get_webp_size(payload) is None


class TestSizeComparison:
    def test_bigger_first_image_is_above(self):
        big = base64.b64encode(_png(64, 64))
        small = base64.b64encode(_png(16, 16))
        assert is_image_size_above(big, small) is True
        assert is_image_size_above(small, big) is False

    def test_svg_or_empty_is_never_above(self):
        svg = base64.b64encode(b'<svg/>')
        assert is_image_size_above(svg, base64.b64encode(_png())) is False
        assert is_image_size_above(b'', base64.b64encode(_png())) is False


class TestGuessSizeFromFieldName:
    @pytest.mark.parametrize('name, size', [
        ('image', (1024, 1024)), ('image_128', (128, 128)),
        ('image_1920', (1920, 1920)), ('x_image_512', (0, 0)),
        ('image_8', (0, 0)), ('avatar', (0, 0)),
    ])
    def test_the_suffix_is_the_size(self, name, size):
        assert image_guess_size_from_field_name(name) == size


class TestColorMaths:
    def test_average_dominant_color_groups_close_colors(self):
        colors = [(50, (200, 10, 10, 255)), (40, (210, 20, 20, 255)),
                  (5, (10, 10, 200, 255))]
        dominant, remaining = average_dominant_color(colors)
        assert remaining == [(5, (10, 10, 200, 255))]
        # promedio ponderado de las dos rojas, mitigado a 175 en la banda alta
        assert dominant[0] == 175 and dominant[1] < 30

    def test_hsl_helpers_and_hex_round_trip(self):
        assert get_saturation((255, 0, 0)) == 1
        assert get_saturation((128, 128, 128)) == 0
        assert get_lightness((255, 255, 255)) == 1
        assert hex_to_rgb('#ff0080') == (255, 0, 128)
        assert rgb_to_hex((255, 0, 128)) == '#ff0080'
