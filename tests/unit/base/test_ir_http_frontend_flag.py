"""Contrato de ``request.is_frontend`` — la marca de cara pública (#546).

La semántica es la de la fuente: la marca la pone el **despacho** desde lo
que el endpoint declara (``odoo19c: addons/http_routing/models/ir_http.py:375``
— ``request.is_frontend = routing.get('website', False)``), con default
``False`` (``odoo19c: addons/http_routing/__init__.py:11``). Aquí el default
lo estampa ``CompanyContextMiddleware.__call__`` y la promoción la hace su
``process_view`` leyendo el atributo ``is_frontend`` declarado por la vista.

Sin base de datos: el mecanismo es puro objeto-petición + vista despachada.
"""
from django.views.generic import View
from rest_framework.views import APIView

from addons.base.models.ir_http import CompanyContextMiddleware


class _AnonymousUser:
    is_authenticated = False
    company_id = None


class _Request:
    def __init__(self):
        self.user = _AnonymousUser()


def _middleware(capture):
    """Middleware con un ``get_response`` que captura la marca en despacho."""

    def get_response(request):
        capture['is_frontend'] = getattr(request, 'is_frontend', None)
        return 'ok'

    return CompanyContextMiddleware(get_response)


class _FrontendAPIView(APIView):
    """Vista DRF que se declara de cara pública — ≙ ``@route(website=True)``."""

    is_frontend = True


class _BackendAPIView(APIView):
    """Vista DRF sin declaración — backend por omisión."""


class _ExplicitBackendAPIView(APIView):
    """Vista que declara explícitamente NO ser de cara pública."""

    is_frontend = False


class _FrontendGenericView(View):
    """CBV de Django (expone ``view_class``, no ``cls``)."""

    is_frontend = True


class TestDefaultStamp:
    """El default lo pone ``__call__`` — el papel del post-init de la fuente."""

    def test_request_is_stamped_false_before_dispatch(self):
        capture = {}
        middleware = _middleware(capture)
        middleware(_Request())
        assert capture['is_frontend'] is False

    def test_unresolved_request_stays_false(self):
        # Divergencia declarada: la fuente pone True en NotFound porque su
        # frontend renderiza el 404 con el sitio; aquí el 404 es JSON y sin
        # vista despachada ``process_view`` nunca corre — queda el default.
        request = _Request()
        capture = {}
        _middleware(capture)(request)
        assert request.is_frontend is False


class TestProcessView:
    """El estampado desde la declaración de la vista despachada — ≙ ``_match``."""

    def _stamp(self, view_func):
        request = _Request()
        result = CompanyContextMiddleware(lambda req: 'ok').process_view(
            request, view_func, (), {})
        return request, result

    def test_drf_view_declaring_frontend_marks_the_request(self):
        request, _ = self._stamp(_FrontendAPIView.as_view())
        assert request.is_frontend is True

    def test_drf_view_without_declaration_marks_backend(self):
        request, _ = self._stamp(_BackendAPIView.as_view())
        assert request.is_frontend is False

    def test_drf_view_declaring_false_marks_backend(self):
        request, _ = self._stamp(_ExplicitBackendAPIView.as_view())
        assert request.is_frontend is False

    def test_django_generic_view_declaring_frontend_marks_the_request(self):
        request, _ = self._stamp(_FrontendGenericView.as_view())
        assert request.is_frontend is True

    def test_function_view_with_attribute_marks_the_request(self):
        def page_view(request):
            return 'ok'

        page_view.is_frontend = True
        request, _ = self._stamp(page_view)
        assert request.is_frontend is True

    def test_plain_function_view_marks_backend(self):
        def api_view(request):
            return 'ok'

        request, _ = self._stamp(api_view)
        assert request.is_frontend is False

    def test_process_view_returns_none(self):
        # El hook marca, no responde: un retorno distinto de None haría que
        # Django lo tomara por la respuesta y saltara la vista real.
        _, result = self._stamp(_FrontendAPIView.as_view())
        assert result is None

    def test_truthy_declaration_normalizes_to_bool(self):
        def sloppy_view(request):
            return 'ok'

        sloppy_view.is_frontend = 1
        request, _ = self._stamp(sloppy_view)
        assert request.is_frontend is True


class TestEndToEndOrder:
    """Default en ``__call__`` + promoción en ``process_view`` componen bien."""

    def test_default_then_promotion_inside_the_same_request(self):
        request = _Request()
        seen = {}

        middleware_holder = {}

        def get_response(req):
            # Simula el punto en que Django, con la URL ya resuelta, invoca
            # process_view antes de la vista — el orden real del handler.
            middleware_holder['mw'].process_view(
                req, _FrontendAPIView.as_view(), (), {})
            seen['is_frontend'] = req.is_frontend
            return 'ok'

        middleware = CompanyContextMiddleware(get_response)
        middleware_holder['mw'] = middleware
        middleware(request)
        assert seen['is_frontend'] is True

    def test_view_declaration_does_not_leak_between_requests(self):
        # Un worker atiende peticiones en serie sobre el mismo hilo; la marca
        # viaja en la petición, no en estado del middleware, así que la
        # siguiente petición nace backend aunque la anterior fuera frontend.
        middleware = CompanyContextMiddleware(lambda req: 'ok')

        first = _Request()
        middleware.process_view(first, _FrontendAPIView.as_view(), (), {})
        assert first.is_frontend is True

        second = _Request()
        capture = {}

        def get_response(req):
            capture['is_frontend'] = req.is_frontend
            return 'ok'

        CompanyContextMiddleware(get_response)(second)
        assert capture['is_frontend'] is False
