r"""Sonda: el sustrato de traducción de nuestro stack frente al flujo i18n.

Directiva del ejecutor 2026-08-29: *"vamos a crear analisis del como lo hariamos
con nuestro stack, uno por uno"* + *"vas a analizar los binarios y crear
pruebas"*.

El trazado del flujo i18n
(``docs: analisis-flujo-i18n-en-odoo-tools.rst``) midió que ``_()`` está portado
y lo llaman 141 archivos, con **0 catálogos** en el árbol. Con el catálogo
vacío ``gettext`` devuelve siempre el ``msgid``, así que **ningún caso que use
sólo el árbol puede distinguir «traduce» de «no hay nada que traducir»** — es
sub-patrón D de ``metrica-decide-la-conclusion.md``.

Esta sonda rompe esa ceguera **construyendo un catálogo real** en un directorio
temporal. El ``.mo`` se escribe con ``struct``, no con ``msgfmt``: las
herramientas de gettext **no están instaladas en este contenedor** (medido con
``command -v msgfmt xgettext msgmerge`` → sin salida), y depender de ellas
volvería la sonda no reproducible.

*Métrica:* la conducta de ``django.utils.translation`` y de ``tools.translate._``
contra un catálogo compilado a mano, más la superficie de ``trans_real``.
*Ciega a:* la extracción — que el ``.po`` se genere bien desde el fuente es otro
eje, y hoy no se puede medir aquí por la ausencia de ``xgettext``.
"""
import os
import pathlib
import struct

import pytest
from django.apps import apps
from django.test import override_settings
from django.utils import translation
from django.utils.translation import trans_real
from django.views.i18n import JavaScriptCatalog, JSONCatalog

from config import urls
from tools.translate import _

#: Los dos mensajes del catálogo de prueba: uno simple y otro con marcador de
#: formato, que es el que mide el ORDEN traducir-luego-formatear.
CATALOG = {'Hello': 'Hola', 'Delay on %s': 'Retraso en %s'}


def write_mo(path, entries):
    """Escribe un catálogo ``.mo`` mínimo — el formato es un índice y dos blobs.

    Se implementa aquí en vez de invocar ``msgfmt`` porque las herramientas de
    gettext no están instaladas; el formato está fijado por GNU gettext y su
    número mágico es ``0x950412de``.
    """
    keys = sorted(entries)
    offsets, ids, strings = [], b'', b''
    for key in keys:
        value = entries[key].encode('utf-8')
        key_bytes = key.encode('utf-8')
        offsets.append((len(ids), len(key_bytes), len(strings), len(value)))
        ids += key_bytes + b'\0'
        strings += value + b'\0'
    key_start = 7 * 4 + 16 * len(keys)
    value_start = key_start + len(ids)
    key_offsets, value_offsets = [], []
    for id_offset, id_length, string_offset, string_length in offsets:
        key_offsets += [id_length, id_offset + key_start]
        value_offsets += [string_length, string_offset + value_start]
    output = struct.pack('Iiiiiii', 0x950412de, 0, len(keys),
                         7 * 4, 7 * 4 + len(keys) * 8, 0, 0)
    output += struct.pack('i' * len(key_offsets), *key_offsets)
    output += struct.pack('i' * len(value_offsets), *value_offsets)
    pathlib.Path(path).write_bytes(output + ids + strings)


@pytest.fixture
def locale_dir(tmp_path):
    """Un directorio de catálogos con el idioma ficticio ``xx`` poblado."""
    messages = tmp_path / 'xx' / 'LC_MESSAGES'
    messages.mkdir(parents=True)
    write_mo(messages / 'django.mo', CATALOG)
    # El catálogo se memoriza por idioma: sin limpiar, un test previo dejaría
    # el suyo y la medición no vería el nuestro.
    trans_real._translations.clear()
    yield str(tmp_path)
    trans_real._translations.clear()


class TestTheCatalogChangesTheResult:
    """El control que el árbol solo no puede dar: con catálogo, `_` traduce."""

    def test_with_a_catalog_the_message_is_translated(self, locale_dir):
        with override_settings(LOCALE_PATHS=[locale_dir], USE_I18N=True):
            with translation.override('xx'):
                assert str(_('Hello')) == 'Hola'

    def test_without_the_active_language_it_falls_back_to_the_source(self, locale_dir):
        # El par de control: mismo catálogo, otro idioma activo. Si este caso
        # también dijera 'Hola', el anterior no estaría midiendo el catálogo.
        with override_settings(LOCALE_PATHS=[locale_dir], USE_I18N=True):
            with translation.override('en'):
                assert str(_('Hello')) == 'Hello'

    def test_it_translates_first_and_formats_afterwards(self, locale_dir):
        # El orden de la referencia (odoo19c: odoo/tools/translate.py:447):
        # lo que se busca en el catálogo es la plantilla CON su marcador, para
        # que el traductor pueda reordenarlo en su idioma.
        with override_settings(LOCALE_PATHS=[locale_dir], USE_I18N=True):
            with translation.override('xx'):
                assert str(_('Delay on %s', 'X')) == 'Retraso en X'


class TestTheLazinessIsReal:
    """`_` devuelve un perezoso: el idioma lo decide el momento de la lectura."""

    def test_the_same_object_reads_differently_under_two_languages(self, locale_dir):
        with override_settings(LOCALE_PATHS=[locale_dir], USE_I18N=True):
            message = _('Hello')          # declarado UNA vez, fuera de idioma
            with translation.override('xx'):
                translated = str(message)
            with translation.override('en'):
                untranslated = str(message)
        assert (translated, untranslated) == ('Hola', 'Hello')

    def test_it_is_not_a_plain_string(self):
        # Si `_` devolviera `str`, el caso anterior daría el mismo valor dos
        # veces y nadie lo notaría: el idioma habría quedado congelado en la
        # declaración.
        assert not isinstance(_('Hello'), str)


class TestDjangoLooksForCatalogsPerApp:
    """La forma de la referencia -un catálogo por addon- ya está cableada."""

    def test_each_app_contributes_its_own_locale_directory(self):
        # `trans_real.all_locale_paths` añade `<app>/locale` de cada app
        # instalada, condicionado a que el directorio exista. Es la contraparte
        # de `addons/<x>/i18n/` de la referencia: no hace falta LOCALE_PATHS.
        source = pathlib.Path(trans_real.__file__).read_text(encoding='utf-8')
        assert 'locale_path = os.path.join(app_config.path, "locale")' in source
        assert 'if os.path.exists(locale_path):' in source

    def test_today_none_of_our_own_apps_has_one(self):
        # El estado medido, y la razón por la que el catálogo está vacío: no es
        # que Django no sepa dónde buscar, es que el directorio no existe.
        own = [
            config.label for config in apps.get_app_configs()
            if 'site-packages' not in config.path
            and os.path.exists(os.path.join(config.path, 'locale'))
        ]
        assert own == [], own


class TestTheCatalogEndpointForTheUiExists:
    """La contraparte de /web/webclient/translations viene con Django."""

    def test_django_ships_a_json_catalog_view(self):
        assert issubclass(JSONCatalog, JavaScriptCatalog)

    def test_it_is_not_wired_into_our_urlconf_yet(self):
        # Estado, no aspiración: el endpoint existe en el binario y NO está
        # publicado. Es la tarea #186.
        source = pathlib.Path(urls.__file__).read_text(encoding='utf-8')
        assert 'JSONCatalog' not in source
