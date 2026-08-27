"""Autenticacion de sesion sin exigencia de token CSRF (ADR-018).

Reubicada desde ``addons/users/authentication.py`` al disolver ``users`` en
``base`` (H-API-119): es plomeria del framework, no dominio de identidad —
vive con ``ir_*`` y ``res_*``, no con la credencial que autentica.

Auth **unica** del SPA tras la migracion completa (Opcion 3 del
analisis-incidente-csrf-mutaciones).

``SessionAuthentication`` de DRF exige un token CSRF en metodos no seguros. Eso
rompia las mutaciones cuando el token en memoria ya no estaba (post-recarga):
la sesion autenticaba, pero el ``POST`` (p. ej. agregar al carrito) respondia
403 y el SPA cerraba sesion.

Se retira la exigencia del **token** CSRF y se confia en la defensa que ya da
la propia cookie de sesion: ``SameSite=Lax`` + prefijo ``__Host-``. Con
``Lax`` la cookie **no viaja en un POST cross-site**, que es el vector de
CSRF; y como TODAS las mutaciones del SPA son XHR ``POST``/``PATCH``/
``DELETE``, un sitio ajeno no puede forzarlas. Ver el analisis de esta
iniciativa.

**No es ``Strict``, y la diferencia importa** (CR-5, hotfix de ADR-018 —
ver ``config/settings/production.py:18-25``). Con ``Strict``, entrar al SPA
por un enlace **externo** con sesion viva —un correo de verificacion, un
resultado de buscador— hace que el navegador omita la cookie en esa
navegacion top-level, y el primer render sale anonimo: la UI lo presenta
como "la sesion expiro". Los XHR same-origin no cambian entre ``Lax`` y
``Strict``, asi que ``Strict`` costaba ese falso 401 sin comprar defensa.

**Guardrail que acompania a ``Lax``:** ningun endpoint muta estado por
``GET``. ``Lax`` SI envia la cookie en una navegacion ``GET`` top-level.
"""
from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """SessionAuthentication cuya defensa CSRF es ``SameSite=Lax``.

    ``enforce_csrf`` se vuelve no-op: no se pide token ``X-CSRFToken``. El
    riesgo CSRF lo cubre la cookie ``__Host-sessionid; SameSite=Lax``, que no
    viaja en un ``POST`` cross-site — el vector real, dado que toda mutacion
    es XHR. Ver el docstring del modulo para por que ``Lax`` y no ``Strict``.

    Ademas provee ``authenticate_header`` para que una peticion **no
    autenticada** a un endpoint protegido devuelva **401** (no 403). DRF
    devuelve 401 solo si algun autenticador aporta un ``WWW-Authenticate``;
    ``SessionAuthentication`` base no lo hace, asi que al quedar como auth
    unica los anonimos recibirian 403. El SPA (apiService) y los tests
    dependen del contrato 401 = "sesion ausente/expirada", asi que se conserva.
    """

    def enforce_csrf(self, request):
        return  # defensa CSRF = SameSite=Lax + __Host-, no token

    def authenticate_header(self, request):
        # Fuerza 401 (no 403) para peticiones sin sesion en endpoints
        # protegidos. El valor exacto es informativo (no hay reto HTTP real).
        return 'Session'
