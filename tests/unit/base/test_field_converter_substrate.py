r"""Sonda: los 21 conversores de campo, ¿quién formatea y con qué del stack?

Directiva del ejecutor 2026-08-29: *"si es que no, entonces analiza los
binarios de nuestro stack, genera los documentos de pruebas, y documenta"*.

El análisis :doc:`docs: analisis-construir-lo-que-qweb-hace-con-nuestro-stack`
declaró para la pieza 4 que *"el grueso ya está en Django:
``django.utils.formats``, ``django.utils.timesince``, ``get_FOO_display()``"*.
Esta sonda mide dos cosas distintas, y la segunda contradice a la primera:

1. **Django SÍ lo trae** — los tres símbolos existen en el binario instalado y
   hacen lo que la tabla dice.
2. **Y el árbol NO los usa**: ``ir_field_converters.py`` importa ``escape`` y
   ``mark_safe``, y nada de ``django.utils.formats``. Cinco conversores
   **delegan al cliente** con su razón escrita.

Las dos son ciertas a la vez y no se contradicen: la delegación es una
**divergencia elegida**, no una incapacidad. Esta sonda la prueba midiendo que
la alternativa existía — un control que sólo comprobara la delegación no
distinguiría «se eligió» de «no había con qué».

*Métrica:* la presencia y la conducta de los símbolos de formateo en Django
6.0.5, y la clasificación por AST de los 21 ``value_to_html`` del árbol.
*Ciega a:* si el formateo del cliente coincide con el de la source para una
locale dada — eso vive en ``ui`` y no se mide desde aquí.
"""
import ast
import datetime
import pathlib

import pytest
from django.utils import formats, timesince

from addons.base.models import ir_field_converters
from addons.base.models.ir_ui_view import IrUiView

CONVERTERS = pathlib.Path(ir_field_converters.__file__)

#: Los cinco que delegan, con a quién. Se declara aquí para que la sonda falle
#: si alguno cambia de bando sin que nadie lo note.
DELEGATED = {
    'IrFieldConverterImage': 'cliente',
    'IrFieldConverterMonetary': 'cliente',
    'IrFieldConverterRelative': 'cliente',
    'IrFieldConverterBarcode': 'cliente',
    'IrFieldConverterTemplate': 'compilador no portado',
}


def classify():
    """Cada clase del archivo por quién resuelve su ``value_to_html``."""
    tree = ast.parse(CONVERTERS.read_text(encoding='utf-8'))
    out = {}
    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
        method = next((f for f in cls.body
                       if isinstance(f, ast.FunctionDef) and f.name == 'value_to_html'), None)
        if method is None:
            out[cls.name] = 'hereda'
        elif 'NotImplementedError' in ast.dump(method):
            out[cls.name] = 'delega'
        else:
            out[cls.name] = 'formatea'
    return out


class TestTheFamilyIsWhatTheReferenceDeclares:

    def test_there_are_twenty_one_classes(self):
        assert len(classify()) == 21

    def test_fourteen_format_here_two_inherit_and_five_delegate(self):
        split = classify()
        counts = {v: sum(1 for x in split.values() if x == v) for v in set(split.values())}
        assert counts == {'formatea': 14, 'hereda': 2, 'delega': 5}, counts

    def test_the_five_that_delegate_are_the_declared_ones(self):
        assert {k for k, v in classify().items() if v == 'delega'} == set(DELEGATED)


class TestEveryDelegationNamesItsReason:
    """Una delegación sin razón escrita es un hueco disfrazado de decisión."""

    @pytest.mark.parametrize('name', sorted(DELEGATED))
    def test_it_raises_with_a_message_that_says_who_does_it(self, name):
        cls = getattr(ir_field_converters, name)
        with pytest.raises(NotImplementedError) as exc:
            cls.value_to_html(1)
        assert len(str(exc.value)) > 40, 'el mensaje no explica nada'


class TestDjangoDidBringTheAlternative:
    """El control que separa «se eligió» de «no había con qué».

    Si estos casos cayeran, las cinco delegaciones dejarían de ser una
    divergencia elegida y pasarían a ser una incapacidad — y el desenlace
    correcto sería otro. Por eso se miden.
    """

    def test_django_formats_a_date_by_locale(self):
        assert formats.date_format(datetime.date(2026, 8, 29), 'Y-m-d') == '2026-08-29'

    def test_django_formats_a_number_by_locale(self):
        assert formats.number_format(1234.5, decimal_pos=2) in ('1234.50', '1,234.50')

    def test_django_brings_the_relative_converter_that_relative_delegates(self):
        now_ = datetime.datetime(2026, 8, 29, 12, 0)
        assert timesince.timesince(now_ - datetime.timedelta(days=2), now=now_).strip() \
            .startswith('2')

    def test_the_selection_label_comes_from_the_orm_not_from_the_converter(self):
        # Sobre un modelo REAL del arbol, no uno fabricado aqui: `IrUiView.type`
        # declara `VIEW_TYPE_CHOICES`, y el ORM le genera el descriptor.
        assert IrUiView(type='qweb').get_type_display() == 'QWeb'


class TestWhatTheTreeActuallyImports:
    """La contradicción, medida: la tabla propone Django y el código no lo usa."""

    def test_the_module_does_not_import_django_formats(self):
        source = CONVERTERS.read_text(encoding='utf-8')
        assert 'django.utils.formats' not in source
        assert 'django.utils.timesince' not in source

    def test_what_it_does_import_is_escaping_only(self):
        source = CONVERTERS.read_text(encoding='utf-8')
        assert 'from django.utils.html import escape' in source
        assert 'from django.utils.safestring import mark_safe' in source


class TestTheFourteenThatFormatHereDoItWithoutQweb:

    def test_date_comes_out_in_iso_and_that_is_the_declared_contract(self):
        assert ir_field_converters.IrFieldConverterDate.value_to_html(
            datetime.date(2026, 8, 29)) == '2026-08-29'

    def test_float_time_turns_fractional_hours_into_hh_mm(self):
        assert ir_field_converters.IrFieldConverterFloat_Time.value_to_html(1.5) == '01:30'

    def test_the_empty_value_comes_out_empty_not_as_none(self):
        assert ir_field_converters.IrFieldConverterDate.value_to_html(None) == ''
