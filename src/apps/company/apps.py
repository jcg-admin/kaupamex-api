"""AppConfig — apps.company (capa L1 de la plataforma Kaupamex).

Aloja el modelo multi-company de la plataforma: ``Company`` (el cliente/
organización que contrata Kaupamex, raíz L1; DEC-T7) y
``CompanyModuleSubscription`` (qué módulos tiene contratados cada company — la
puerta L1 sobre el catálogo de capacidades L2 de ``apps.authz``). FK
unidireccional a ``authz.Module`` (sin ciclo). Diseño:
``analisis-modelo-tenant-l1-foundation`` (plataforma-kaupamex).
"""
from django.apps import AppConfig


class TenancyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.company'
    verbose_name = 'Plataforma (companies y suscripciones)'
