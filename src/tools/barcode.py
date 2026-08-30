"""Códigos de barras — dígito verificador, validación y raster a PNG.

Adaptación de Odoo ``odoo/tools/barcode.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 5 de 5
====================================

Medido sobre ``odoo19c: odoo/tools/barcode.py`` (93 líneas): 5 símbolos.

================================================  =====================================
Símbolo de la referencia (línea)                  Aquí
================================================  =====================================
``get_barcode_check_digit`` (48-72)               ``get_barcode_check_digit``
``check_barcode_encoding`` (75-93)                ``check_barcode_encoding``
``BARCODE_SIZES`` (implícito, ``:82-88``)         constante nombrada
``createBarcodeDrawing`` (38-40)                  ``render_barcode_png``
``_init_barcode`` (15-35) · ``get_barcode_font``  divergencia declarada (abajo)
================================================  =====================================

**Dos símbolos de más, y no son porte.** ``render_barcode_image`` e
``image_to_png`` son el corte en dos de ``render_barcode_png``: el gancho de
máscara de ``ir.actions.report.barcode`` post-procesa el dibujo **antes** de
serializarlo, así que necesita un punto donde la imagen exista y los bytes
todavía no. La referencia no los declara porque su ``Drawing`` de ReportLab ya
es ese punto intermedio.

Divergencias declaradas
=========================

**El motor de raster es otro, y por eso dos símbolos no tienen contraparte.**
La referencia rasteriza con ``reportlab.graphics.barcode``, que es su librería
de PDF; este árbol no la integra (decreto del ejecutor: el motor de papel es
nuestro). El raster lo hacen ``python-barcode`` —con el ``ImageWriter`` de
Pillow— y ``qrcode``, que producen PNG y no tocan la generación de PDF.

Los dos símbolos que quedan fuera son **infraestructura de ReportLab**, no
comportamiento del código de barras:

- ``_init_barcode`` toma un ``RLock`` porque la caché de fuentes T1 de
  ReportLab no es *thread-safe* (``:10-13`` lo comenta en la fuente). Sin esa
  caché no hay nada que serializar: copiar el candado sería copiar la cura de
  una enfermedad que este árbol no tiene.
- ``get_barcode_font`` nombra una fuente T1 del catálogo de ReportLab
  (``Courier``, con respaldo ``NimbusMonoPS-Regular``). El texto legible lo
  dibuja ``ImageWriter`` con la fuente que Pillow resuelva.

El **nombre** también diverge, y es deliberado: ``createBarcodeDrawing``
promete un ``Drawing`` de ReportLab que aquí no existe. Devolver bytes bajo
ese nombre mentiría sobre el tipo de retorno, así que el símbolo se nombra por
lo que entrega.

*Métrica:* símbolos de la referencia con contraparte aquí.
*Ciega a:* la **fidelidad visual** del trazado. Que ambos entreguen un PNG
válido del mismo tipo y valor no prueba que un lector de códigos lea los dos
igual; eso se mide con un decodificador, no con un conteo de símbolos, y no
se ha medido.
"""
import io
import re

import barcode
import qrcode
from barcode.errors import BarcodeError
from barcode.writer import ImageWriter
from PIL import Image

__all__ = ['check_barcode_encoding', 'get_barcode_check_digit',
           'render_barcode_image', 'render_barcode_png', 'image_to_png',
           'BARCODE_SIZES']

#: Los cuatro niveles de corrección de error de un QR, con el porcentaje de
#: daño que tolera cada uno — ≙ el comentario de ``barcode``
#: (``odoo19c: odoo/addons/base/models/ir_actions_report.py:695-700``).
_QR_ERROR_LEVELS = {
    'L': qrcode.constants.ERROR_CORRECT_L,   # hasta 7 % de daño (por defecto)
    'M': qrcode.constants.ERROR_CORRECT_M,   # hasta 15 % (lo exige l10n_ch)
    'Q': qrcode.constants.ERROR_CORRECT_Q,   # hasta 25 %
    'H': qrcode.constants.ERROR_CORRECT_H,   # hasta 30 %
}

#: El vocabulario de tipos de la referencia es el de ReportLab; el de
#: ``python-barcode`` no coincide en tres nombres. La tabla los traduce en vez
#: de renombrar el contrato: quien llama sigue pidiendo ``Code128``.
_BARCODE_TYPE_NAMES = {
    'Code128': 'code128',
    'Code39': 'code39',
    'EAN8': 'ean8',
    'EAN13': 'ean13',
    'UPCA': 'upca',
    'ITF': 'itf',
}

#: ≙ el diccionario ``barcode_sizes`` de ``check_barcode_encoding``
#: (``odoo19c: odoo/tools/barcode.py:82-88``). Se nombra en vez de quedar
#: dentro de la función porque los consumidores lo consultan (``stock``,
#: ``barcodes_gs1_nomenclature``).
BARCODE_SIZES = {
    'ean8': 8,
    'ean13': 13,
    'gtin14': 14,
    'upca': 12,
    'sscc': 18,
}


