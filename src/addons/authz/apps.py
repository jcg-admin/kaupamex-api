"""AppConfig — addons.authz (modelo de capacidades propio, MOD-027).

Aloja el modelo de autorización propio (Opción B, DEC-AUTHZ-01) que reemplaza
la autorización nativa de Django (is_staff/is_superuser/groups): Module,
Capability, Role, RoleAssignment, DirectEntitlement, EntitlementRevocation y
AuthzEvent. SOL-016, iniciativa crear-apps-authz.
"""
from django.apps import AppConfig


class AuthzConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.authz'
    verbose_name = 'Autorización (capacidades)'
