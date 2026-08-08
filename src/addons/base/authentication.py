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
la propia cookie de sesion: ``SameSite=Strict`` + prefijo ``__Host-`` (la
cookie **no viaja** en peticiones cross-site, que es el vector de CSRF). Ver
el analisis de esta iniciativa.
"""
from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """SessionAuthentication cuya defensa CSRF es ``SameSite=Strict``.

    ``enforce_csrf`` se vuelve no-op: no se pide token ``X-CSRFToken``. El
    riesgo CSRF lo cubre la cookie ``__Host-sessionid; SameSite=Strict``.

    Ademas provee ``authenticate_header`` para que una peticion **no
    autenticada** a un endpoint protegido devuelva **401** (no 403). DRF
    devuelve 401 solo si algun autenticador aporta un ``WWW-Authenticate``;
    ``SessionAuthentication`` base no lo hace, asi que al quedar como auth
    unica los anonimos recibirian 403. El SPA (apiService) y los tests
    dependen del contrato 401 = "sesion ausente/expirada", asi que se conserva.
    """

    def enforce_csrf(self, request):
        return  # defensa CSRF = SameSite=Strict + __Host-, no token

    def authenticate_header(self, request):
        # Fuerza 401 (no 403) para peticiones sin sesion en endpoints
        # protegidos. El valor exacto es informativo (no hay reto HTTP real).
        return 'Session'
