"""Datos semilla del eje L0 — equivalente nativo de ``data/*.xml``.

Aquí viven los DATOS concretos del deployment: los códigos de las compañías
especiales y los settings L1 del tenant insignia. ``base`` queda abstracto
(no nombra tenants) — igual que en la referencia, donde una compañía real es
un registro de datos, no código del framework.

- ``FOUNDER_COMPANY_CODE`` — el L1 insignia (PracticaYoruba): primer tenant
  real, destino del backfill de las filas de dominio existentes. En prosa NO
  se le llama "founder" (``terminologia-l0-company.md``); el nombre de la
  constante se conserva porque es el identificador real en uso.
- ``SYSTEM_COMPANY_CODE`` — la compañía de datos compartidos del operador
  (``is_system=True``). Los datos globales cuelgan de ella; NO se usa
  ``company_id`` nullable.
- ``FOUNDER_L1_SETTINGS`` — remitentes de correo per-tenant del insignia,
  sembrados como sus ``CompanySetting`` (antes ``default=`` global en
  ``config.settings.base``; PracticaYoruba es L1, no L0, así que no estaban
  stale — estaban mal ubicados).

Nota de multi-DB (gotcha heredado de la migración ``0006``): al sembrar
settings se asigna ``company_id=<pk>`` escalar y no la instancia — asignar la
instancia dispara el descriptor de la FK, que consulta el router multi-DB sin
``company_scope`` activo y revienta con ``CompanyContextRequired``.
"""
from django.db import DEFAULT_DB_ALIAS

from addons.base.models import CompanySetting, ResCompany

FOUNDER_COMPANY_CODE = 'practicayoruba'
SYSTEM_COMPANY_CODE = 'kaupamex_global'

# ``notifications.from_email`` es el remitente no-reply transaccional ÚNICO
# del tenant: bajo el diseño previo todo el correo transaccional salía de un
# solo remitente global. Se conserva esa unicidad como una sola clave
# per-tenant, en vez de una clave por addon.
FOUNDER_L1_SETTINGS = {
    'contact.from_email': 'hola@practicayoruba.com',
    'contact.notify_email': 'hola@practicayoruba.com',
    'newsletter.from_email': 'newsletter@practicayoruba.com',
    'notifications.from_email': 'noreply@practicayoruba.com',
}


def seed(using=DEFAULT_DB_ALIAS):
    """Crea el L1 insignia y sus settings ausentes. Idempotente."""
    # ``name`` vive en el partner (related): la semilla pasa por el camino de
    # creación que fabrica el partner, no por un get_or_create plano.
    founder = ResCompany.get_founder()
    for key, value in FOUNDER_L1_SETTINGS.items():
        CompanySetting.objects.using(using).get_or_create(
            company_id=founder.pk, key=key, defaults={'value': value},
        )
    return founder