def get_barcode_check_digit(numeric_barcode: str) -> int:
    """≙ ``get_barcode_check_digit`` (``odoo19c: odoo/tools/barcode.py:48-72``).

    Calcula el dígito verificador según la especificación GTIN, común a
    EAN-8, EAN-13, UPC-A, GTIN-14 y SSCC.

    El algoritmo pondera ×3 y ×1 alternando posiciones. Dos detalles del
    cuerpo, que la referencia comenta y no son cosméticos:

    - se **quita** el dígito verificador antes de calcular (``[-2::-1]``), o
      interferiría con su propio cálculo;
    - se **invierte** el código, para que el grupo par/impar de cada dígito no
      dependa de la longitud total del código.
    """
    even = odd = 0
    code = numeric_barcode[-2::-1]
    for position, digit in enumerate(code):
        if position % 2 == 0:
            even += int(digit)
        else:
            odd += int(digit)
    total = even * 3 + odd
    return (10 - total % 10) % 10


def check_barcode_encoding(barcode: str, encoding: str) -> bool:
    """≙ ``check_barcode_encoding`` (``odoo19c: odoo/tools/barcode.py:75-93``).

    ``True`` si el código está bien formado en esa codificación: longitud
    exacta, sólo dígitos y dígito verificador correcto.

    La condición extra de EAN-13 —que no empiece por ``0``— no es un capricho:
    un EAN-13 con cero inicial **es** un UPC-A de 12 dígitos con relleno, y
    aceptarlo como EAN-13 confundiría las dos codificaciones.
    """
    encoding = encoding.lower()
    if encoding == 'any':
        return True
    size = BARCODE_SIZES[encoding]
    return bool(
        (encoding != 'ean13' or barcode[0] != '0')
        and len(barcode) == size
        and re.match(r'^\d+$', barcode)
        and get_barcode_check_digit(barcode) == int(barcode[-1])
    )


def render_barcode_png(barcode_type, value, width=600, height=100,
                       human_readable=False, quiet=True, bar_border=4,
                       bar_level='L'):
    """≙ ``createBarcodeDrawing`` (``odoo19c: odoo/tools/barcode.py:38-40``).

    Devuelve el PNG del código, ya escalado a ``width`` × ``height``.

    **Divergencia de mecanismo, con su razón.** La referencia delega en
    ``reportlab.graphics.barcode``, que es su librería de PDF; este árbol no
    la integra (decreto del ejecutor: el motor de papel es nuestro). El
    contrato que sí se conserva es el que consume ``ir.actions.report``:
    entra un tipo y un valor, sale un PNG del tamaño pedido.

    De ahí salen los dos únicos cambios de forma:

    - **el nombre.** ``createBarcodeDrawing`` promete un ``Drawing`` de
      ReportLab, que aquí no existe; devolver bytes bajo ese nombre sería
      mentir sobre el tipo de retorno. Se nombra por lo que entrega.
    - **el candado ``RLock`` y ``_init_barcode`` no se portan.** Existen
      porque la caché de fuentes T1 de ReportLab no es *thread-safe*
      (``:10-13`` lo comenta). Sin esa caché no hay nada que serializar:
      copiar el candado sería copiar la cura de una enfermedad que este
      árbol no tiene.

    ``get_barcode_font`` tampoco se porta, por lo mismo: nombra una fuente T1
    del catálogo de ReportLab. El texto legible lo dibuja ``ImageWriter`` con
    la fuente que Pillow resuelva.
    """
    return image_to_png(render_barcode_image(
        barcode_type, value, width=width, height=height,
        human_readable=human_readable, quiet=quiet, bar_border=bar_border,
        bar_level=bar_level))


def render_barcode_image(barcode_type, value, width=600, height=100,
                         human_readable=False, quiet=True, bar_border=4,
                         bar_level='L'):
    """La imagen del código, ya escalada — el paso previo a serializarla.

    Existe porque el gancho de máscara de ``ir.actions.report.barcode``
    post-procesa el dibujo **antes** de convertirlo a bytes: la referencia le
    entrega el ``Drawing`` de ReportLab, y aquí le entrega la imagen de
    Pillow. Sin este corte el gancho no tendría dónde morder.

    **Traduce el error de la librería a ``ValueError``**, que es lo que
    ``createBarcodeDrawing`` alza y lo que su llamador atrapa
    (``except (ValueError, AttributeError)``). ``python-barcode`` tiene su
    propia jerarquía (``BarcodeError``) y ``Code128('')`` alza un
    ``IndexError``; dejarlos pasar rompería el respaldo a ``Code128`` de la
    fuente, que es comportamiento, no forma.
    """
    try:
        if barcode_type == 'QR':
            code = qrcode.QRCode(
                error_correction=_QR_ERROR_LEVELS.get(
                    bar_level, qrcode.constants.ERROR_CORRECT_L),
                border=bar_border,
                box_size=10,
            )
            code.add_data(value)
            code.make(fit=True)
            image = code.make_image().convert('RGB')
        else:
            name = _BARCODE_TYPE_NAMES.get(barcode_type, barcode_type).lower()
            barcode_class = barcode.get_barcode_class(name)
            buffer = io.BytesIO()
            barcode_class(value, writer=ImageWriter()).write(buffer, {
                'module_height': 10.0,
                'quiet_zone': 6.5 if quiet else 0.0,
                'write_text': bool(human_readable),
                'font_size': 10,
                'text_distance': 3.0,
            })
            buffer.seek(0)
            image = Image.open(buffer).convert('RGB')
    except (BarcodeError, IndexError) as error:
        raise ValueError(str(error)) from error

    return image.resize((width, height), Image.LANCZOS)


def image_to_png(image):
    """Serializa a PNG la imagen que ``render_barcode_image`` devuelve."""
    output = io.BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()
