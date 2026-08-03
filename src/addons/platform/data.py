"""Datos semilla del addon — equivalente nativo de ``data/*.xml``.

Siembra el L1 de ejemplo (PracticaYoruba, ``FOUNDER_COMPANY_CODE``) y sus
``CompanySetting`` L1 (``FOUNDER_L1_SETTINGS``, que ya incluye la clave que
añadió la migración ``0007``). El spec vive en ``addons.platform.models``; aquí
sólo está el ``seed()`` que re-aplica las migraciones ``0006``/``0007`` sobre el
modelo vivo (H-API-22).

Nota de multi-DB (mismo gotcha que documenta la migración ``0006``): se asigna
``company_id=<pk>`` escalar y no la instancia. Asignar la instancia dispara el
``ForwardManyToOneDescriptor`` de Django, que consulta el
``CompanyDatabaseRouter`` sin ``company_scope`` activo y revienta con
``CompanyContextRequired``.
"""
from django.db import DEFAULT_DB_ALIAS

from addons.platform.models import (
    FOUNDER_COMPANY_CODE,
    FOUNDER_L1_SETTINGS,
    Company,
    CompanySetting,
)


def seed(using=DEFAULT_DB_ALIAS):
    """Crea el L1 de ejemplo y sus settings ausentes. Idempotente."""
    founder, _ = Company.objects.using(using).get_or_create(
        code=FOUNDER_COMPANY_CODE,
        defaults={'name': 'PracticaYoruba', 'status': 'active'},
    )
    for key, value in FOUNDER_L1_SETTINGS.items():
        CompanySetting.objects.using(using).get_or_create(
            company_id=founder.pk, key=key, defaults={'value': value},
        )
