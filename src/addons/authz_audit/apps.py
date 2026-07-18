"""AppConfig — addons.authz_audit (auditoría de autorización, DEC-07).

Módulo de feature **opcional** extraído de ``addons.authz`` (SOL-094 frente B,
DEC-01): la auditoría append-only de autorización (``AuthzEvent``) vive en su
propio módulo instalable, al estilo Odoo (``account_audit_trail`` separado de
``account``). Un despliegue puede omitirlo sin afectar el core de autorización.
"""
from django.apps import AppConfig


class AuthzAuditConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.authz_audit'
    verbose_name = 'Autorización — auditoría'
