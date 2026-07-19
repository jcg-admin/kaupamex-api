import os

from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, Http404
from django.urls import path, include, re_path

from addons.settings_app.views import ShippingMethodListPublicView, ShippingZoneListPublicView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

# Seguridad (H-11): el admin nativo de Django se monta SOLO cuando
# DJANGO_ADMIN_ENABLED (default = DEBUG). En produccion queda apagado para no
# exponer /admin/ como login de fuerza bruta; el backoffice real es el admin
# React + DRF /api/v2/admin/. Ver reportes-agentes-admin (H-11).
_admin_urls = (
    [path('admin/', admin.site.urls)] if settings.DJANGO_ADMIN_ENABLED else []
)

urlpatterns = _admin_urls + [
    # --- OpenAPI Schema (JSON/YAML) ---
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),

    # --- Swagger UI ---
    path(
        'api/schema/swagger-ui/',
        SpectacularSwaggerView.as_view(url_name='schema'),
        name='swagger-ui',
    ),

    # --- Redoc ---
    path(
        'api/schema/redoc/',
        SpectacularRedocView.as_view(url_name='schema'),
        name='redoc',
    ),

    # --- API v1 (DEC-V2-02: webhooks registrados con terceros — no renombrar) ---
    path('api/v1/payments/', include('addons.payments.webhook_urls')),
    path('api/v1/logistics/', include('addons.logistics.webhook_urls')),

    # --- API v2 ---
    # chartsize_v2 ANTES de catalogue_v2: más específico (/products/<slug>/variants/)
    # debe resolverse antes del catch-all de catalogue_v2 (/products/<slug>/).
    path('api/v2/products/', include(('addons.chartsize.urls', 'chartsize'), namespace='chartsize_v2')),
    path('api/v2/',          include(('addons.catalogue.urls', 'catalogue'), namespace='catalogue_v2')),

    # ─── API v2 (F2: cart, wishlist, referral, notifications) ───────────────────
    # SOL-011 T-06: logs tecnicos read-only (UC-ADM-06, DEC-LOG-08 revisada).
    path('api/v2/admin/',          include(('addons.observability.admin_urls', 'admin_core'), namespace='admin_core_v2')),
    path('api/v2/cart/',           include(('addons.cart.urls', 'cart'),                       namespace='cart_v2')),
    path('api/v2/wishlist/',       include(('addons.wishlist.urls', 'wishlist'),               namespace='wishlist_v2')),
    path('api/v2/admin/',          include(('addons.wishlist.admin_urls', 'admin_wishlist'),   namespace='admin_wishlist_v2')),
    path('api/v2/account/',        include(('addons.referral.urls', 'referral'),               namespace='referral_v2')),
    path('api/v2/notifications/',  include(('addons.mail.urls', 'notifications'),     namespace='notifications_v2')),
    path('api/v2/admin/',          include(('addons.mail.admin_notifications', 'admin_notifications'),
                                           namespace='admin_notifications_v2')),

    # ─── API v2 (F3: orders, returns, reviews, questions, support) ──────────────
    path('api/v2/orders/',                include(('addons.orders.urls', 'orders'),               namespace='orders_v2')),
    path('api/v2/return-requests/',       include(('addons.returns.urls', 'returns'),             namespace='returns_v2')),
    path('api/v2/admin/return-requests/', include(('addons.returns.admin_urls', 'admin_returns'), namespace='admin_returns_v2')),
    path('api/v2/products/',              include(('addons.reviews.urls', 'reviews'),             namespace='reviews_v2')),
    path('api/v2/admin/',                 include(('addons.reviews.admin_urls', 'admin_reviews'), namespace='admin_reviews_v2')),
    path('api/v2/products/',              include(('addons.questions.urls', 'questions'),         namespace='questions_v2')),
    path('api/v2/admin/',                 include(('addons.questions.admin_urls', 'admin_questions'), namespace='admin_questions_v2')),
    path('api/v2/support/',               include(('addons.support.urls', 'support'),             namespace='support_v2')),

    # ─── API v2 (F4: inventory admin + catalogue admin) ───────────────────────
    path('api/v2/admin/inventory/', include(('addons.inventory.admin_urls', 'admin_inventory_v2'), namespace='admin_inventory_v2')),
    path('api/v2/admin/',           include(('addons.catalogue.admin_urls', 'admin_catalogue'),    namespace='admin_catalogue_v2')),

    # ─── API v2 (F5: logistics/shipments, newsletter, contact, pages, backups,
    #             reports, auth §2.1) ────────────────────────────────────────
    path('api/v2/',            include(('addons.logistics.urls', 'logistics'), namespace='logistics_v2')),
    path('api/v2/newsletter/', include(('addons.website_mass_mailing.urls', 'website_mass_mailing'), namespace='newsletter_v2')),
    path('api/v2/admin/',      include(('addons.mass_mailing.admin_urls', 'admin_newsletter'),   namespace='admin_newsletter_v2')),
    path('api/v2/admin/',      include(('addons.contact.admin_urls', 'admin_contact'),         namespace='admin_contact_v2')),
    path('api/v2/admin/',      include(('addons.settings_app.admin_urls', 'admin_settings'),   namespace='admin_settings_v2')),
    path('api/v2/admin/',      include(('addons.auto_backup.admin_urls', 'admin_backups'),         namespace='admin_backups_v2')),
    path('api/v2/admin/',      include(('addons.reports.admin_urls', 'admin_reports'),         namespace='admin_reports_v2')),
    path('api/v2/auth/',       include(('addons.users.auth_urls', 'auth'),                     namespace='auth_v2')),
    # T-214: consulta pública SEPOMEX de CP → asentamientos (autocompletado de direcciones)
    path('api/v2/geo/',        include(('addons.geo.urls', 'geo'),                             namespace='geo_v2')),
    # MOD-028 FINANCE: modulo financiero (UC-FIN-01..08). Primer slice: conceptos.
    path('api/v2/finance/',    include(('addons.finance.urls', 'finance'),                     namespace='finance_v2')),
    # DEC-08/09: capacidades del usuario + menú admin dinámico (podado por capacidad)
    path('api/v2/authz/',      include(('addons.authz.urls', 'authz'),                         namespace='authz_v2')),
    # DEC-01 (~auth_totp): gestión del 2FA TOTP del usuario autenticado
    path('api/v2/authz/totp/', include(('addons.authz_totp.urls', 'authz_totp'),               namespace='authz_totp_v2')),
    # G-PERM-01: catálogo de roles para el selector de /admin/permissions (UC-ADM-02)
    path('api/v2/admin/',      include(('addons.authz.admin_urls', 'admin_authz'),             namespace='admin_authz_v2')),
    # UC-PLT-12: consola L0 del operador Kaupamex — directorio de tenants (platform.provision)
    path('api/v2/platform/',   include(('addons.company.urls', 'company'),                     namespace='company')),

    # ─── API v2 (F6: payments + checkout) ─────────────────────────────────────
    path('api/v2/payments/', include(('addons.payments.urls', 'payments'),                    namespace='payments_v2')),
    path('api/v2/checkout/', include(('addons.payments.checkout_urls', 'checkout'), namespace='checkout_v2')),
    # GAP-C1: public shipping methods for checkout (unauthenticated)
    path('api/v2/shipping-methods/', ShippingMethodListPublicView.as_view(), name='public-shipping-methods'),
    # H-12: public shipping zones + delivery-time catalog (unauthenticated)
    path('api/v2/shipping-zones/', ShippingZoneListPublicView.as_view(), name='public-shipping-zones'),

    # ─── API v2 (§4 same-path passthrough: remaining apps not yet in v2) ────
    # These keep the same URL structure — only prefix changes from v1 to v2.
    # DEC-V2-05 sancionados (login, register, refresh, logout, change-password)
    # appear here via users.urls — correct behaviour (same at both v1 and v2).
    # F6 (payments initiate/checkout) excluded — those are Tier B.
    path('api/v2/auth/',    include(('addons.users.urls', 'users'),                                      namespace='users_v2_pt')),
    path('api/v2/config/',         include(('addons.settings_app.urls', 'settings_app'),          namespace='settings_v2')),
    path('api/v2/shipping-methods/', include(('addons.settings_app.public_urls', 'public_shipping'), namespace='public_shipping_v2')),
    path('api/v2/admin/',   include(('addons.users.admin_urls', 'admin_users'),                         namespace='admin_users_v2')),
    path('api/v2/admin/',   include(('addons.loyalty.urls', 'admin_voucher'),                           namespace='admin_voucher_v2')),
    path('api/v2/admin/',   include(('addons.orders.admin_urls', 'admin_orders'),                       namespace='admin_orders_v2')),
    path('api/v2/admin/',   include(('addons.support.admin_urls', 'admin_support'),                     namespace='admin_support_v2')),
    path('api/v2/contact/', include(('addons.contact.urls', 'contact'),                                 namespace='contact_v2')),
    path('api/v2/admin/',   include(('addons.static_content.admin_urls', 'admin_static_content'),      namespace='admin_static_content_v2')),
    path('api/v2/admin/',   include(('addons.payments.admin_urls', 'admin_payments'),                   namespace='admin_payments_v2')),
    path('api/v2/admin/',   include(('addons.catalogue.browse_admin_urls', 'catalogue_browse_admin'),   namespace='catalogue_browse_admin_v2')),
    path('api/v2/',         include(('addons.catalogue.browse_public_urls', 'catalogue_browse_public'), namespace='catalogue_browse_public_v2')),
    # Chartsize admin (variants) after catalogue CRUD so POST /api/v2/admin/products/
    # resolves to ProductAdminViewSet, not chartsize DefaultRouter root (GET-only).
    path('api/v2/admin/',   include(('addons.chartsize.admin_urls', 'admin_chartsize'),                 namespace='admin_chartsize_v2')),
    # Inventory list (/inventory/) and movements (/inventory/variants/<pk>/movements/)
    # not yet ported to urls_v2; admin_inventory_v2 (line 121) handles the rest.
    path('api/v2/admin/',   include(('addons.inventory.urls', 'admin_inventory'),                        namespace='admin_inventory_pt')),
    # Search history — no v2-specific URL file; same endpoints at v2.
    path('api/v2/search/',  include(('addons.search_history.urls', 'search_history'),                    namespace='search_history_v2')),
]


