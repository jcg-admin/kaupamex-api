"""Token de signup/reset firmado — ≙ ``odoo.tools.hash_sign`` /
``verify_hash_signed`` acotado al scope ``'signup'``.

La referencia describe su ``hash_sign`` como *"muy similar a JWT"*: un payload
urlsafe firmado con HMAC sobre el secreto del despliegue, con expiración. El
mecanismo nativo Django idéntico es ``django.core.signing`` (firma con
``SECRET_KEY`` + timestamp). Se usa un ``salt`` propio (= el ``scope='signup'``
de la referencia) para que la firma no colisione con otros usos.

El token es **stateless**: no se almacena. Lo único persistido es
``SignupRequest.signup_type`` (marca de que hay un signup/reset pendiente).
Como el ``login_date`` va en el payload, el token se **invalida en cuanto el
usuario inicia sesión** — fidelidad exacta a ``_generate_signup_token``
(res_partner.py:180-181).
"""
from django.core.signing import BadSignature, SignatureExpired, dumps, loads

_SALT = 'authz_signup'  # ≙ scope 'signup' de la referencia


def sign_signup_payload(payload):
    """Firma el payload (lista) y devuelve el token urlsafe. ≙ ``hash_sign``."""
    return dumps(list(payload), salt=_SALT)


def read_signup_payload(token, max_age_seconds):
    """Verifica firma + expiración y devuelve el payload, o ``None``.

    ≙ ``verify_hash_signed``: firma inválida o token vencido → ``None`` (no
    excepción — el llamador decide el mensaje, igual que la referencia).
    """
    try:
        return loads(token, salt=_SALT, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None


def read_signup_payload_unchecked_age(token):
    """Devuelve el payload validando **sólo la firma**, sin edad — para leer
    el ``signup_type`` y decidir con qué validez re-verificar la edad
    (signup 144h vs reset 4h son distintas). ``None`` si la firma es
    inválida."""
    try:
        return loads(token, salt=_SALT)
    except BadSignature:
        return None
