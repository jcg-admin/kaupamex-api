"""AppConfig — apps.tenancy (capa L1 de la plataforma Kaupamex).

Aloja el modelo multi-tenant de la plataforma: ``Tenant`` (el cliente/
organización que contrata Kaupamex, raíz L1) y ``TenantModuleSubscription``
(qué módulos tiene contratados cada tenant — la puerta L1 sobre el catálogo de
capacidades L2 de ``apps.authz``). FK unidireccional a ``authz.Module`` (sin
ciclo). Diseño: ``analisis-modelo-tenant-l1-foundation`` (plataforma-kaupamex).
"""
from django.apps import AppConfig


class TenancyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tenancy'
    verbose_name = 'Plataforma (tenants y suscripciones)'
