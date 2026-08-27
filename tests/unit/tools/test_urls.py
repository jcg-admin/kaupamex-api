"""``tools.urls`` — la unión estricta, contra los ejemplos de la fuente.

Fiel a ``odoo19c: odoo/tools/urls.py`` (``odoo-tools``, LGPL-3). Lógica pura,
sin base de datos. Los casos cubren lo que hace a este ``urljoin`` distinto
del RFC 3986 de ``urllib.parse``: unión tipo ``base + '/' + extra``, query
fusionada, rechazo de esquema/host ajenos, segmentos punto (también
codificados ``%2e%2e``) y la guarda del prefijo backslash.
"""
import pytest

from tools.urls import _contains_dot_segments, urljoin

pytestmark = pytest.mark.unit


# -- unión estricta (los ejemplos del docstring de la fuente) ----------------

def test_joins_base_and_relative_path():
    assert (urljoin('https://api.example.com/v1/?bar=fiz', '/users/42?bar=bob')
            == 'https://api.example.com/v1/users/42?bar=bob')


def test_merges_query_onto_base_path():
    assert (urljoin('https://api.example.com/data/', '/?lang=fr')
            == 'https://api.example.com/data/?lang=fr')


def test_collapses_duplicate_slashes():
    # La normalización foo//bar -> foo/bar de la fuente. (Un extra que
    # empiece con '//' no sirve aquí: urlsplit lo lee como netloc y la
    # fuente lo rechaza como host ajeno.)
    assert (urljoin('https://example.com/a/', '/x//y')
            == 'https://example.com/a/x/y')


def test_accepts_absolute_extra_matching_the_base():
    # Una ``extra`` absoluta se admite sólo si coincide esquema, host y
    # prefijo de path con la base.
    assert (urljoin('https://example.com/foo', 'https://example.com/foo/bar')
            == 'https://example.com/foo/bar')


# -- rechazo de esquema/host ajenos ------------------------------------------

def test_rejects_foreign_scheme_or_host():
    with pytest.raises(ValueError):
        urljoin('https://example.com/foo', 'http://8.8.8.8/foo')


def test_rejects_same_host_with_foreign_scheme():
    with pytest.raises(ValueError):
        urljoin('https://example.com/foo', 'http://example.com/foo/bar')


def test_rejects_absolute_extra_outside_base_path():
    with pytest.raises(ValueError):
        urljoin('https://example.com/foo', 'https://example.com/otro')


# -- segmentos punto ----------------------------------------------------------

def test_rejects_dot_segments():
    with pytest.raises(ValueError):
        urljoin('https://example.com', '/a/../b')


def test_rejects_encoded_dot_segments():
    # %2e%2e decodifica a '..' — el servidor decodifica antes de resolver.
    with pytest.raises(ValueError):
        urljoin('https://example.com', '/a/%2e%2e/b')


def test_contains_dot_segments_decodes_first():
    assert _contains_dot_segments('/a/%2e%2e/b') is True
    assert _contains_dot_segments('/a/b') is False


# -- guarda del prefijo backslash ---------------------------------------------

def test_strips_backslash_prefix():
    # urljoin('/', '\\example.com/') NO debe resolver absoluto a
    # '//example.com/' en un redirect de navegador — la guarda de la fuente.
    joined = urljoin('/', '\\example.com/')
    assert not joined.startswith('//')


def test_strips_control_character_prefix():
    # El lstrip de la fuente incluye los controles C0 y el espacio.
    joined = urljoin('/', '\t \x00/\\example.com/')
    assert not joined.startswith('//')


# -- contrato de tipos (los asserts de la fuente) -----------------------------

def test_non_string_inputs_are_rejected():
    with pytest.raises(AssertionError):
        urljoin(None, '/a')
    with pytest.raises(AssertionError):
        urljoin('/a', None)
