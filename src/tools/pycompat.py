"""Puentes de compatibilidad — adaptacion de ``odoo19c:
odoo/tools/pycompat.py`` (``odoo-tools@622ddc2a``, LGPL-3 segun el
``__manifest__.py`` de su addon raiz: copia + adaptacion con atribucion
preservada, DEC-KX-03).

Que resuelve: transcodificar un flujo de **bytes** a texto UTF-8 para el CSV,
y llevar un valor cualquiera a ``str``. Los tres simbolos publicos estan
marcados obsoletos desde Odoo 18.0.

**Se portan 5 de 5 simbolos** (``_reader``, ``_writer``, ``csv_reader``,
``csv_writer``, ``to_text``). El archivo aterriza en ``src/tools/`` porque
``src/tools`` ↔ ``odoo/tools`` es una raiz espejada.

Por que entra ahora, siendo obsoleto
=====================================

Porque ``porte-completo-no-parcial.md`` no admite el recorte por juicio: al
portar la raiz espejada se portan **todos** sus archivos, y un modulo que la
referencia conserva —aunque avise— es parte del contrato que este arbol
declara adaptar. Su aviso viaja con el: quien lo llame recibe el mismo
``DeprecationWarning`` que alla, que es la señal de migrar a ``csv`` sobre un
flujo de texto.

El stack lo TRAE — no hay nada que construir
=============================================

CPython puro: ``csv``, ``codecs``, ``io`` y ``warnings``.

Divergencia de mecanismo declarada — ninguna
=============================================

Se porta literal salvo el idioma de docstrings y comentarios. El ``assert``
que rechaza un flujo de texto **se conserva**: es el contrato del simbolo, no
una comprobacion defensiva — sin el, un ``StringIO`` pasaria por el decoder y
fallaria mas adentro con un error que no nombra la causa.
"""
import codecs
import csv
import io
import typing
import warnings

_reader = codecs.getreader('utf-8')
_writer = codecs.getwriter('utf-8')


def csv_reader(stream, **params):
    """Lector CSV sobre un flujo de bytes, transcodificado a UTF-8."""
    warnings.warn(
        "Deprecated since Odoo 18.0: can just use `csv.reader` with a text "
        "stream or use `TextIOWriter` or `codec.getreader` to transcode.",
        DeprecationWarning, stacklevel=2)
    assert not isinstance(stream, io.TextIOBase), \
        "For cross-compatibility purposes, csv_reader takes a bytes stream"
    return csv.reader(_reader(stream), **params)


def csv_writer(stream, **params):
    """Escritor CSV sobre un flujo de bytes, transcodificado a UTF-8."""
    warnings.warn(
        "Deprecated since Odoo 18.0: can just use `csv.writer` with a text "
        "stream or use `TextIOWriter` or `codec.getwriter` to transcode.",
        DeprecationWarning, stacklevel=2)
    assert not isinstance(stream, io.TextIOBase), \
        "For cross-compatibility purposes, csv_writer takes a bytes stream"
    return csv.writer(_writer(stream), **params)


def to_text(source: typing.Any) -> str:
    """Genera un valor de texto a partir de una fuente arbitraria.

    * ``False`` y ``None`` se convierten en cadena vacia
    * el texto pasa tal cual
    * los bytes se decodifican como UTF-8
    * el resto se textifica
    """
    warnings.warn(
        "Deprecated since Odoo 18.0.", DeprecationWarning, stacklevel=2)
    if source is None or source is False:
        return ''

    if isinstance(source, bytes):
        return source.decode()

    if isinstance(source, str):
        return source

    return str(source)
