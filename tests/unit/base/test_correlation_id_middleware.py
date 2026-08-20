"""Tests unitarios — ``CorrelationIdMiddleware`` (DEC-LOG-07, DEC-AF-11).

Es la mitad que **sobrevive** de ``RequestLogMiddleware``. Aquélla abría la
correlación, medía la petición y escribía una fila de ``RequestLog``; DEC-AF-11
retiró el modelo —su mitad de acceso es trabajo del ``access_log`` del proxy
inverso— y dejó vivo el único trabajo sin otro dueño: abrir y cerrar el
identificador que une ``ir.logging`` con ``BusinessEvent``.

Lo que se verifica:

- abre la correlación antes de la vista y la expone en ``request``,
- la publica en ``X-Correlation-Id``, que es la precondición para unir la línea
  del proxy con la fila de ``ir.logging`` (el ``LogFormat`` del vhost es la
  tarea #55),
- la **limpia** al terminar, incluso si la vista levanta. Sin esa limpieza el
  identificador sobreviviría a la petición dentro del mismo worker de Gunicorn
  (prefork síncrono, un hilo) y las líneas de la siguiente saldrían
  correlacionadas con la anterior,
- no rompe la respuesta si la cabecera no se puede fijar (DEC-LOG-04).

No toca DB: el middleware no persiste nada — ése es justo el cambio.
"""
import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from addons.base.models.ir_http import CorrelationIdMiddleware
from tools.logging_context import clear_correlation_id, get_correlation_id

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def _contexto_limpio():
    clear_correlation_id()
    yield
    clear_correlation_id()


def test_opens_the_correlation_and_exposes_it():
    visto = {}

    def get_response(request):
        visto['en_la_vista'] = get_correlation_id()
        visto['en_el_request'] = request.correlation_id
        return HttpResponse(status=200)

    response = CorrelationIdMiddleware(get_response)(
        RequestFactory().get('/api/v2/catalogue/products/'))

    assert visto['en_la_vista']                              # hay correlación
    assert visto['en_el_request'] == visto['en_la_vista']    # y es la misma
    assert response['X-Correlation-Id'] == visto['en_la_vista']


def test_clears_the_correlation_after_the_response():
    CorrelationIdMiddleware(lambda request: HttpResponse(status=200))(
        RequestFactory().get('/x'))

    assert get_correlation_id() is None


def test_clears_the_correlation_when_the_view_raises():
    def get_response(request):
        raise RuntimeError('la vista revienta')

    with pytest.raises(RuntimeError):
        CorrelationIdMiddleware(get_response)(RequestFactory().get('/x'))

    assert get_correlation_id() is None


def test_does_not_break_the_response_if_the_header_cannot_be_set():
    class RespuestaSinCabeceras(HttpResponse):
        def __setitem__(self, header, value):
            raise TypeError('esta respuesta no admite cabeceras')

    response = CorrelationIdMiddleware(
        lambda request: RespuestaSinCabeceras(status=200))(
            RequestFactory().get('/x'))

    assert response.status_code == 200
    assert get_correlation_id() is None
