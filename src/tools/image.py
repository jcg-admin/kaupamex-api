"""Utilidades de imagen — ≙ ``odoo/tools/image.py`` (``odoo19c:``, LGPL-3,
603 líneas). Atribución y aviso de licencia preservados (DEC-KX-03).

Porte — 22 de 22 símbolos (16 ``def``/``class`` + 6 constantes, medidos por
AST sobre la fuente; tarea #285). El primer tramo (#261) trajo sólo los dos
que ``ir.qweb._prepare_environment`` consume; éste completa el archivo.

Dos divergencias de forma, declaradas:

- ``_lt`` es aquí el ``_`` eager de :mod:`tools.translate`: la fuente lo
  declara ``LazyTranslate('base')`` para que el mensaje se traduzca al
  formatearse, y este árbol no tiene traducción perezosa (el eje ``translate``
  es la tarea #184). Los mensajes se levantan en el momento, así que el
  resultado es el mismo texto.
- ``Image.preinit()`` / ``Image._initialized = 2`` se conservan: precargan
  el subconjunto mínimo de formatos que Pillow reconoce sin recorrer todos
  los plugins, como la fuente.
"""
import base64
import binascii
import io
from random import randrange
from typing import Tuple, Union

# ICO se precarga también: se considera seguro (la fuente hace lo mismo).
from PIL import IcoImagePlugin  # noqa: F401
from PIL import Image, ImageOps
from PIL.Image import Palette, Resampling, Transpose

from exceptions import UserError
from tools.misc import DotDict
from tools.translate import _

__all__ = ["image_process"]

#: ≙ ``_lt = LazyTranslate('base')`` — ver la divergencia declarada arriba.
_lt = _

# Precarga de Pillow con el subconjunto mínimo de formatos que hacen falta.
Image.preinit()
Image._initialized = 2

#: ≙ ``FILETYPE_BASE64_MAGICWORD`` (``:32-38``): sólo los 6 primeros bits
#: del base64 — bastante exacto para este uso y más rápido que decodificar
#: el binario entero.
FILETYPE_BASE64_MAGICWORD = {
    b'/': 'jpg',
    b'R': 'gif',
    b'i': 'png',
    b'P': 'svg+xml',
    b'U': 'webp',
}

EXIF_TAG_ORIENTATION = 0x112
#: El objetivo es que la primera fila/columna quede arriba/izquierda.
#: Nota: ``rotate`` gira en sentido antihorario.
EXIF_TAG_ORIENTATION_TO_TRANSPOSE_METHODS = {  # lado inicial en fila/col 1:
    0: [],                                                # reservado
    1: [],                                                # arriba/izquierda
    2: [Transpose.FLIP_LEFT_RIGHT],                       # arriba/derecha
    3: [Transpose.ROTATE_180],                            # abajo/derecha
    4: [Transpose.FLIP_TOP_BOTTOM],                       # abajo/izquierda
    5: [Transpose.FLIP_LEFT_RIGHT, Transpose.ROTATE_90],  # izquierda/arriba
    6: [Transpose.ROTATE_270],                            # derecha/arriba
    7: [Transpose.FLIP_TOP_BOTTOM, Transpose.ROTATE_90],  # derecha/abajo
    8: [Transpose.ROTATE_90],                             # izquierda/abajo
}

#: Límite arbitrario que cubre la mayoría de resoluciones: la foto de un
#: Samsung Galaxy A22, 8K con relación hasta 16:10 y casi todas las variantes
#: de 4320p.
IMAGE_MAX_RESOLUTION = 50e6


