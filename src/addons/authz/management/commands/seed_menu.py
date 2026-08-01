"""Seed idempotente del menú admin (DEC-08/09, árbol de 3 niveles).

Proyecta el manifiesto de navegación a filas ``authz_menu_item``, etiquetando
cada **hoja** con la capacidad que su endpoint enforce (verificado en código,
:ref:`analisis-jerarquia-menu-admin`) para no mostrar destinos que darían 403.
Idempotente por ``key`` (``update_or_create``). Requiere ``seed_authz`` antes.

Estructura recursiva de un nodo: ``(key, label, route, cap_code, [hijos])``.
Secciones (nivel 0) y agrupadores (nivel 1 sin ruta, p.ej. Reportes) llevan
``route=''`` y ``cap_code=None``; se podan si no les queda hijo visible.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from addons.authz.models import Capability
from addons.authz_menu.models import MenuItem


def _leaf(key, label, route, cap):
    return (key, label, route, cap, [])


def _group(key, label, children):
    return (key, label, '', None, children)


MENU = [
    _group('sec-principal', 'Principal', [
        _leaf('dashboard', 'Dashboard', '/admin', 'reports'),
    ]),
    _group('sec-catalogo', 'Catálogo', [
        _leaf('productos', 'Productos', '/admin/products', 'catalogue'),
        _leaf('producto-nuevo', 'Crear Producto', '/admin/products/new', 'catalogue'),
        _leaf('categorias', 'Categorías', '/admin/categories', 'catalogue'),
        _leaf('descuentos', 'Descuentos', '/admin/product-discounts', 'catalogue'),
        _leaf('price-sync', 'Sincronización de precios', '/admin/price-sync', 'catalogue'),
    ]),
    _group('sec-ventas', 'Ventas', [
        _leaf('pedidos', 'Pedidos', '/admin/orders', 'orders'),
        _leaf('pedidos-panel', 'Panel de pedidos', '/admin/orders-dashboard', 'orders'),
        _leaf('pagos', 'Pagos', '/admin/payments', 'payments'),
        _leaf('contracargos', 'Contracargos', '/admin/chargebacks', 'payments'),
        _leaf('devoluciones', 'Devoluciones', '/admin/returns', 'returns'),
        _leaf('cupones', 'Cupones', '/admin/vouchers', 'vouchers'),
    ]),
    _group('sec-marketing', 'Marketing', [
        # Reseñas admin = gestión/moderación para marketing + comportamiento
        # (no la reseña que envía el comprador — eso es storefront). Por eso
        # vive en Marketing junto al resto de UGC/engagement, no en Catálogo.
        _leaf('resenas', 'Reseñas', '/admin/reviews/moderation', 'moderation'),
        # Q&A de producto: el grupo vuelve con el cluster ``website_sale`` que
        # lo hospeda (H-QUESTIONS-01). Su capacidad murió con el addon.
        _group('grp-newsletter', 'Newsletter', [
            _leaf('newsletter-compose', 'Redactar', '/admin/newsletter/compose', 'newsletter'),
            _leaf('newsletter-subs', 'Suscriptores', '/admin/newsletter/subscribers', 'newsletter'),
        ]),
        _leaf('notificaciones', 'Notificaciones', '/admin/notifications/compose', 'notifications'),
        _leaf('listas-deseos', 'Listas de deseos', '/admin/marketing/wishlist', 'users'),
        _leaf('banners', 'Banners de portada', '/admin/banners', 'banners'),
    ]),
    _group('sec-clientes', 'Clientes', [
        _leaf('usuarios', 'Usuarios', '/admin/users', 'users'),
        _leaf('permisos', 'Permisos', '/admin/permissions', 'permissions'),
        _leaf('soporte', 'Soporte (Tickets)', '/admin/support', 'support'),
        _leaf('contacto', 'Mensajes de contacto', '/admin/contact/messages', 'support'),
    ]),
    _group('sec-operaciones', 'Operaciones', [
        _leaf('inventario', 'Inventario', '/admin/inventory', 'inventory'),
        _leaf('logistica', 'Logística', '/admin/logistics', 'logistics'),
        _leaf('paqueterias', 'Paqueterías', '/admin/couriers', 'logistics'),
        _leaf('zonas-entrega', 'Zonas de entrega', '/admin/shipping-zones', 'settings'),
        _group('grp-reportes', 'Reportes', [
            _leaf('reportes-dashboard', 'Dashboard', '/admin/reports', 'reports'),
            _leaf('reportes-ventas', 'Ventas', '/admin/reports/sales', 'reports'),
            _leaf('reportes-top', 'Top sellers', '/admin/reports/top-sellers', 'reports'),
            _leaf('reportes-rfm', 'Clientes RFM', '/admin/reports/customers-rfm', 'reports'),
        ]),
    ]),
    _group('sec-sistema', 'Sistema', [
        _leaf('logs', 'Logs técnicos', '/admin/logs', 'audit'),
        _leaf('auditoria', 'Auditoría', '/admin/audit-log', 'audit'),
    ]),
    _group('sec-configuracion', 'Configuración', [
        _leaf('config', 'Configuración', '/admin/config', 'settings'),
        _leaf('config-sistema', 'Configuración Sistema', '/admin/system-settings', 'settings'),
        _leaf('contenido-estatico', 'Contenido estático', '/admin/content', 'settings'),
        _leaf('backups', 'Backups', '/admin/backups', 'backups'),
    ]),
]


# Menú de CUENTA del comprador (audience='account', DEC-AUTHZ-BUYER). Mismo
# mecanismo registro-dirigido: cada hoja lleva su capacidad ``account.*`` (rol
# 'comprador'). Una sola sección 'Mi cuenta'; el UI aplana sus hijos. Agregar
# una entrada aquí = sembrar una fila, sin tocar AccountLayout.
ACCOUNT_MENU = [
    _group('sec-cuenta', 'Mi cuenta', [
        _leaf('cuenta-resumen', 'Resumen', '/account', 'account.overview'),
        _leaf('cuenta-pedidos', 'Mis pedidos', '/account/orders', 'account.orders'),
        _leaf('cuenta-favoritos', 'Mis favoritos', '/account/wishlist', 'account.wishlist'),
        _leaf('cuenta-devoluciones', 'Mis devoluciones', '/account/returns', 'account.returns'),
        _leaf('cuenta-soporte', 'Soporte', '/support/tickets', 'account.support'),
        _leaf('cuenta-notificaciones', 'Notificaciones', '/account/notifications', 'account.notifications'),
        _leaf('cuenta-perfil', 'Mi perfil', '/account/profile', 'account.profile'),
        _leaf('cuenta-password', 'Cambiar contraseña', '/account/change-password', 'account.password'),
        _leaf('cuenta-baja', 'Dar de baja', '/account/deactivate', 'account.deactivate'),
    ]),
]


class Command(BaseCommand):
    help = 'Siembra el menú admin (authz_menu_item), árbol de 3 niveles, idempotente.'

    @transaction.atomic
    def handle(self, *args, **options):
        self._caps = {c.code: c for c in Capability.objects.all()}
        self._n = 0
        self._seen = set()
        for order, node in enumerate(MENU):
            self._seed(node, parent=None, order=order,
                       audience=MenuItem.AUDIENCE_ADMIN)
        for order, node in enumerate(ACCOUNT_MENU):
            self._seed(node, parent=None, order=order,
                       audience=MenuItem.AUDIENCE_ACCOUNT)
        # Re-seed autoritativo: podar filas que ya no están en MENU (p.ej. una
        # sección movida/renombrada). Sin esto, update_or_create deja huérfanos
        # que aparecerían como secciones vacías. Idempotente: en un árbol ya
        # sembrado el keyset coincide y no borra nada.
        stale = MenuItem.objects.exclude(key__in=self._seen)
        pruned = stale.count()
        stale.delete()
        self.stdout.write(self.style.SUCCESS(
            f'{self._n} entradas de menú sembradas (árbol de 3 niveles); '
            f'{pruned} obsoletas podadas.'
        ))

    def _seed(self, node, parent, order, audience):
        key, label, route, cap_code, children = node
        cap = None
        if cap_code:
            cap = self._caps.get(cap_code)
            if cap is None:
                self.stderr.write(
                    f'  ADVERTENCIA: capacidad {cap_code} no existe; item {key} '
                    f'queda sin candado. Corre seed_authz primero.'
                )
        item, _ = MenuItem.objects.update_or_create(
            key=key,
            defaults=dict(parent=parent, label=label, route=route, icon='',
                          order=order, required_capability=cap, is_active=True,
                          audience=audience),
        )
        self._seen.add(key)
        self._n += 1
        for child_order, child in enumerate(children):
            self._seed(child, parent=item, order=child_order, audience=audience)
