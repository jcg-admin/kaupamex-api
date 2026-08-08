"""Extensiones drf-spectacular de la autenticación (H-API-264).

Esta pieza vivía en ``users/schema.py`` y murió con la disolución de
``users`` en ``base``: desde entonces el OpenAPI publicaba
``securitySchemes`` **vacío** y drf-spectacular emitía una W001 (*could
not resolve authenticator*) por cada vista del árbol. Se recrea aquí —
``base`` es el dueño actual de la credencial (``ResUsers``) y de
``CsrfExemptSessionAuthentication`` — siguiendo el patrón Open/Closed del
proyecto: el hook de PREPROCESSING (``config.spectacular_hooks``) importa
los ``schema.py`` de cada app ANTES de generar, y la extensión se
auto-registra al definirse la clase.

De las tres extensiones originales sólo se recrea la de sesión: las dos
de simplejwt (``PYTokenObtainPairSerializerExtension`` y
``TokenBlacklistViewFix``) perdieron su sujeto con ``users`` —
``PYTokenObtainPairSerializer`` ya no existe en ``src/`` y
``TokenBlacklistView`` no está ruteada (simplejwt instalado pero
**dormido**, ADR-018). Si el login JWT despierta, sus extensiones
vuelven con él.
"""
from drf_spectacular.authentication import SessionScheme


class CsrfExemptSessionScheme(SessionScheme):
    """Documenta la auth por sesión (ADR-018) en el esquema OpenAPI.

    ``CsrfExemptSessionAuthentication`` es la auth por defecto del
    proyecto. drf-spectacular sólo resuelve la clase exacta
    ``SessionAuthentication``, no sus subclases — sin esta extensión el
    esquema queda SIN ``securityScheme`` y cada vista emite una W001.
    Reutiliza el ``SessionScheme`` built-in (produce ``cookieAuth``).
    """
    target_class = 'addons.base.authentication.CsrfExemptSessionAuthentication'
    name = 'cookieAuth'