class ImageProcess:
    """≙ ``ImageProcess`` (``:58-296``) — la tubería de operaciones sobre
    una imagen: abrir, corregir orientación, redimensionar, recortar,
    colorear, rellenar y serializar con calidad."""

    def __init__(self, source, verify_resolution=True):
        """Prepara la imagen ``source`` para procesarla.

        :param bytes source: el binario original. No se procesa nada si
            ``source`` es falso o si la imagen es SVG.
        :param bool verify_resolution: si es verdadero, comprueba que la
            resolución original no sea excesiva antes de procesar; el máximo
            lo fija ``IMAGE_MAX_RESOLUTION``.
        :raise UserError: si la imagen es demasiado grande con
            ``verify_resolution``, o si Pillow no la reconoce.
        """
        self.source = source or False
        self.operationsCount = 0

        if not source or source[:1] == b'<':
            # ni fuente vacía ni SVG se procesan
            self.image = False
        elif source[0:4] == b'RIFF' and source[8:15] == b'WEBPVP8':
            # WEBP no se procesa, pero su resolución se verifica igual que la
            # de los demás formatos.
            self.image = False
            if verify_resolution:
                size = get_webp_size(source)
                if size and size[0] * size[1] > IMAGE_MAX_RESOLUTION:
                    raise UserError(_lt(
                        "Too large image (above %sMpx), "
                        "reduce the image size.",
                        str(IMAGE_MAX_RESOLUTION / 1e6)))
        else:
            try:
                self.image = Image.open(io.BytesIO(source))
            except (OSError, binascii.Error):
                raise UserError(_lt(
                    "This file could not be decoded as an image file."))

            # El formato original se guarda antes de corregir la orientación
            # o de cualquier otra operación: la imagen resultante lo pierde.
            self.original_format = (self.image.format or '').upper()

            self.image = image_fix_orientation(self.image)

            w, h = self.image.size
            if verify_resolution and w * h > IMAGE_MAX_RESOLUTION:
                raise UserError(_lt(
                    "Too large image (above %sMpx), reduce the image size.",
                    str(IMAGE_MAX_RESOLUTION / 1e6)))

    def image_quality(self, quality=0, output_format=''):
        """La imagen resultante de todas las operaciones aplicadas.

        La fuente se devuelve tal cual si es SVG, o si no se aplicó ninguna
        operación, ``output_format`` coincide con el original y no se pidió
        calidad.

        :param int quality: calidad. JPEG: 1 peor, 95 mejor (por encima de 95
            se desaconseja; un valor falso cae a 95 sólo si la imagen cambió).
            PNG: falso evita la conversión a paleta WEB. Otros: sin efecto.
        :param str output_format: PNG, JPEG, GIF o ICO. Por defecto el formato
            original si es válido; si no, BMP pasa a PNG y el resto a JPEG.
        :return: la imagen final, o ``False`` si ``source`` era falso.
        :rtype: bytes | False
        """
        if not self.image:
            return self.source

        output_image = self.image

        output_format = output_format.upper() or self.original_format
        if output_format == 'BMP':
            output_format = 'PNG'
        elif output_format not in ['PNG', 'JPEG', 'GIF', 'ICO']:
            output_format = 'JPEG'

        if (not self.operationsCount and output_format == self.original_format
                and not quality):
            return self.source

        opt = {'output_format': output_format}

        if output_format == 'PNG':
            opt['optimize'] = True
            if quality:
                if output_image.mode != 'P':
                    # tramado Floyd-Steinberg por defecto
                    output_image = output_image.convert('RGBA').convert(
                        'P', palette=Palette.WEB, colors=256)
        if output_format == 'JPEG':
            opt['optimize'] = True
            opt['quality'] = quality or 95
        if output_format == 'GIF':
            opt['optimize'] = True
            opt['save_all'] = True

        if (output_image.mode not in ["1", "L", "P", "RGB", "RGBA"]
                or (output_format == 'JPEG' and output_image.mode == 'RGBA')):
            output_image = output_image.convert("RGB")

        output_bytes = image_apply_opt(output_image, **opt)
        if (len(output_bytes) >= len(self.source)
                and self.original_format == output_format
                and not self.operationsCount):
            # El formato no cambió y el contenido tampoco, pero el binario
            # salió más grande: mejor el original.
            return self.source
        return output_bytes

    def resize(self, max_width=0, max_height=0, expand=False):
        """Redimensiona sin superar el tamaño actual (salvo ``expand``).

        Conserva la relación de aspecto (para cambiarla, ``crop_resize``). Si
        ``max_width`` o ``max_height`` es falso, se calcula del otro; si los
        dos lo son, no se hace nada. No soportado para GIF (no se manejan
        todos los fotogramas).

        :return: ``self``, para encadenar.
        """
        if (self.image and self.original_format != 'GIF'
                and (max_width or max_height)):
            w, h = self.image.size
            asked_width = max_width or (w * max_height) // h
            asked_height = max_height or (h * max_width) // w
            if expand and (asked_width > w or asked_height > h):
                self.image = self.image.resize((asked_width, asked_height))
                self.operationsCount += 1
                return self
            if asked_width != w or asked_height != h:
                self.image.thumbnail(
                    (asked_width, asked_height), Resampling.LANCZOS)
                if self.image.width != w or self.image.height != h:
                    self.operationsCount += 1
        return self

    def crop_resize(self, max_width, max_height, center_x=0.5, center_y=0.5):
        """Recorta y redimensiona a la relación ``max_width``/``max_height``.

        Nunca agranda. El recorte va antes del redimensionado para conservar
        cuanto se pueda de la imagen: el objetivo es llegar a una relación de
        aspecto, no quitar partes indeseadas (para eso, ``crop`` de Pillow).
        No soportado para GIF.

        :param float center_x: centro del recorte entre 0 (izquierda) y 1
            (derecha); 0.5 por defecto.
        :param float center_y: ídem entre 0 (arriba) y 1 (abajo).
        :return: ``self``, para encadenar.
        """
        if (self.image and self.original_format != 'GIF'
                and max_width and max_height):
            w, h = self.image.size
            # Conservar cuanto se pueda: al menos una de las dos dimensiones
            # del recorte es siempre la de la imagen original. El tamaño
            # objetivo lo alcanza el redimensionado final.
            if w / max_width > h / max_height:
                new_w, new_h = w, (max_height * w) // max_width
            else:
                new_w, new_h = (max_width * h) // max_height, h

            # Sin recortes por encima del tamaño de la imagen.
            if new_w > w:
                new_w, new_h = w, (new_h * w) // new_w
            if new_h > h:
                new_w, new_h = (new_w * h) // new_h, h

            # Las dimensiones son al menos 1.
            new_w, new_h = max(new_w, 1), max(new_h, 1)

            # Colocar bien el centro del recorte.
            x_offset = int((w - new_w) * center_x)
            h_offset = int((h - new_h) * center_y)

            if new_w != w or new_h != h:
                self.image = self.image.crop(
                    (x_offset, h_offset, x_offset + new_w, h_offset + new_h))
                if self.image.width != w or self.image.height != h:
                    self.operationsCount += 1

        return self.resize(max_width, max_height)

    def colorize(self, color=None):
        """Sustituye el fondo transparente por ``color`` (RGB) o por uno al
        azar. :return: ``self``, para encadenar."""
        if color is None:
            color = (randrange(32, 224, 24), randrange(32, 224, 24),
                     randrange(32, 224, 24))
        if self.image:
            original = self.image
            self.image = Image.new('RGB', original.size)
            self.image.paste(color, box=(0, 0) + original.size)
            self.image.paste(original, mask=original)
            self.operationsCount += 1
        return self

    def add_padding(self, padding):
        """Amplía la imagen añadiendo un borde de ``padding`` píxeles.
        :return: ``self``, para encadenar."""
        if self.image:
            img_width, img_height = self.image.size
            self.image = self.image.resize(
                (img_width - 2 * padding, img_height - 2 * padding))
            self.image = ImageOps.expand(self.image, border=padding)
            self.operationsCount += 1
        return self


