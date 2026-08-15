"""Cookie governance middleware (LFPDPPP).

Gobierna toda cookie emitida contra un registro declarado (COOKIE_REGISTER):
la observa en ``response.cookies`` al final del ciclo, la clasifica y —segun la
politica y el consentimiento del titular— la audita y, en modo enforce, la
suprime.

No verifica CSRF ni fija cookies: esa responsabilidad es del middleware nativo
de Django. Aqui solo se **observa y gobierna** (Single Responsibility).

Fase 1 (por defecto): modo auditoria — loguea el veredicto, no borra.
Fase 2 (``COOKIE_GOVERNANCE_ENFORCE = True``): fail-closed — borra cookies no
registradas o sin consentimiento.

Ver los analisis de la iniciativa migrar-auth-sesion-cookie-httponly
(gobernanza de cookies + consentimiento UI + LFPDPPP).
"""
import json
import logging
from urllib.parse import unquote

from django.conf import settings

logger = logging.getLogger('cookie_governance')

CONSENT_COOKIE = 'cookie_consent'

# Registro de cookies. Cada entrada declara su categoria; las de categoria
# distinta de "necessary" requieren consentimiento. Las estrictamente
# necesarias (sesion, CSRF) y la propia cookie de consentimiento estan exentas.
COOKIE_REGISTER = {
    'sessionid': {'category': 'necessary'},
    '__Host-sessionid': {'category': 'necessary'},
    'csrftoken': {'category': 'necessary'},
    '__Host-csrftoken': {'category': 'necessary'},
    CONSENT_COOKIE: {'category': 'necessary'},
    # H-CART-01 Fase 2: cookie funcional del carrito. No identifica a la
    # persona por si sola y es indispensable para el servicio de tienda
    # solicitado -> exenta de consentimiento (LFPDPPP/GDPR). httpOnly, la
    # emite CartCookieMiddleware.
    'cart_token': {'category': 'necessary'},
    # utm: los tres ejes de marketing que ir.http captura de la URL. La
    # referencia los emite con cookie_type='optional' (odoo19c:
    # addons/utm/models/ir_http.py:21), su clasificacion de consentimiento —
    # aqui eso es una categoria distinta de "necessary", asi que sin
    # consentimiento el modo enforce las suprime. No son indispensables para
    # el servicio: atribuyen la visita a una campania.
    'kaupamex_utm_campaign': {'category': 'marketing'},
    'kaupamex_utm_source': {'category': 'marketing'},
    'kaupamex_utm_medium': {'category': 'marketing'},
}


def _read_consent(request):
    """Devuelve el mapa de elecciones {categoria: bool} del titular, o {}.

    La cookie ``cookie_consent`` es JSON URL-encoded escrito por la UI.
    """
    raw = request.COOKIES.get(CONSENT_COOKIE)
    if not raw:
        return {}
    try:
        record = json.loads(unquote(raw))
    except (ValueError, TypeError):
        return {}
    choices = record.get('choices') if isinstance(record, dict) else None
    return choices if isinstance(choices, dict) else {}


def _requires_consent(policy):
    return policy['category'] != 'necessary'


class CookieGovernanceMiddleware:
    """Audita/gobierna las cookies emitidas contra COOKIE_REGISTER.

    Debe ubicarse por ENCIMA de SessionMiddleware y CsrfViewMiddleware en
    MIDDLEWARE para que su ``process_response`` (orden inverso) corra despues
    de que aquellas hayan puesto sus cookies.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.enforce = getattr(settings, 'COOKIE_GOVERNANCE_ENFORCE', False)

    def __call__(self, request):
        response = self.get_response(request)
        consent = _read_consent(request)

        for name in list(response.cookies.keys()):
            policy = COOKIE_REGISTER.get(name)

            if policy is None:
                self._audit(request, name, 'UNREGISTERED')
                if self.enforce:
                    del response.cookies[name]
                continue

            if _requires_consent(policy) and not consent.get(policy['category']):
                self._audit(request, name, 'BLOCKED_NO_CONSENT')
                if self.enforce:
                    del response.cookies[name]
                continue

            self._audit(request, name, 'ALLOWED')

        return response

    def _audit(self, request, name, verdict):
        logger.info(
            'cookie_governance verdict=%s cookie=%s path=%s enforce=%s',
            verdict, name, request.path, self.enforce,
        )
