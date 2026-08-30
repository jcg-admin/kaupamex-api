r"""Sonda: el formato de cable de la API frente al lenguaje de la vista.

Motivo (directiva del ejecutor 2026-08-29): *"si no me equivoco odoo-tools
consume sus vistas en xml, nosotros actualmente enviamos json, lo que
queremos es que si odoo-tools consume sus vistas en xml, nuestra api ya deja
de ser json y tiene que ser xml, como la referencia"*.

La premisa mezcla **dos capas** que la referencia mantiene separadas, y la
sonda las separa aquí para que nadie las vuelva a confundir:

.. list-table::
   :header-rows: 1

   * - Capa
     - En la referencia
     - Aquí
   * - **Lenguaje de la vista** (definición, en servidor)
     - XML en ``ir_ui_view.arch_db``
     - XML en ``arch_db`` — **idéntico**, ver :class:`TestTheViewLanguageIsXml`
   * - **Formato de cable** (lo que viaja por HTTP)
     - **JSON-RPC** — 0 despachadores XML
     - JSON — ver :class:`TestOurWireFormatIsJsonLikeTheReference`

El ``arch`` XML viaja **como cadena dentro de una respuesta JSON**
(``odoo19c: odoo/addons/base/models/ir_ui_view.py:3125`` — ``'arch': arch``,
dentro del ``dict`` que ``get_view`` devuelve). Cambiar nuestro cable a XML
**divergiría** de la referencia en vez de seguirla.

El censo de la referencia NO se mide aquí: este archivo, como su hermano
``test_xml_template_substrate.py``, mide **nuestro** árbol y los paquetes
instalados, que es lo que existe sin depender de que ``odoo-tools`` esté
montado. El censo vive en el hallazgo, con su comando.
"""
import importlib.util
import json
from pathlib import Path

import pytest
from django.conf import settings
from rest_framework.renderers import JSONRenderer

from addons.base.models.ir_ui_view import MODE_PRIMARY, IrUiView

#: La raíz del repo, para leer ``uv.lock`` sin teclear la ruta.
REPO_ROOT = Path(__file__).resolve().parents[3]


class TestOurWireFormatIsJsonLikeTheReference:
    """El cable es JSON, que es lo que la referencia hace con JSON-RPC."""

    def test_the_default_renderer_is_json(self):
        """``DEFAULT_RENDERER_CLASSES`` declara el renderizador JSON."""
        renderers = settings.REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES']
        assert 'rest_framework.renderers.JSONRenderer' in renderers

    def test_no_xml_renderer_is_declared(self):
        """Ningún renderizador declarado nombra XML.

        Es el control que caería si alguien cambiara el cable a XML sin
        pasar por la decisión: el fallo nombraría la clase intrusa.
        """
        renderers = settings.REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES']
        intruders = [name for name in renderers if 'XML' in name.upper()]
        assert intruders == [], f'renderizador XML no decidido: {intruders}'

    def test_no_xml_parser_is_declared(self):
        """Simétrico del anterior sobre el lado de entrada.

        ``DEFAULT_PARSER_CLASSES`` puede no estar declarado — el default de
        DRF (JSON, form, multipart) tampoco trae XML, así que la ausencia de
        la clave es un resultado válido y no un hueco de la medición.
        """
        parsers = settings.REST_FRAMEWORK.get('DEFAULT_PARSER_CLASSES', [])
        intruders = [name for name in parsers if 'XML' in name.upper()]
        assert intruders == [], f'parser XML no decidido: {intruders}'


class TestTheXmlPackageIsNotADeclaredDependency:
    """``djangorestframework-xml`` no está — la decisión #178 sigue abierta.

    DRF **retiró** el soporte XML de su núcleo a un paquete de terceros. Que
    no esté instalado es el estado medido, no una omisión: si algún día un
    endpoint necesita XML sobre HTTP, la decisión es adoptarlo o escribir un
    ``BaseRenderer`` propio, y esta sonda lo declara pendiente.
    """

    def test_the_third_party_package_is_not_installed(self):
        assert importlib.util.find_spec('rest_framework_xml') is None

    def test_the_lock_does_not_declare_it(self):
        lock = (REPO_ROOT / 'uv.lock').read_text()
        assert 'djangorestframework-xml' not in lock


@pytest.mark.django_db
class TestTheViewLanguageIsXml:
    """La vista SÍ se define en XML — y eso no toca el formato de cable."""

    def test_arch_db_is_a_text_column(self):
        """``arch_db`` guarda el XML como texto, como la fuente.

        Un XML almacenado en una columna de texto es lo que permite que
        viaje **como valor de una clave JSON** sin re-serializar nada.
        """
        field = IrUiView._meta.get_field('arch_db')
        assert field.get_internal_type() == 'TextField'

    def test_the_arch_travels_as_a_string_inside_a_json_payload(self):
        """El contrato completo, de punta a punta y sobre un registro real.

        Reproduce lo que ``get_view`` hace en la fuente
        (``odoo19c: ir_ui_view.py:3125`` — ``'arch': arch`` dentro del
        ``dict``): la arquitectura XML se serializa a cadena y **cabe** en
        una respuesta JSON sin dejar de ser XML.

        Cae si ``get_combined_arch`` dejara de devolver una cadena, o si el
        XML no sobreviviera al viaje por JSON.
        """
        view = IrUiView.objects.create(
            name='wire', type='template', key='test.wire', mode=MODE_PRIMARY,
            arch_db='<doc><a t-esc="x"/></doc>',
        )
        arch = view.get_combined_arch()
        assert isinstance(arch, str)

        payload = JSONRenderer().render({'arch': arch, 'id': view.pk})
        assert json.loads(payload)['arch'] == '<doc><a t-esc="x"/></doc>'
