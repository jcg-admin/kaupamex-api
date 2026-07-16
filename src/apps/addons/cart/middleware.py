"""Cart cookie middleware (H-CART-01 Fase 2).

Fija/renueva la cookie httpOnly ``cart_token`` para carritos anónimos, de modo
que el carrito sea durable entre recargas y pestañas nuevas — a diferencia del
header ``X-Cart-Token`` memory-only (DEC-BC-07), que el cliente pierde al
recargar la página o abrir el enlace de activación del correo.

Las vistas de carrito señalizan el token a persistir en
``request._anon_cart_token`` (ver ``apps/cart/views.py::_get_or_create_cart``).
Este middleware SÓLO lee esa señal y fija la cookie; no resuelve carritos
(Single Responsibility) y no toca respuestas de usuarios autenticados (allí el
carrito se resuelve por ``user``, no por token).

Por qué una cookie httpOnly NO contradice DEC-BC-07/ADR-005 (anti-XSS): una
cookie ``httpOnly`` no es leíble por JavaScript, de modo que un XSS no puede
exfiltrar el token — a diferencia de ``localStorage``/``sessionStorage``, que sí
son accesibles por JS y por eso DEC-BC-07 los rechazó. La cookie viaja sola en
cada request same-origin con ``credentials: 'include'``; el frontend no la lee
ni la escribe. Ver ``analisis-carrito-persistente-marketing.rst``.

La cookie ``cart_token`` está declarada como ``necessary`` en
``COOKIE_REGISTER`` (cookie funcional del carrito): no identifica a la persona
por sí sola y es indispensable para el servicio de tienda solicitado, por lo que
está exenta de consentimiento bajo LFPDPPP/GDPR.
"""
from django.conf import settings

CART_COOKIE_NAME = 'cart_token'
# 30 días; se renueva en cada respuesta de carrito → ventana deslizante.
CART_COOKIE_MAX_AGE = 60 * 60 * 24 * 30


class CartCookieMiddleware:
    """Persiste el ``cart_token`` anónimo en una cookie httpOnly.

    Debe ubicarse por DEBAJO de ``CookieGovernanceMiddleware`` en MIDDLEWARE
    para que el ``process_response`` de aquél (orden inverso) observe la cookie
    de carrito y emita su veredicto (``ALLOWED`` por estar registrada).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        token = getattr(request, '_anon_cart_token', None)
        if token:
            response.set_cookie(
                CART_COOKIE_NAME,
                token,
                max_age=CART_COOKIE_MAX_AGE,
                httponly=True,
                secure=not settings.DEBUG,
                samesite='Lax',
            )
        return response
