"""Códigos de barras — dígito verificador y validación de codificación.

Adaptación de Odoo ``odoo/tools/barcode.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 3 de 5
====================================

Medido sobre ``odoo19c: odoo/tools/barcode.py`` (93 líneas): 5 símbolos.

===============================================  ======================================
Símbolo de la referencia (línea)                 Aquí
===============================================  ======================================
``get_barcode_check_digit`` (48-72)              ``get_barcode_check_digit``
``check_barcode_encoding`` (75-93)               ``check_barcode_encoding``
``BARCODE_SIZES`` (implícito, ``:82-88``)        constante nombrada
``_init_barcode`` (15-35)                        **divergencia declarada** (abajo)
``createBarcodeDrawing`` (38-40)                 **divergencia declarada**
``get_barcode_font`` (43-46)                     **divergencia declarada**
===============================================  ======================================

Divergencias declaradas
=========================

**Los tres símbolos de renderizado no se portan aquí porque su motor es otro.**
No es «no se puede»: es que en este árbol el dibujo del código de barras no lo
hace ReportLab. La referencia rasteriza con ``reportlab.graphics.barcode`` y
toma un ``RLock`` porque su caché de fuentes T1 no es *thread-safe*; nuestro
motor de PDF es **libharu** (ADR-017), que no comparte esa caché ni ese
candado, así que copiar el bloqueo sería copiar la cura de una enfermedad que
este árbol no tiene.

El renderizador equivalente —``ir.actions.report`` con dibujo de código de
barras sobre libharu— está registrado como tarea **#192**. Hasta que exista,
lo que este módulo entrega es la mitad **aritmética**, que es la que valida
un código y la que ``stock.package.valid_sscc`` consume; la mitad gráfica no
tiene hoy ningún consumidor en el árbol.

*Métrica:* símbolos de la referencia con contraparte aquí.
*Ciega a:* que los dos bloques cubren necesidades distintas — validar un
código y dibujarlo no son el mismo trabajo, y contar «3 de 5» sugiere una
carencia proporcional que no lo es.
"""
import re

__all__ = ['check_barcode_encoding', 'get_barcode_check_digit', 'BARCODE_SIZES']

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
    pares = impares = 0
    codigo = numeric_barcode[-2::-1]
    for posicion, digito in enumerate(codigo):
        if posicion % 2 == 0:
            pares += int(digito)
        else:
            impares += int(digito)
    total = pares * 3 + impares
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
    tamano = BARCODE_SIZES[encoding]
    return bool(
        (encoding != 'ean13' or barcode[0] != '0')
        and len(barcode) == tamano
        and re.match(r'^\d+$', barcode)
        and get_barcode_check_digit(barcode) == int(barcode[-1])
    )
