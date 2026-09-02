"""``ModelConverter`` — el slug de la URL al registro, y de vuelta.

Es la pieza que sustituye a ``werkzeug.routing.BaseConverter`` con la
primitiva equivalente de Django (convertidor de ruta: ``regex`` +
``to_python`` + ``to_url``). Los casos miden el contrato de las dos
direcciones, no que la clase exista.
"""
import re

import pytest

from addons.http_routing.models.ir_http import (
    _UNSLUG_ROUTE_PATTERN,
    ModelConverter,
    model_converter_for,
)


class _Row:
    def __init__(self, pk, display_name='Silla de Oficina'):
        self.pk = pk
        self.display_name = display_name


class _Manager:
    """El ``objects`` mínimo que ``_browse`` usa: ``filter(pk=…).first()``."""

    def __init__(self, rows):
        self._rows = rows

    def filter(self, pk):
        self._match = self._rows.get(pk)
        return self

    def first(self):
        return self._match


class _Model:
    def __init__(self, rows):
        self.objects = _Manager(rows)


@pytest.fixture
def converter(monkeypatch):
    rows = {7: _Row(7), 3: _Row(3, 'Mesa')}
    monkeypatch.setattr(
        'addons.http_routing.models.ir_http.model_by_name',
        lambda name: _Model(rows),
    )
    return model_converter_for('product.template')()


class TestTheRegexAcceptsAReadableSlug:
    """Falla si el ``regex`` siguiera siendo el ``[0-9]+`` de ``base``."""

    @pytest.mark.parametrize('value', ['silla-de-oficina-7', '7', 'ab-7', 'cosa--3'])
    def test_it_matches_a_name_and_an_identifier(self, value):
        assert re.fullmatch(_UNSLUG_ROUTE_PATTERN, value)

    @pytest.mark.parametrize('value', ['silla', '', 'silla-', '--3'])
    def test_it_rejects_what_has_no_identifier(self, value):
        assert not re.fullmatch(_UNSLUG_ROUTE_PATTERN, value)

    def test_a_digits_only_regex_would_not_pass_these(self):
        # Discrimina: el control que el ``regex`` de ``base`` NO pasaría.
        assert not re.fullmatch(r'[0-9]+', 'silla-de-oficina-7')


class TestToPythonResolvesTheRecord:
    """Falla si ``to_python`` devolviera el entero en vez del registro."""

    def test_a_readable_slug_gives_the_row(self, converter):
        assert converter.to_python('silla-de-oficina-7').pk == 7

    def test_a_bare_identifier_gives_the_same_row(self, converter):
        assert converter.to_python('7').pk == 7

    def test_the_raw_value_travels_on_the_instance(self, converter):
        # ≙ ``with_context(_converter_value=value)`` de la fuente.
        assert converter.to_python('silla-de-oficina-7')._converter_value == \
            'silla-de-oficina-7'

    def test_an_unknown_identifier_gives_nothing(self, converter):
        assert converter.to_python('99') is None


class TestTheNegativeIdentifierFallback:
    """``if record.id < 0 and not exists(): record = browse(abs(id))``."""

    def test_a_negative_identifier_falls_back_to_its_absolute(self, converter):
        # -3 no existe; 3 sí. La fuente asume el abs() por culpa del patrón.
        assert converter.to_python('mesa--3').pk == 3

    def test_a_negative_identifier_with_no_absolute_gives_nothing(self, converter):
        assert converter.to_python('cosa--99') is None

    def test_a_positive_identifier_is_not_absolutized(self, converter):
        # Discrimina: sin la guarda ``< 0`` esto también reintentaría.
        assert converter.to_python('99') is None


class TestToUrlIsTheOtherDirection:
    """``to_url`` es ``_slug``: lo que ``reverse()`` pone en la URL."""

    def test_it_writes_the_readable_slug(self, converter):
        assert converter.to_url(_Row(42, 'Silla de Oficina')) == 'silla-de-oficina-42'

    def test_it_round_trips_with_to_python(self, converter):
        assert converter.to_python(converter.to_url(_Row(7))).pk == 7


class TestTheConstructorKeepsTheSourceSignature:
    """La firma es contrato — ``porte-completo-no-parcial.md``."""

    def test_model_and_domain_are_accepted_positionally(self):
        conv = ModelConverter(None, 'product.template', "[('sale_ok','=',True)]")
        assert (conv.model, conv.domain) == (
            'product.template', "[('sale_ok','=',True)]")

    def test_the_default_domain_is_the_empty_one(self):
        assert ModelConverter().domain == '[]'
