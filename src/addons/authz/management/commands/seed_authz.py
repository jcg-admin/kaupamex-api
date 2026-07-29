"""Seed idempotente del catálogo authz — módulos, capacidades y rol superadmin.

**DEC-11 (sustantivo + nivel).** Las capacidades **CRUD** se siembran como
**sustantivo puro** (``catalogue``, ``orders``, …): el nivel de acceso
(``VIEW<CREATE<EDIT<FULL``) vive en ``RoleCapability.level``, no en el código.
El resolver expande ``noun@nivel → {noun.view, noun.create, noun.edit,
noun.full}`` (``addons.authz.services.resolve_capabilities``). Las **acciones
nombradas** (``account.*``, ``inventory.adjust``/``import``, ``reports.export``,
``platform.provision``) se siembran **con punto** (membresía, sin nivel).

El rol ``superadmin`` agrupa todas las capacidades a nivel FULL (default de
``RoleCapability``) y además hace *bypass* en el resolver. Idempotente
(``get_or_create``); re-ejecutable sin duplicar.

Uso: ``python manage.py seed_authz [--skip-checks]``.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from addons.authz.models import Capability, Module, Role
from addons.authz.services import BUYER_ROLE_CODE, SUPERADMIN_ROLE_CODE

# Capacidades CRUD (sustantivo, sin punto). ``(noun, is_sensitive)``. El nivel
# se asigna en RoleCapability; el nombre proviene de _MODULE_NAMES (1:1 noun↔módulo).
CRUD_NOUNS = [
    ('audit',         False),
    ('backups',       True),
    ('banners',       False),
    ('catalogue',     False),
    ('content',       False),
    ('finance',       True),
    ('inventory',     False),
    ('invoices',      True),
    ('logistics',     False),
    ('moderation',    False),
    ('newsletter',    False),
    ('notifications', False),
    ('orders',        False),
    ('payments',      True),
    ('permissions',   True),
    ('platform',      True),
    ('questions',     False),
    ('reports',       False),
    ('returns',       False),
    ('seo',           False),
    ('settings',      True),
    ('support',       False),
    ('users',         True),
    ('vouchers',      False),
]

# Acciones nombradas (con punto → membresía, sin nivel). ``(code, name, is_sensitive)``.
NAMED_ACTIONS = [
    ('account.overview',      'Ver resumen de cuenta',            False),
    ('account.orders',        'Ver mis pedidos',                  False),
    ('account.wishlist',      'Ver mis favoritos',                False),
    ('account.returns',       'Ver mis devoluciones',             False),
    ('account.support',       'Ver mi soporte',                   False),
    ('account.notifications', 'Ver mis notificaciones',           False),
    ('account.bus',          'Leer mi canal de eventos',         False),
    ('account.profile',       'Ver mi perfil',                    False),
    ('account.password',      'Cambiar mi contraseña',            False),
    ('account.security',      'Gestionar mi verificación 2FA',    False),
    ('account.deactivate',    'Dar de baja mi cuenta',            False),
    ('account.reviews',       'Ver y escribir mis reseñas',       False),
    ('account.referral',      'Ver mi programa de referidos',     False),
    ('account.payments',      'Ver mi historial y tarjetas',      False),
    ('account.shipments',     'Ver el seguimiento de mis envíos', False),
    ('inventory.adjust',      'Ajustar existencias',              True),
    ('inventory.import',      'Importar inventario',              True),
    ('reports.export',        'Exportar reportes',                False),
    ('platform.provision',    'Provisionar la plataforma (operador Kaupamex L0)', True),
    ('platform.billing',      'Facturar y cobrar suscripciones (operador Kaupamex L0)', True),
    # MOD-028 FINANCE — acciones SoD (segregacion de funciones, UC-FIN-01..08).
    ('finance.record',        'Registrar movimiento/concepto financiero',  True),
    ('finance.reconcile',     'Conciliar liquidaciones del gateway',       True),
    ('finance.disburse',      'Pagar flete / cancelar-reembolsar cobro',   True),
    ('finance.close',         'Sellar corte de caja / cerrar ejercicio',   True),
]

_MODULE_NAMES = {
    'audit': 'Auditoría', 'backups': 'Respaldos', 'banners': 'Banners',
    'catalogue': 'Catálogo', 'content': 'Contenido', 'finance': 'Finanzas',
    'inventory': 'Inventario',
    'invoices': 'Facturas', 'logistics': 'Logística', 'moderation': 'Moderación',
    'newsletter': 'Newsletter', 'notifications': 'Notificaciones',
    'orders': 'Pedidos', 'payments': 'Pagos', 'permissions': 'Permisos',
    'platform': 'Plataforma', 'questions': 'Preguntas de producto',
    'reports': 'Reportes', 'returns': 'Devoluciones', 'seo': 'SEO',
    'settings': 'Configuración', 'support': 'Soporte', 'users': 'Usuarios',
    'vouchers': 'Cupones', 'account': 'Mi cuenta',
}

# Grafo de dependencias entre módulos (SOL-085 S3): activar un módulo para una
# company exige sus ``depends`` activos. Dependencias funcionales reales; sólo
# se declaran deps directas (transitivamente correcto — ver Module.depends).
MODULE_DEPENDS = {
    'inventory': ['catalogue'],              # stock es por producto
    'orders':    ['catalogue', 'inventory'],  # no hay pedido sin catálogo + stock
    'payments':  ['orders'],                 # el pago es contra un pedido
    'invoices':  ['orders'],                 # se factura un pedido
    'logistics': ['orders'],                 # se envía un pedido
    'returns':   ['orders'],                 # se devuelve un pedido
}


# Catálogo L0 de NUESTROS módulos (diseno-catalogo-l0-module-extendido, #179).
# ``is_application`` = app vendible top-level vs módulo técnico (dependencia
# interna) — clasificación ESTRUCTURAL (INFERRED, ratificable: es dato editable
# en runtime). ``category`` = agrupación funcional de catálogo. **``tier`` NO se
# fija aquí**: el modelo de precios (free/paid por módulo) es GAP 4 / #180
# (billing L0 abierto); todos quedan en el default ``free`` hasta esa decisión.
# ``category`` = **familia funcional ERP** (taxonomía NetSuite/Odoo ``__manifest__``),
# no una etiqueta plana. Los módulos se agrupan por familia (Order Management ≠
# SCM ≠ Finance ≠ CRM ≠ Employee Management), como ratifican los análisis de
# referencia de la iniciativa plataforma-kaupamex:
#   - Order Management = el continuo comercial completo (Sales Order → Fulfill →
#     Invoice → Payment → Returns), PROVEN en
#     ``analisis-ubicacion-modulo-billing-order-management`` (facturación e
#     invoices viven aquí, NO en Finance).
#   - Employee Management (SuitePeople/HCM) = familia HR, hermana top-level;
#     futura, ningún módulo actual la ocupa (``analisis-netsuite-modulo-employee-management``).
# Valor = string display en inglés (contrato del ``category`` de manifest, que
# en Odoo es "Human Resources"/"Sales", no un slug). El identificador máquina es
# ``code``. ``tier`` NO se fija aquí (pricing = GAP 4 / #180 — no inventar precios).
MODULE_CATALOG = {
    # code:        (is_application, category)  — category = familia funcional ERP
    'catalogue':   (True,  'Order Management'),
    'orders':      (True,  'Order Management'),
    'payments':    (True,  'Order Management'),
    'invoices':    (True,  'Order Management'),
    'vouchers':    (True,  'Order Management'),
    'inventory':   (True,  'Supply Chain Management'),
    'logistics':   (True,  'Order Management'),
    'returns':     (True,  'Order Management'),
    'finance':     (True,  'Finance'),
    'reports':     (True,  'Finance'),
    'newsletter':  (True,  'CRM'),
    'support':     (True,  'CRM'),
    # Técnicos (no se contratan por separado; dependencia/infra interna):
    'moderation':  (False, 'CRM'),
    'questions':   (False, 'Order Management'),
    'banners':     (False, 'CRM'),
    'content':     (False, 'Platform'),
    'seo':         (False, 'Platform'),
    'notifications': (False, 'Platform'),
    'audit':       (False, 'Platform'),
    'backups':     (False, 'Platform'),
    'permissions': (False, 'Platform'),
    'platform':    (False, 'Platform'),
    'settings':    (False, 'Platform'),
    'users':       (False, 'Platform'),
    'account':     (False, 'Platform'),
}


class Command(BaseCommand):
    help = 'Siembra módulos, capacidades y el rol superadmin de addons.authz.'

    @transaction.atomic
    def handle(self, *args, **options):
        modules = {}
        for domain, name in _MODULE_NAMES.items():
            modules[domain], _ = Module.objects.get_or_create(
                code=domain, defaults={'name': name},
            )

        # Catálogo L0 (#179): clasifica NUESTROS módulos (is_application +
        # category). Idempotente; refresca filas ya existentes. ``tier`` se
        # deja en su default (free) — pricing es GAP 4 / #180.
        for code, (is_app, category) in MODULE_CATALOG.items():
            mod = modules[code]
            if mod.is_application != is_app or mod.category != category:
                mod.is_application = is_app
                mod.category = category
                mod.save(update_fields=['is_application', 'category', 'updated_at'])

        # Grafo de dependencias (SOL-085 S3). ``set`` es idempotente.
        for domain, dep_codes in MODULE_DEPENDS.items():
            modules[domain].depends.set([modules[d] for d in dep_codes])

        caps = []
        # Capacidades CRUD como sustantivo (nivel en RoleCapability).
        for noun, sensitive in CRUD_NOUNS:
            cap, _ = Capability.objects.get_or_create(
                code=noun,
                defaults={
                    'module': modules[noun], 'name': _MODULE_NAMES[noun],
                    'is_sensitive': sensitive,
                },
            )
            caps.append(cap)
        # Acciones nombradas (con punto → membresía).
        for code, name, sensitive in NAMED_ACTIONS:
            domain = code.split('.', 1)[0]
            cap, _ = Capability.objects.get_or_create(
                code=code,
                defaults={
                    'module': modules[domain], 'name': name,
                    'is_sensitive': sensitive,
                },
            )
            caps.append(cap)

        # Superadmin: todas las capacidades. Las CRUD quedan a nivel FULL (default
        # de RoleCapability) → implican view/create/edit/full; las nombradas por
        # membresía. Además hace bypass en el resolver.
        role, _ = Role.objects.get_or_create(
            code=SUPERADMIN_ROLE_CODE, defaults={'name': 'Superadministrador'},
        )
        role.capabilities.set(caps)

        # Rol base del comprador (DEC-AUTHZ-BUYER): las acciones nombradas
        # ``account.*`` que gobiernan el menú de cuenta dinámico.
        buyer_caps = [c for c in caps if c.code.startswith('account.')]
        buyer_role, _ = Role.objects.get_or_create(
            code=BUYER_ROLE_CODE, defaults={'name': 'Comprador'},
        )
        buyer_role.capabilities.set(buyer_caps)

        # Capacidades de "cuenta propia": todo usuario autenticado —incluido
        # staff no-superadmin— gestiona SU propia cuenta (perfil, contraseña,
        # baja, historial de pago). Se siembran en TODOS los roles para no dejar
        # a nadie fuera de su propia cuenta (DEC-ENF-01). ``add`` es idempotente.
        # DEC-ENF-01: capacidades de cuenta propia — se siembran en TODOS los
        # roles para que nadie quede fuera de su propia cuenta.
        # 'account.bus' entra aquí porque el endpoint del bus deriva el canal de
        # la sesión y sólo devuelve mensajes del propio usuario: gatearlo con una
        # capacidad de dominio (p. ej. notificaciones) dejaría sin eventos de pago
        # a quien no la tenga, siendo suyos.
        self_account_codes = {
            'account.profile', 'account.password', 'account.security',
            'account.deactivate', 'account.payments', 'account.bus',
        }
        self_account_caps = [c for c in caps if c.code in self_account_codes]
        roles_patched = 0
        for r in Role.objects.all():
            r.capabilities.add(*self_account_caps)
            roles_patched += 1

        self.stdout.write(self.style.SUCCESS(
            f'authz self-account caps sembradas en {roles_patched} roles.'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'authz seed OK: {len(modules)} módulos, {len(caps)} capacidades '
            f'({len(CRUD_NOUNS)} CRUD sustantivo + {len(NAMED_ACTIONS)} nombradas), '
            f'rol {SUPERADMIN_ROLE_CODE} con {role.capabilities.count()} y '
            f'rol {BUYER_ROLE_CODE} con {buyer_role.capabilities.count()}.'
        ))