def image_process(source, size=(0, 0), verify_resolution=False, quality=0,
                  expand=False, crop=None, colorize=False, output_format='',
                  padding=False):
    """≙ ``image_process`` (``:298-329``) — aplica a ``source`` las
    operaciones pedidas y devuelve la imagen resultante."""
    if not source or ((not size or (not size[0] and not size[1]))
                      and not verify_resolution and not quality and not crop
                      and not colorize and not output_format and not padding):
        # por rendimiento: nada que hacer si la imagen es falsa o no se pidió
        # ninguna operación
        return source

    image = ImageProcess(source, verify_resolution)
    if size:
        if crop:
            center_x = 0.5
            center_y = 0.5
            if crop == 'top':
                center_y = 0
            elif crop == 'bottom':
                center_y = 1
            image.crop_resize(max_width=size[0], max_height=size[1],
                              center_x=center_x, center_y=center_y)
        else:
            image.resize(max_width=size[0], max_height=size[1], expand=expand)
    if padding:
        image.add_padding(padding)
    if colorize:
        image.colorize(colorize if isinstance(colorize, tuple) else None)
    return image.image_quality(quality=quality, output_format=output_format)


# ----------------------------------------
# Utilidades sueltas de imagen
# ----------------------------------------

def average_dominant_color(colors, mitigate=175, max_margin=140):
    """≙ ``average_dominant_color`` (``:336-395``) — el color dominante de
    una lista de ``(conteo, (R, G, B, A))`` (salida de ``Image.getcolors``).

    Cinco pasos: aislar el color más frecuente; fijar márgenes según su
    prevalencia; agrupar en el conjunto dominante los colores parecidos y
    dejar el resto en «remaining»; promediar banda a banda; mitigar el
    promedio final.

    :return: ``(promedio del conjunto dominante como (R, G, B), remaining)``.
    """
    dominant_color = max(colors)
    dominant_rgb = dominant_color[1][:3]
    dominant_set = [dominant_color]
    remaining = []

    margins = [max_margin * (1 - dominant_color[0] /
                             sum([col[0] for col in colors]))] * 3

    colors.remove(dominant_color)

    for color in colors:
        rgb = color[1]
        if (rgb[0] < dominant_rgb[0] + margins[0]
                and rgb[0] > dominant_rgb[0] - margins[0]
                and rgb[1] < dominant_rgb[1] + margins[1]
                and rgb[1] > dominant_rgb[1] - margins[1]
                and rgb[2] < dominant_rgb[2] + margins[2]
                and rgb[2] > dominant_rgb[2] - margins[2]):
            dominant_set.append(color)
        else:
            remaining.append(color)

    dominant_avg = []
    for band in range(3):
        avg = total = 0
        for color in dominant_set:
            avg += color[0] * color[1][band]
            total += color[0]
        dominant_avg.append(int(avg / total))

    final_dominant = []
    brightest = max(dominant_avg)
    for color in range(3):
        value = (dominant_avg[color] / (brightest / mitigate)
                 if brightest > mitigate else dominant_avg[color])
        final_dominant.append(int(value))

    return tuple(final_dominant), remaining