# --- SPA React Router — catch-all --------------------------------------
# Django está montado en raíz (/) via WSGIScriptAlias en Apache.
# Las rutas del UI React como /cart, /checkout, /profile no existen
# en urlpatterns — Django devolvería 404 sin este handler.
# serve_spa sirve index.html para que React Router tome el control
# del routing en el navegador.
#
# Se activa SOLO cuando UI_DIST está configurado en settings.
# NO usa `if not settings.DEBUG` porque testing.py también tiene
# DEBUG=False y el catch-all no debe estar activo en tests (H-F0-001).
#
# Activo en:   producción (UI_DIST configurado en .env de la API)
# Inactivo en: tests (UI_DIST no definido en testing.py)
#              desarrollo (UI_DIST no definido en development.py;
#              el UI corre en su propio servidor webpack en :3001)

def serve_spa(request):
    """
    Catch-all para rutas del UI React (SPA).

    Sirve UI_DIST/index.html para rutas desconocidas.
    El regex del re_path excluye api/, admin/, static/ y media/
    para que DRF, Django Admin y los archivos estáticos sigan
    siendo manejados por sus propios handlers.

    FileResponse cierra el file descriptor al terminar el streaming
    — no es necesario un context manager (comportamiento documentado
    en Django: django.http.FileResponse).
    """
    index_path = os.path.join(
        getattr(settings, 'UI_DIST', ''), 'index.html'
    )
    if not os.path.isfile(index_path):
        raise Http404(
            f'UI build no encontrado en {index_path}. '
            f'Ejecuta: npm run build en e-commerce-ui'
        )
    return FileResponse(open(index_path, 'rb'), content_type='text/html')


if getattr(settings, 'UI_DIST', None):
    urlpatterns += [
        re_path(r'^(?!api/|admin/|static/|media/|.*\.(?:js|css|map|ico|png|jpg|svg|woff2?|ttf|eot)).*$', serve_spa),
    ]


