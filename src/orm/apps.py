"""AppConfig — ``orm`` (infraestructura multi-DB, hermano de ``apps``).

Fiel a ``odoo/orm/`` de Odoo 19 (hermano de ``addons``): aloja el registro L0
(``CompanyDatabase``) y el router de bases por empresa (``routers.py``),
separados del dominio (``apps.*``).
"""
from django.apps import AppConfig


class OrmConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'orm'
    verbose_name = 'Infraestructura ORM multi-DB (registro L0 + router)'
