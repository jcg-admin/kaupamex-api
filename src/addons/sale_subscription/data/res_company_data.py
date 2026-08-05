"""Datos semilla del eje L0 — equivalente nativo de ``data/*.xml``.

Aquí vive el DATO concreto del deployment que sí es del operador: el código de
la compañía de sistema. ``base`` queda abstracto (no nombra empresas) — igual
que en la referencia, donde una compañía real es un registro de datos, no
código del framework.

- ``SYSTEM_COMPANY_CODE`` — la compañía de datos compartidos del operador
  (``is_system=True``). Los datos globales cuelgan de ella; NO se usa
  ``company_id`` nullable.

**La primera empresa L1 ya no se nombra aquí** (DEC-3 de
``tenants-sin-clases-en-codigo``, directiva del ejecutor 2026-08-05). Antes
este módulo declaraba ``FOUNDER_COMPANY_CODE = 'practicayoruba'`` y sus cuatro
remitentes de correo como constantes, y ``ResCompany.get_founder()`` la
fabricaba bajo demanda: eso hacía que la app conociera "el founder" por código
en runtime, cuando el L1 de ejemplo es una empresa entre potencialmente varias.
Ahora la empresa inicial se declara en config (``BOOTSTRAP_COMPANY_CODE``) y la
crea el bootstrap ``manage.py company_create``, que además admite
``--setting clave=valor`` para sus ``CompanySetting`` per-empresa.

Nota de multi-DB (gotcha heredado de la migración ``0006``): al sembrar
settings se asigna ``company_id=<pk>`` escalar y no la instancia — asignar la
instancia dispara el descriptor de la FK, que consulta el router multi-DB sin
``company_scope`` activo y revienta con ``CompanyContextRequired``.
"""
from django.conf import settings

from addons.base.models import ResCompany

SYSTEM_COMPANY_CODE = 'kaupamex_global'


def seed():
    """Crea la empresa de bootstrap declarada en config. Idempotente.

    No-op cuando ``BOOTSTRAP_COMPANY_CODE`` está vacío: una instalación sin
    empresa declarada no siembra ninguna. Devuelve la empresa o ``None``.
    """
    code = getattr(settings, 'BOOTSTRAP_COMPANY_CODE', '')
    if not code:
        return None
    company = ResCompany.objects.filter(code=code).first()
    if company is not None:
        return company
    # ``name`` vive en el partner (related): la semilla pasa por el camino de
    # creación que fabrica el partner, no por un get_or_create plano.
    name = getattr(settings, 'BOOTSTRAP_COMPANY_NAME', '') or code
    return ResCompany.create_company(
        name, code=code, status=ResCompany.Status.ACTIVE)
