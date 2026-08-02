"""``audit_log_business`` — emisor de ``BusinessEvent`` (DEC-CC-2).

Inserta el evento vía ``transaction.on_commit`` cuando hay una transacción
abierta, para no bloquear el camino caliente y para que el evento no exista si
la transacción aborta; inserta directo cuando no la hay (rutas de excepción que
abortan el ``atomic`` block). Ver la iniciativa
``audit-log-eventos-cross-cutting``, DEC-AL-3 (PII safe) y DEC-AL-4 (on_commit).

**Procedencia.** Vivía en ``users/audit.py`` junto a ``audit_log_auth``. El
commit ``api@6cf8120`` disolvió ``users`` y el archivo se borró sin re-alojar.
Aquí viaja **sólo** la mitad de negocio: ``audit_log_auth`` emite ``AuthEvent``,
cuyo homólogo en la referencia es ``res.users.log``
(``odoo19c: odoo/addons/base/models/res_users.py``) y por tanto pertenece a
``base``, no a ``observability``. Separarlas es la consecuencia de que la
referencia las separa. ``audit_log_auth`` **no se re-alojó** en este pase: a
HEAD tiene **0** llamadores vivos (medido con ``grep -rn`` sobre ``src/``,
excluyendo ``migrations/``), así que re-crearlo sería código sin consumidor.
Ver H-API-211.
"""
from django.db import transaction

from addons.observability.models import BusinessEvent


def extract_ip(request):
    """IP del cliente, respetando el proxy (``X-Forwarded-For`` primero)."""
    if request is None:
        return None
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def audit_log_business(actor, action, request,
                       target_type: str = '', target_id: int | None = None,
                       extra: dict | None = None):
    """Crea un ``BusinessEvent``.

    Argumentos:
      actor:       credencial que dispara el evento (``None`` para acciones
                   del sistema).
      action:      constante ``BusinessEvent.ACTION_*``.
      request:     ``HttpRequest`` (o ``None`` en acciones del sistema).
      target_type: constante ``BusinessEvent.TARGET_*``.
      target_id:   id del objetivo.
      extra:       dict opcional. NUNCA PII, contraseñas ni tokens (DEC-AL-3).
    """
    ip_addr = extract_ip(request)

    def _create():
        BusinessEvent.objects.create(
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=target_id,
            ip_addr=ip_addr,
            extra_json=extra,
        )

    if transaction.get_autocommit():
        _create()
    else:
        transaction.on_commit(_create)
