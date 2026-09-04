"""``_post_logout`` — el enganche que corre después de cerrar sesión.

En la referencia el cuerpo base es ``pass``
(``odoo19c: ir_http.py:362-364``): existe **sólo** para que un addon
enganche ahí. Enterprise 19 lo hereda en dos clases con
``_inherit = 'ir.http'``.

Aquí no había dónde: los dos endpoints de cierre llamaban a ``logout()`` de
Django y devolvían 204, sin punto de extensión entre medias.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models.ir_http import IrHttp


pytestmark = pytest.mark.django_db


def test_the_base_hook_does_nothing_and_returns_none():
    assert IrHttp._post_logout() is None


@pytest.mark.parametrize('ruta', [
    '/api/v2/web/session/destroy/',
    '/api/v2/web/session/logout/',
])
def test_both_endpoints_call_the_hook(client, monkeypatch, ruta):
    """El control: si el endpoint no lo llamara, la lista quedaría vacía.

    Es lo único que distingue un enganche de un método que existe.
    """
    user = get_user_model().objects.create_user(
        login='quien.cierra', password='X9v!kQ2mZr4t')
    client.force_login(user)

    calls = []
    monkeypatch.setattr(IrHttp, '_post_logout',
                        classmethod(lambda cls: calls.append(ruta)))

    response = client.post(ruta)
    assert response.status_code == 204
    assert calls == [ruta]