def image_fix_orientation(image):
    """≙ ``image_fix_orientation`` (``:398-427``) — aplica la transposición
    que dicta la etiqueta EXIF de orientación, antes de cualquier otra
    operación: todas esperan la imagen ya orientada (primera fila arriba,
    primera columna a la izquierda), y las etiquetas EXIF no sobreviven al
    guardado. La etiqueta no se retira de la imagen resultante: nadie la lee
    después, y quitarla costaría más de lo que vale.
    """
    getexif = (getattr(image, 'getexif', None)
               or getattr(image, '_getexif', None))  # Pillow < 6.0
    if getexif:
        exif = getexif()
        if exif:
            orientation = exif.get(EXIF_TAG_ORIENTATION, 0)
            for method in EXIF_TAG_ORIENTATION_TO_TRANSPOSE_METHODS.get(
                    orientation, []):
                image = image.transpose(method)
            return image
    return image


def binary_to_image(source):
    """≙ ``binary_to_image`` (``:430-434``)."""
    try:
        return Image.open(io.BytesIO(source))
    except (OSError, binascii.Error):
        raise UserError(
            _lt("This file could not be decoded as an image file."))


def base64_to_image(base64_source: Union[str, bytes]) -> Image:
    """≙ ``base64_to_image`` (``:436-445``) — la imagen Pillow de un base64;
    ``UserError`` si el base64 es inválido o Pillow no la reconoce."""
    try:
        return Image.open(io.BytesIO(base64.b64decode(base64_source)))
    except (OSError, binascii.Error):
        raise UserError(
            _lt("This file could not be decoded as an image file."))


def image_apply_opt(image: Image, output_format: str, **params) -> bytes:
    """≙ ``image_apply_opt`` (``:448-461``) — serializa ``image`` a
    ``output_format`` con ``params`` (los de ``Image.save``)."""
    if output_format == 'JPEG' and image.mode not in ['1', 'L', 'RGB']:
        image = image.convert("RGB")
    stream = io.BytesIO()
    image.save(stream, format=output_format, **params)
    return stream.getvalue()


def image_to_base64(image, output_format, **params):
    """≙ ``image_to_base64`` (``:464-474``) — la imagen serializada y en
    base64 (``bytes``)."""
    stream = image_apply_opt(image, output_format, **params)
    return base64.b64encode(stream)


