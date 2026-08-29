r"""Sonda: el diferimiento de la respuesta en nuestro stack frente al Flujo A.

Directiva del ejecutor 2026-08-29: *"vamos a crear analisis del como lo
hariamos con nuestro stack, uno por uno"* + *"vas a analizar los binarios y
crear pruebas"*.

El Flujo A de la referencia
(``docs: analisis-flujo-a-la-pagina-web-en-odoo-tools.rst``) difiere el
renderizado en cuatro eslabones: el endpoint devuelve un ``Response`` con la
plantilla dentro, ``is_qweb`` delata que está pendiente, el **dispatch** —no la
vista— lo aplana, y sólo entonces existe el cuerpo.

Esta sonda mide que **Django y DRF ya traen ese mismo diseño**, eslabón por
eslabón, para poder declarar que no hay nada que portar del Flujo A sin
afirmarlo de memoria. Se mide contra los paquetes instalados, no contra la
documentación:

.. list-table::
   :header-rows: 1

   * - Eslabón de la referencia
     - Contraparte medida aquí
   * - ``Response(template=…)`` sin renderizar
     - ``rest_framework.response.Response(SimpleTemplateResponse)``
   * - ``is_qweb`` = ``template is not None``
     - ``is_rendered`` + ``ContentNotRenderedError``
   * - ``flatten()``
     - ``SimpleTemplateResponse.render()``
   * - ``if …is_qweb: result.flatten()`` en ``ir_http._dispatch``
     - ``django.core.handlers.base`` — ``response.render()``
   * - ``type='http'`` fija el mimetype
     - negociación de contenido → ``accepted_renderer``

*Métrica:* la superficie declarada por los paquetes instalados y la conducta
observada al ejercitarla.
*Ciega a:* si algún endpoint nuestro rompe el patrón devolviendo un
``HttpResponse`` ya renderizado — eso lo cubre el censo de
:class:`TestOurApiSurfaceStaysJsonOnly`, con otro instrumento.
"""
import pathlib

import pytest
from django.conf import settings
from django.core.handlers import base as django_handler
from django.http import Http404
from django.template.response import ContentNotRenderedError, SimpleTemplateResponse
from django.test import RequestFactory
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer, StaticHTMLRenderer
from rest_framework.response import Response

from config.urls import serve_spa


class TestTheResponseIsDeferredLikeTheReference:
    """El eslabón 2 del Flujo A: lo que la vista devuelve no es el cuerpo."""

    def test_the_drf_response_is_a_django_template_response(self):
        # ≙ la referencia envuelve plantilla + contexto en un Response que
        # todavía no es HTML (odoo19c: odoo/http.py:2131).
        assert issubclass(Response, SimpleTemplateResponse)

    def test_reading_the_body_before_rendering_raises(self):
        # ≙ `is_qweb`: la respuesta se sabe pendiente. Aquí no hay bandera —
        # el acceso al cuerpo levanta, que es una guarda más fuerte.
        response = Response({'a': 1})
        assert response.is_rendered is False
        with pytest.raises(ContentNotRenderedError):
            response.content

    def test_the_headers_can_be_mutated_while_the_body_does_not_exist(self):
        # Es la propiedad exacta que el controlador del paso 1 explota:
        #   response = request.render('web.login', values)
        #   response.headers['Cache-Control'] = 'no-cache'
        response = Response({'a': 1})
        response['Cache-Control'] = 'no-cache'
        response['X-Frame-Options'] = 'SAMEORIGIN'
        assert response.is_rendered is False
        assert response['Cache-Control'] == 'no-cache'


class TestTheFlatteningBelongsToTheHandler:
    """El eslabón 4: quien aplana no es la vista sino la capa de despacho."""

    def _view(self, renderer):
        @api_view(['GET'])
        @permission_classes([AllowAny])
        @renderer_classes([renderer])
        def probe(request):
            response = Response({'ok': True})
            # La vista devuelve SIN renderizar, igual que el endpoint de la
            # referencia; el aplanado ocurre después de este `return`.
            assert response.is_rendered is False
            response['X-Probe'] = 'set-before-flatten'
            return response
        return probe

    def test_the_response_arrives_rendered_and_keeps_the_header(self):
        request = RequestFactory().get('/probe')
        response = self._view(JSONRenderer)(request)
        # `finalize_response` fijó el renderer; el cuerpo ya se puede leer.
        assert response.accepted_renderer.__class__ is JSONRenderer
        assert response.rendered_content == b'{"ok":true}'
        assert response['X-Probe'] == 'set-before-flatten'

    def test_django_handler_declares_the_render_hook(self):
        # ≙ ir_http._dispatch:355 — `if …is_qweb: result.flatten()`.
        # Aquí la condición es `hasattr(response, "render")`, y vive en el
        # handler de Django, no en un modelo.
        source = pathlib.Path(django_handler.__file__).read_text(encoding='utf-8')
        assert 'hasattr(response, "render")' in source
        assert 'response.render()' in source


class TestContentNegotiationPlaysTheDispatcherRole:
    """El eslabón 7: quién decide el mimetype."""

    def test_the_declared_renderer_decides_the_content_type(self):
        # ≙ `type='http'` vs `type='jsonrpc'` en el decorador de la referencia:
        # el mimetype lo fija lo que el endpoint declara, no el motor.
        request = RequestFactory().get('/probe')

        @api_view(['GET'])
        @permission_classes([AllowAny])
        @renderer_classes([StaticHTMLRenderer])
        def html_probe(_request):
            return Response('<p>hola</p>')

        response = html_probe(request)
        assert response['Content-Type'] == 'text/html; charset=utf-8'
        assert response.rendered_content == b'<p>hola</p>'

    def test_the_project_default_is_json_only(self):
        # El default del proyecto declara UN renderer, y es JSON: por eso
        # ningún endpoint cae en `text/html` por omisión.
        assert settings.REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] == [
            'rest_framework.renderers.JSONRenderer',
        ]


class TestOurApiSurfaceStaysJsonOnly:
    """Censo: ninguna vista de la API declara un renderer de HTML."""

    def test_no_view_declares_an_html_renderer(self):
        root = pathlib.Path(settings.BASE_DIR)
        offenders = [
            f"{p.relative_to(root)}:{n}"
            for p in root.rglob('*.py')
            if 'test' not in p.parts and '.venv' not in p.parts
            for n, line in enumerate(p.read_text(encoding='utf-8').splitlines(), 1)
            if 'TemplateHTMLRenderer' in line or 'StaticHTMLRenderer' in line
        ]
        assert offenders == [], offenders


class TestTheSpaEntryPointIsOutsideTheApi:
    """El HTML que sí servimos no lo genera una plantilla: es un archivo."""

    def test_serving_the_spa_without_a_build_fails_loudly(self, settings):
        # La guarda mide su propio fallo: sin build, 404 con el motivo escrito,
        # no una página vacía que parezca sana.
        settings.UI_DIST = '/ruta/que/no/existe'
        with pytest.raises(Http404, match='UI build no encontrado'):
            serve_spa(RequestFactory().get('/cualquier/ruta'))
