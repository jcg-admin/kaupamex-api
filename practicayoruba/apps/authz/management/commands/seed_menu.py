"""Seed idempotente del menú admin (DEC-08/09).

Proyecta el manifiesto de navegación (secciones → items) a filas
``authz_menu_item``, etiquetando cada hoja con su ``Capability``. Idempotente
por ``key`` (``update_or_create``). Requiere ``seed_authz`` corrido antes (las
capacidades deben existir).

El manifiesto es la fuente única: el sidebar de React (``AdminLayout``) consume
``/api/v2/authz/me/menu/`` — no vuelve a declarar la estructura.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.authz.models import Capability, MenuItem

# (key_seccion, label_seccion, [ (key_item, label, route, cap_code) ... ])
MENU = [
    ('sec-principal', 'Principal', [
        ('dashboard', 'Dashboard', '/admin', 'reports.view'),
    ]),
    # Cada hoja lleva la MISMA capacidad que el endpoint de destino enforce
    # (permission_map/required_capability), para no mostrar destinos que darían
    # 403. Verificado contra las vistas admin (B2).
    ('sec-catalogo', 'Catálogo', [
        ('productos', 'Productos', '/admin/products', 'catalogue.manage'),
        ('producto-nuevo', 'Crear Producto', '/admin/products/new', 'catalogue.manage'),
        ('categorias', 'Categorías', '/admin/categories', 'catalogue.manage'),
    ]),
    ('sec-ventas', 'Ventas', [
        ('pedidos', 'Pedidos', '/admin/orders', 'orders.manage'),
        ('pagos', 'Pagos', '/admin/payments', 'payments.manage'),
        ('devoluciones', 'Devoluciones', '/admin/returns', 'returns.manage'),
        ('cupones', 'Cupones', '/admin/vouchers', 'vouchers.view'),
    ]),
    ('sec-clientes', 'Clientes', [
        ('usuarios', 'Usuarios', '/admin/users', 'users.view'),
        ('permisos', 'Permisos', '/admin/permissions', 'permissions.manage'),
        ('soporte', 'Soporte (Tickets)', '/admin/support', 'support.manage'),
    ]),
    ('sec-operaciones', 'Operaciones', [
        ('inventario', 'Inventario', '/admin/inventory', 'inventory.manage'),
        ('logistica', 'Logística', '/admin/logistics', 'logistics.manage'),
        ('paqueterias', 'Paqueterías', '/admin/couriers', 'logistics.manage'),
        ('zonas-entrega', 'Zonas de entrega', '/admin/shipping-zones', 'settings.manage'),
        ('reportes-dashboard', 'Reportes: Dashboard', '/admin/reports', 'reports.view'),
        ('reportes-ventas', 'Reportes: Ventas', '/admin/reports/sales', 'reports.view'),
        ('reportes-top', 'Reportes: Top sellers', '/admin/reports/top-sellers', 'reports.view'),
        ('reportes-rfm', 'Reportes: Clientes RFM', '/admin/reports/customers-rfm', 'reports.view'),
    ]),
    ('sec-sistema', 'Sistema', [
        ('logs', 'Logs técnicos', '/admin/logs', 'audit.view'),
        ('auditoria', 'Auditoría', '/admin/audit-log', 'audit.view'),
    ]),
    ('sec-configuracion', 'Configuración', [
        ('config', 'Configuración', '/admin/config', 'settings.manage'),
        ('config-sistema', 'Configuración Sistema', '/admin/system-settings', 'settings.manage'),
        ('backups', 'Backups', '/admin/backups', 'backups.manage'),
    ]),
]


class Command(BaseCommand):
    help = 'Siembra el menú admin (authz_menu_item) desde el manifiesto, idempotente.'

    @transaction.atomic
    def handle(self, *args, **options):
        caps = {c.code: c for c in Capability.objects.all()}
        secciones = 0
        items = 0
        for sec_order, (sec_key, sec_label, children) in enumerate(MENU):
            section, _ = MenuItem.objects.update_or_create(
                key=sec_key,
                defaults=dict(parent=None, label=sec_label, route='', icon='',
                              order=sec_order, required_capability=None, is_active=True),
            )
            secciones += 1
            for it_order, (key, label, route, cap_code) in enumerate(children):
                cap = caps.get(cap_code)
                if cap is None:
                    self.stderr.write(
                        f'  ADVERTENCIA: capacidad {cap_code} no existe; '
                        f'item {key} queda sin candado. Corre seed_authz primero.'
                    )
                MenuItem.objects.update_or_create(
                    key=key,
                    defaults=dict(parent=section, label=label, route=route, icon='',
                                  order=it_order, required_capability=cap, is_active=True),
                )
                items += 1
        self.stdout.write(self.style.SUCCESS(
            f'{secciones} secciones, {items} items de menú sembrados.'
        ))