def get_webp_size(source):
    """≙ ``get_webp_size`` (``:477-511``) — ``(ancho, alto)`` de un binario
    WEBP para VP8, VP8X y VP8L; ``None`` si el subformato no se soporta.
    Ver https://developers.google.com/speed/webp/docs/riff_container.
    """
    if not (source[0:4] == b'RIFF' and source[8:15] == b'WEBPVP8'):
        raise UserError(_lt("This file is not a webp file."))

    vp8_type = source[15]
    if vp8_type == 0x20:  # 0x20 = ' '
        # Tamaños en 16 bits little-endian en el desplazamiento 26.
        width_low, width_high, height_low, height_high = source[26:30]
        width = (width_high << 8) + width_low
        height = (height_high << 8) + height_low
        return (width, height)
    elif vp8_type == 0x58:  # 0x58 = 'X'
        # Tamaños (menos uno) en 24 bits little-endian en el 24.
        (width_low, width_medium, width_high,
         height_low, height_medium, height_high) = source[24:30]
        width = 1 + (width_high << 16) + (width_medium << 8) + width_low
        height = 1 + (height_high << 16) + (height_medium << 8) + height_low
        return (width, height)
    elif vp8_type == 0x4C and source[20] == 0x2F:  # 0x4C = 'L'
        # Tamaños (menos uno) en 14 bits en el desplazamiento 21:
        # [@20] 2F ab cd ef gh — width = 1 + (c&0x3)d ab (se ignoran los dos
        # bits altos del segundo byte); height = 1 + hef(c&0xC>>2).
        ab, cd, ef, gh = source[21:25]
        width = 1 + ((cd & 0x3F) << 8) + ab
        height = 1 + ((gh & 0xF) << 10) + (ef << 2) + (cd >> 6)
        return (width, height)
    return None


def is_image_size_above(base64_source_1, base64_source_2):
    """≙ ``is_image_size_above`` (``:514-538``) — ¿la primera imagen es más
    grande que la segunda en alguna dimensión? Falso para SVG y para un WEBP
    de subformato desconocido."""
    if not base64_source_1 or not base64_source_2:
        return False
    if (base64_source_1[:1] in (b'P', 'P')
            or base64_source_2[:1] in (b'P', 'P')):
        # Falso para SVG
        return False

    def get_image_size(base64_source):
        source = base64.b64decode(base64_source)
        if (source[0:4] == b'RIFF' and source[8:15] == b'WEBPVP8'):
            size = get_webp_size(source)
            if size:
                return DotDict({'width': size[0], 'height': size[0]})
            else:
                # Falso para un WEBP de formato desconocido
                return False
        else:
            return image_fix_orientation(binary_to_image(source))

    image_source = get_image_size(base64_source_1)
    image_target = get_image_size(base64_source_2)
    return (image_source.width > image_target.width
            or image_source.height > image_target.height)


def image_guess_size_from_field_name(field_name: str) -> Tuple[int, int]:
    """≙ ``image_guess_size_from_field_name`` (``:541-562``) — el tamaño que
    sugiere el nombre del campo (``image_128`` → ``(128, 128)``); ``(0, 0)``
    si no se puede adivinar o es un campo a medida (``x_``)."""
    if field_name == 'image':
        return (1024, 1024)
    if field_name.startswith('x_'):
        return (0, 0)
    try:
        suffix = int(field_name.rsplit('_', 1)[-1])
    except ValueError:
        return 0, 0

    if suffix < 16:
        # Por debajo de 16 el sufijo seguramente no es el tamaño
        return (0, 0)

    return (suffix, suffix)


def image_data_uri(base64_source: bytes) -> str:
    """≙ ``image_data_uri`` (``:564-572``) — la URL ``data:`` de RFC 2397
    para cualquier imagen soportada (PNG, GIF, JPG, SVG, WEBP); PNG cuando el
    primer byte no delata el tipo.
    """
    return 'data:image/%s;base64,%s' % (
        FILETYPE_BASE64_MAGICWORD.get(base64_source[:1], 'png'),
        base64_source.decode(),
    )


def get_saturation(rgb):
    """≙ ``get_saturation`` (``:575-584``) — la saturación HSL de un RGB."""
    c_max = max(rgb) / 255
    c_min = min(rgb) / 255
    d = c_max - c_min
    return 0 if d == 0 else d / (1 - abs(c_max + c_min - 1))


def get_lightness(rgb):
    """≙ ``get_lightness`` (``:587-593``) — la luminosidad HSL de un RGB."""
    return (max(rgb) + min(rgb)) / 2 / 255


def hex_to_rgb(hx):
    """≙ ``hex_to_rgb`` (``:596-598``) — ``'#rrggbb'`` a tupla RGB."""
    return tuple([int(hx[i:i + 2], 16) for i in range(1, 6, 2)])


def rgb_to_hex(rgb):
    """≙ ``rgb_to_hex`` (``:601-603``) — tupla o lista RGB a ``'#rrggbb'``."""
    return '#' + ''.join([(hex(c).split('x')[-1].zfill(2)) for c in rgb])
