"""
apps/core/log_scrubber.py

PIIScrubber (SOL-011 T-02, DEC-LOG-03 Nivel 1): redacta *secretos* del texto
libre que llega a los logs (``IrLogging.message`` / ``IrLogging.trace`` /
``RequestLog.error_detail``). Es obligatorio tambien en tracebacks: los
``locals`` que Python muestra en una traza pueden contener ``password=...`` o
``card_token=...``.

Alcance = **Nivel 1 (secretos)** de DEC-LOG-03: NUNCA se almacenan, ni cifrados
(PCI: el CVV no se persiste). El Nivel 2 (PII) no se copia por diseno (se guarda
la FK ``user`` / ``order_number``), asi que el scrubber no intenta enmascarar
nombres/emails — esos nunca deberian entrar al log.

Funcion pura, sin dependencias de Django ni de DB: se puede aplicar en el
handler, el middleware o el exception_handler antes de insertar.
"""
import re

# Marcador de redaccion. Constante publica para que los tests no dependan del
# literal.
REDACTED = "***REDACTED***"

# Claves de secreto de Nivel 1 (DEC-LOG-03). Case-insensitive, con ``\b`` para
# no matchear dentro de otra palabra (``japan`` no dispara ``pan``). El guion
# bajo es caracter de palabra, asi que ``access_token`` se matchea completo y
# ``csrf_token`` no dispara ``token`` a mitad de palabra (el proyecto no usa
# token CSRF; los tokens de auth son ``access_token`` / ``refresh_token``,
# listados explicitamente).
_SECRET_KEYS = [
    "password", "passwd", "pwd",
    "access_token", "refresh_token", "id_token", "card_token", "token",
    "authorization", "auth_token",
    "client_secret", "secret", "api_key", "apikey",
    "cvv", "cvc", "csc", "pan",
]

# Alternacion con las claves mas largas primero para que ``access_token`` gane
# sobre ``token`` en el punto de match.
_KEY_ALT = "|".join(
    re.escape(k) for k in sorted(_SECRET_KEYS, key=len, reverse=True)
)

# ``key <sep> value`` en cualquier forma comun: ``key=value``, ``key: value``,
# ``"key": "value"``, ``'key': 'value'``, ``key => value``. El valor puede venir
# entre comillas (se conservan) o desnudo hasta el proximo delimitador.
_KV_RE = re.compile(
    r"""(?ix)
    (?P<key>["']?\b(?:%s)\b["']?)
    (?P<sep>\s*(?:=>|[:=])\s*)
    (?P<val>
        "(?:[^"\\]|\\.)*"
      | '(?:[^'\\]|\\.)*'
      | [^\s,;&}{)\]]+
    )
    """ % _KEY_ALT,
)

# ``Bearer <token>`` / ``Basic <token>`` en headers o logs (aunque no venga como
# ``key=value``).
_BEARER_RE = re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._\-+/=]+")

# PAN de tarjeta: 13-19 digitos contiguos, o en grupos de 4 separados por
# espacio/guion. Conservador para no redactar ids cortos (status, duration).
_PAN_CONTIGUOUS_RE = re.compile(r"\b\d{13,19}\b")
_PAN_GROUPED_RE = re.compile(r"\b\d{4}[ -]\d{4}[ -]\d{4}[ -]\d{1,7}\b")


def _redact_kv(match):
    val = match.group("val")
    if len(val) >= 2 and val[0] in "\"'" and val[-1] == val[0]:
        new_val = f'{val[0]}{REDACTED}{val[0]}'
    else:
        new_val = REDACTED
    return f'{match.group("key")}{match.group("sep")}{new_val}'


def scrub(text):
    """Redacta secretos de Nivel 1 en ``text``.

    Tolera ``None`` (lo devuelve tal cual) y valores no-str (los coacciona con
    ``str``). Idempotente: aplicar ``scrub`` dos veces da el mismo resultado.
    """
    if text is None:
        return None
    if not isinstance(text, str):
        text = str(text)
    if not text:
        return text
    # Bearer/Basic primero: si viene ``Authorization: Bearer xyz``, redacta el
    # token completo antes de que la regla ``key=value`` solo tome ``Bearer``.
    text = _BEARER_RE.sub(lambda m: f"{m.group(1)} {REDACTED}", text)
    text = _KV_RE.sub(_redact_kv, text)
    text = _PAN_GROUPED_RE.sub(REDACTED, text)
    text = _PAN_CONTIGUOUS_RE.sub(REDACTED, text)
    return text
