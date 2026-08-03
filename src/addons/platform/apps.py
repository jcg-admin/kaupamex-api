"""AppConfig — addons.platform (capa L1 de la plataforma Kaupamex).

Aloja el modelo multi-company de la plataforma: ``Company`` (el cliente/
organización que contrata Kaupamex, raíz L1; DEC-T7) y
``CompanyModuleSubscription`` (qué módulos tiene contratados cada company — la
puerta L1 sobre el catálogo de capacidades L2 de ``addons.authz``). FK
unidireccional a ``authz.Module`` (sin ciclo). Diseño:
``analisis-modelo-tenant-l1-foundation`` (plataforma-kaupamex).
"""
from django.apps import AppConfig


class PlatformConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.platform'
    # app_label = 'platform' (por defecto, el último componente de name). El
    # addon 'company' no existe en odoo-tools y se disuelve; conservar el
    # app_label 'company' sólo arrastraría deuda (una app muerta). Las
    # migraciones se regeneran; el db_table físico de cada modelo (``company``,
    # ``company_setting``, …) es aparte y se conserva — es el nombre de la
    # tabla, no la identidad de la app. Ver H-API-238/239 y
    # analisis-disolucion-addons-company.rst.
    verbose_name = 'Plataforma (companies y suscripciones)'
