"""Seed idempotente del catálogo authz — módulos, capacidades y rol superadmin.

Crea el catálogo de :ref:`catalogo-permisos-granulares` (dominio.verbo) y el rol
``superadmin`` que agrupa todas las capacidades. Idempotente
(``get_or_create``); re-ejecutable sin duplicar. El superadmin además hace
*bypass* en el resolver (``apps.authz.services.has_capability``), por lo que el
rol es la fuente de verdad greppeable aunque el bypass lo cortocircuite.

Uso: ``python manage.py seed_authz [--skip-checks]``.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.authz.models import Capability, Module, Role
from apps.authz.services import BUYER_ROLE_CODE, SUPERADMIN_ROLE_CODE

# (code, name, is_sensitive). El dominio (antes del punto) define el Module.
CAPABILITIES = [
    ('audit.view',         'Ver bitácora de auditoría',        False),
    ('backups.manage',     'Gestionar respaldos',              True),
    ('banners.manage',     'Gestionar banners',                False),
    ('catalogue.view',     'Ver catálogo (admin)',             False),
    ('catalogue.manage',   'Gestionar catálogo',               False),
    ('content.manage',     'Gestionar contenido estático',     False),
    ('inventory.view',     'Ver inventario',                   False),
    ('inventory.manage',   'Gestionar inventario',             False),
    ('inventory.adjust',   'Ajustar existencias',              True),
    ('inventory.import',   'Importar inventario',              True),
    ('invoices.view',      'Ver facturas',                     True),
    ('logistics.view',     'Ver logística',                    False),
    ('logistics.manage',   'Gestionar logística',              False),
    ('moderation.view',    'Ver moderación de reseñas',        False),
    ('moderation.manage',  'Moderar reseñas',                  False),
    ('newsletter.manage',  'Gestionar newsletter',             False),
    ('notifications.view', 'Ver notificaciones (admin)',       False),
    ('notifications.manage', 'Gestionar notificaciones',       False),
    ('questions.view',     'Ver preguntas de producto',        False),
    ('questions.manage',   'Moderar preguntas de producto',    False),
    ('orders.view',        'Ver pedidos',                      False),
    ('orders.manage',      'Gestionar pedidos',                False),
    ('payments.view',      'Ver pagos',                        False),
    ('payments.manage',    'Gestionar pagos / reembolsos',     True),
    ('permissions.manage', 'Gestionar permisos y roles',       True),
    ('reports.view',       'Ver reportes',                     False),
    ('reports.export',     'Exportar reportes',                False),
    ('returns.view',       'Ver devoluciones',                 False),
    ('returns.manage',     'Gestionar devoluciones',           False),
    ('seo.manage',         'Gestionar SEO',                    False),
    ('settings.view',      'Ver configuración',                False),
    ('settings.manage',    'Gestionar configuración',          True),
    ('support.view',       'Ver soporte',                      False),
    ('support.manage',     'Gestionar soporte',                False),
    ('users.view',         'Ver usuarios',                     False),
    ('users.manage',       'Gestionar usuarios',               True),
    ('vouchers.view',      'Ver cupones',                      False),
    ('vouchers.manage',    'Gestionar cupones',                False),
    # ── Dominio 'account' — capacidades del COMPRADOR (DEC-AUTHZ-BUYER) ──
    # Gobiernan el menú de cuenta dinámico (audience='account'). El rol
    # 'comprador' las agrupa; se asigna al registrarse. NO son admin.
    ('account.overview',   'Ver resumen de cuenta',            False),
    ('account.orders',     'Ver mis pedidos',                  False),
    ('account.wishlist',   'Ver mis favoritos',                False),
    ('account.returns',    'Ver mis devoluciones',             False),
    ('account.support',    'Ver mi soporte',                   False),
    ('account.notifications', 'Ver mis notificaciones',        False),
    ('account.profile',    'Ver mi perfil',                    False),
    ('account.password',   'Cambiar mi contraseña',            False),
    ('account.deactivate', 'Dar de baja mi cuenta',            False),
    ('account.reviews',    'Ver y escribir mis reseñas',       False),
    ('account.referral',   'Ver mi programa de referidos',     False),
    ('account.payments',   'Ver mi historial y tarjetas',      False),
    ('account.shipments',  'Ver el seguimiento de mis envíos', False),
]

_MODULE_NAMES = {
    'audit': 'Auditoría', 'backups': 'Respaldos', 'banners': 'Banners',
    'catalogue': 'Catálogo', 'content': 'Contenido', 'inventory': 'Inventario',
    'invoices': 'Facturas', 'logistics': 'Logística', 'moderation': 'Moderación',
    'newsletter': 'Newsletter', 'notifications': 'Notificaciones',
    'orders': 'Pedidos', 'payments': 'Pagos', 'permissions': 'Permisos',
    'questions': 'Preguntas de producto', 'reports': 'Reportes',
    'returns': 'Devoluciones', 'seo': 'SEO', 'settings': 'Configuración',
    'support': 'Soporte', 'users': 'Usuarios', 'vouchers': 'Cupones',
    'account': 'Mi cuenta',
}


class Command(BaseCommand):
    help = 'Siembra módulos, capacidades y el rol superadmin de apps.authz.'

    @transaction.atomic
    def handle(self, *args, **options):
        modules = {}
        for domain, name in _MODULE_NAMES.items():
            modules[domain], _ = Module.objects.get_or_create(
                code=domain, defaults={'name': name},
            )

        caps = []
        for code, name, sensitive in CAPABILITIES:
            domain = code.split('.', 1)[0]
            cap, _ = Capability.objects.get_or_create(
                code=code,
                defaults={
                    'module': modules[domain], 'name': name,
                    'is_sensitive': sensitive,
                },
            )
            caps.append(cap)

        role, _ = Role.objects.get_or_create(
            code=SUPERADMIN_ROLE_CODE, defaults={'name': 'Superadministrador'},
        )
        role.capabilities.set(caps)

        # Rol base del comprador (DEC-AUTHZ-BUYER): agrupa las capacidades
        # ``account.*`` que gobiernan el menú de cuenta dinámico.
        buyer_caps = [c for c in caps if c.code.startswith('account.')]
        buyer_role, _ = Role.objects.get_or_create(
            code=BUYER_ROLE_CODE, defaults={'name': 'Comprador'},
        )
        buyer_role.capabilities.set(buyer_caps)

        self.stdout.write(self.style.SUCCESS(
            f'authz seed OK: {len(modules)} módulos, {len(caps)} capacidades, '
            f'rol {SUPERADMIN_ROLE_CODE} con {role.capabilities.count()} y '
            f'rol {BUYER_ROLE_CODE} con {buyer_role.capabilities.count()}.'
        ))
