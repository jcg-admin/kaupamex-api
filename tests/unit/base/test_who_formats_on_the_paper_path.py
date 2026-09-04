r"""Quién formatea el valor cuando no hay ``ui`` — el conversor, en el servidor.

Directiva del ejecutor 2026-08-30: completar las piezas faltantes con el
criterio de las dos categorías —*el stack lo trae hecho* frente a *el stack
tiene con qué construirlo*—. Cierre de la tarea **#197**, que
:ref:`h-api-937` dejó abierta.

Aquel hallazgo enumeró tres desenlaces —formatear al interpretar, exponer el
campo ya formateado desde el modelo, o formatear en el helper de libharu— y
**omitió el que la referencia usa**: el conversor formatea, en el servidor,
en la capa ``ir.qweb.field.*``. Se omitió porque la pieza 4 había clasificado
a los conversores como delegadores, y esa clasificación se hizo mirando el
camino del API.

Medido, la delegación nunca fue total: 14 de los 21 ya formatean aquí. Lo que
delegaba era lo **dependiente de idioma**, y su razón declarada —que la
referencia se apoya en ``babel``, ausente— sólo cubre la mitad del caso
monetario: el símbolo y su posición son **campos de** ``res.currency``, no
datos de ``babel``, y los separadores los trae ``django.utils.formats``.

*Métrica:* la salida real de ``value_to_html`` y del intérprete, no el texto
de sus cuerpos.
*Ciega a:* si el formato que sale coincide con el que un lector mexicano
espera para un documento fiscal — eso lo fija el CFDI (tarea #182), no este
archivo.
"""
from decimal import Decimal

import pytest
from django.utils import translation
from lxml import etree

from addons.base import report_template
from addons.base.models import ir_field_converters as conv
from addons.base.models.res_currency import ResCurrency


def peso():
    """Una moneda con símbolo delante, sin tocar la base."""
    return ResCurrency(name='MXN', symbol='$', position='before',
                       rounding=Decimal('0.01'), decimal_places=2)


def euro():
    """Y otra con el símbolo detrás, que es el otro valor de la Selection."""
    return ResCurrency(name='EUR', symbol='\N{EURO SIGN}', position='after',
                       rounding=Decimal('0.01'), decimal_places=2)


def arch(xml):
    return etree.fromstring(xml)


class TestTheMonetaryConverterFormatsHere:
    """Deja de delegar: el importe sale con su símbolo y sus separadores."""

    def test_the_symbol_goes_before_when_the_currency_says_so(self):
        html = conv.IrFieldConverterMonetary.value_to_html(
            Decimal('1234.5'), {'display_currency': peso()})
        assert html.replace('\N{NO-BREAK SPACE}', ' ') == '$ 1,234.50'

    def test_and_after_when_it_says_after(self):
        html = conv.IrFieldConverterMonetary.value_to_html(
            Decimal('1234.5'), {'display_currency': euro()})
        assert html.replace('\N{NO-BREAK SPACE}', ' ') == '1,234.50 \N{EURO SIGN}'

    def test_the_separators_come_from_the_active_locale_not_from_a_literal(self):
        # El control que discrimina el mecanismo: si los separadores fueran
        # literales del código, las dos locales darían lo mismo. Django trae
        # el dato por locale, que es lo que hace innecesario a ``babel``.
        with translation.override('es'):
            europeo = conv.IrFieldConverterMonetary.value_to_html(
                Decimal('1234.5'), {'display_currency': euro()})
        with translation.override('en'):
            ingles = conv.IrFieldConverterMonetary.value_to_html(
                Decimal('1234.5'), {'display_currency': euro()})
        assert europeo != ingles
        assert '1,234.50' in ingles

    def test_the_amount_is_rounded_by_the_currency_not_truncated(self):
        # La fuente redondea con ``currency.round`` antes de formatear.
        html = conv.IrFieldConverterMonetary.value_to_html(
            Decimal('0.005'), {'display_currency': peso()})
        assert html.replace('\N{NO-BREAK SPACE}', ' ') == '$ 0.01'

    def test_without_a_currency_it_still_refuses_and_says_which_option(self):
        # No se inventa una moneda por defecto: un importe sin moneda no tiene
        # forma presentable, y callarlo daría un número desnudo en el papel.
        with pytest.raises(ValueError, match='display_currency'):
            conv.IrFieldConverterMonetary.value_to_html(Decimal('1'), {})

    def test_an_empty_value_is_still_empty(self):
        assert conv.IrFieldConverterMonetary.value_to_html(
            None, {'display_currency': peso()}) == ''


class TestTheDescriptorRoutesToTheConverter:
    """``<field widget="…">`` — el cableado que faltaba, no el formateo.

    Es el mismo hueco que la tarea #194 cerró para ``<call>``: la pieza estaba
    construida y su único consumidor de producción no la llamaba.
    """

    def test_a_field_with_a_widget_goes_through_its_converter(self):
        d = report_template.interpret_descriptor(
            arch('<descriptor><field name="m" value="importe" '
                 'widget="monetary"/></descriptor>'),
            {'importe': Decimal('1234.5'), 'moneda': peso()},
            widget_options={'monetary': {'display_currency': peso()}})
        assert d['m'].replace('\N{NO-BREAK SPACE}', ' ') == '$ 1,234.50'

    def test_the_widget_name_resolves_the_reference_model_name(self):
        # ``ir.qweb.field.`` + widget, como despacha la fuente
        # (``odoo19c: ir_qweb.py:2784``).
        assert (report_template.converter_for('integer')
                is conv.IrFieldConverterInteger)
        assert (report_template.converter_for('monetary')
                is conv.IrFieldConverterMonetary)

    def test_an_unknown_widget_falls_back_to_the_base_converter(self):
        # La fuente cae a ``ir.qweb.field`` cuando el modelo no existe; no
        # levanta. Se porta esa elección.
        assert (report_template.converter_for('no_existe')
                is conv.IrFieldConverter)

    def test_a_field_without_widget_keeps_rendering_dtl_text(self):
        # El control que impide que el cableado cambie el camino del API: sin
        # ``widget`` el campo sigue saliendo por DTL, crudo. ``1234.5`` y no
        # ``1,234.50``: el ``str()`` del Decimal no rellena el segundo decimal
        # ni pone separador — que es justo lo que el conversor sí hace, así
        # que las dos salidas se distinguen a simple vista.
        d = report_template.interpret_descriptor(
            arch('<descriptor><field name="m">{{ importe }}</field></descriptor>'),
            {'importe': Decimal('1234.5')})
        assert d == {'m': '1234.5'}

    def test_a_widget_without_value_path_is_refused(self):
        with pytest.raises(report_template.InvalidReportTemplate,
                           match="widget.*needs a 'value' path"):
            report_template.interpret_descriptor(
                arch('<descriptor><field name="m" widget="integer">x'
                     '</field></descriptor>'), {})
