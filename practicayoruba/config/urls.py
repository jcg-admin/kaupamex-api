import os

from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, Http404
from django.urls import path, include, re_path

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

urlpatterns = [
    path('admin/', admin.site.urls),

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

    # --- API v1 ---
    path('api/v1/auth/',      include('apps.users.urls')),
    path('api/v1/config/',    include('apps.settings_app.urls', namespace='settings_app')),
    path('api/v1/admin/',     include('apps.users.admin_urls', namespace='admin_users')),
    path('api/v1/admin/',     include('apps.catalogue.admin_urls', namespace='admin_catalogue')),
    path('api/v1/admin/',     include('apps.settings_app.admin_urls', namespace='admin_settings')),
    path('api/v1/admin/',     include('apps.inventory.urls',         namespace='admin_inventory')),
    # ─── URLs específicas PRIMERO (antes del catch-all /api/v1/) ────────────────
    path('api/v1/cart/',      include('apps.cart.urls',        namespace='cart')),
    path('api/v1/admin/',     include('apps.voucher.urls',     namespace='admin_voucher')),
    path('api/v1/account/',   include('apps.referral.urls',    namespace='referral')),
    path('api/v1/wishlist/',  include('apps.wishlist.urls',    namespace='wishlist')),
    path('api/v1/payments/', include('apps.payments.urls',     namespace='payments')),
    path('api/v1/checkout/', include('apps.payments.checkout_urls')),
    # P-17 browse overrides must precede apps.catalogue.urls so /api/v1/catalogue/search/
    # resolves to the new wrapper (normalized_query, persists to apps.search_history).
    path('api/v1/',           include('apps.catalogue.browse_public_urls',
                                      namespace='catalogue_browse_public')),
    path('api/v1/catalogue/', include('apps.catalogue.urls',   namespace='catalogue')),
    path('api/v1/catalogue/', include('apps.chartsize.urls',   namespace='chartsize')),
    path('api/v1/admin/',     include('apps.chartsize.admin_urls', namespace='admin_chartsize')),
    path('api/v1/admin/',    include('apps.orders.admin_urls')),
    path('api/v1/support/',   include('apps.support.urls',          namespace='support')),
    path('api/v1/admin/',     include('apps.support.admin_urls',    namespace='admin_support')),
    path('api/v1/returns/',   include('apps.returns.urls',          namespace='returns')),
    path('api/v1/admin/',     include('apps.returns.admin_urls',    namespace='admin_returns')),
    path('api/v1/notifications/', include('apps.notifications.urls', namespace='notifications')),
    path('api/v1/admin/',     include('apps.notifications.admin_urls', namespace='admin_notifications')),
    path('api/v1/contact/',   include('apps.contact.urls',          namespace='contact')),
    path('api/v1/admin/',     include('apps.contact.admin_urls',    namespace='admin_contact')),
    path('api/v1/newsletter/', include('apps.newsletter.urls',      namespace='newsletter')),
    path('api/v1/admin/',     include('apps.newsletter.admin_urls', namespace='admin_newsletter')),
    path('api/v1/products/',  include('apps.questions.urls',        namespace='questions')),
    path('api/v1/admin/',     include('apps.questions.admin_urls',  namespace='admin_questions')),
    path('api/v1/admin/',     include('apps.reports.admin_urls',    namespace='admin_reports')),

    # ─── P-13 logistics + UC-CFG-04 static content ─────────────────────────────
    path('api/v1/logistics/', include('apps.logistics.urls',        namespace='logistics')),
    path('api/v1/admin/',     include('apps.static_content.admin_urls',
                                      namespace='admin_static_content')),

    # ─── P-14 reviews ──────────────────────────────────────────────────────────
    path('api/v1/products/',  include('apps.reviews.urls',          namespace='reviews')),
    path('api/v1/admin/',     include('apps.reviews.admin_urls',    namespace='admin_reviews')),

    # ─── P-17 catalogue browse + search history ────────────────────────────────
    path('api/v1/search/',    include('apps.search_history.urls',   namespace='search_history')),
    path('api/v1/products/',  include('apps.catalogue.browse_product_urls',
                                      namespace='catalogue_browse_product')),
    path('api/v1/admin/',     include('apps.catalogue.browse_admin_urls',
                                      namespace='catalogue_browse_admin')),
    path('api/v1/admin/',     include('apps.backups.admin_urls',
                                      namespace='admin_backups')),
    # H-CICLO80-01: AdminPaymentListView registrada — faltaba el endpoint
    # UC-PAY-11 /api/v1/admin/payments/ que el UI consulta via useAdminPayments.
    path('api/v1/admin/',     include('apps.payments.admin_urls',
                                      namespace='admin_payments')),

    # ─── Orders bajo /api/v1/orders/ (DEC-ORD-01: alineado con UI productiva
    #     y convencion REST estandar; antes era catch-all en /api/v1/).
    path('api/v1/orders/',   include('apps.orders.urls',       namespace='orders')),

    # ─── API v2 (F1: superficie unificada de productos) ────────────────────────
    # chartsize_v2 ANTES de catalogue_v2: más específico (/products/<slug>/variants/)
    # debe resolverse antes del catch-all de catalogue_v2 (/products/<slug>/).
    path('api/v2/products/', include('apps.chartsize.urls_v2',  namespace='chartsize_v2')),
    path('api/v2/',          include('apps.catalogue.urls_v2',  namespace='catalogue_v2')),

    # ─── API v2 (F2: cart, wishlist, referral, notifications) ───────────────────
    path('api/v2/cart/',           include('apps.cart.urls_v2',          namespace='cart_v2')),
    path('api/v2/wishlist/',       include('apps.wishlist.urls_v2',       namespace='wishlist_v2')),
    path('api/v2/account/',        include('apps.referral.urls_v2',       namespace='referral_v2')),
    path('api/v2/notifications/',  include('apps.notifications.urls_v2',  namespace='notifications_v2')),
    path('api/v2/admin/',          include('apps.notifications.admin_notifications_v2',
                                           namespace='admin_notifications_v2')),

    # ─── API v2 (F3: orders, returns, reviews, questions, support) ──────────────
    path('api/v2/orders/',                include('apps.orders.urls_v2',            namespace='orders_v2')),
    path('api/v2/return-requests/',       include('apps.returns.urls_v2',           namespace='returns_v2')),
    path('api/v2/admin/return-requests/', include('apps.returns.admin_urls_v2',     namespace='admin_returns_v2')),
    path('api/v2/products/',              include('apps.reviews.urls_v2',           namespace='reviews_v2')),
    path('api/v2/admin/',                 include('apps.reviews.admin_urls_v2',     namespace='admin_reviews_v2')),
    path('api/v2/products/',              include('apps.questions.urls_v2',         namespace='questions_v2')),
    path('api/v2/admin/',                 include('apps.questions.admin_urls_v2',   namespace='admin_questions_v2')),
    path('api/v2/support/',               include('apps.support.urls_v2',           namespace='support_v2')),

    # ─── API v2 (F4: inventory admin + catalogue admin) ───────────────────────
    path('api/v2/admin/inventory/', include('apps.inventory.urls_v2',       namespace='admin_inventory_v2')),
    path('api/v2/admin/',           include('apps.catalogue.admin_urls_v2', namespace='admin_catalogue_v2')),

    # ─── API v2 (F5: logistics/shipments, newsletter, contact, pages, backups,
    #             reports, auth §2.1) ────────────────────────────────────────
    path('api/v2/',            include('apps.logistics.urls_v2',           namespace='logistics_v2')),
    path('api/v2/newsletter/', include('apps.newsletter.urls_v2',          namespace='newsletter_v2')),
    path('api/v2/admin/',      include('apps.newsletter.admin_urls_v2',    namespace='admin_newsletter_v2')),
    path('api/v2/admin/',      include('apps.contact.admin_urls_v2',       namespace='admin_contact_v2')),
    path('api/v2/admin/',      include('apps.settings_app.admin_urls_v2',  namespace='admin_settings_v2')),
    path('api/v2/admin/',      include('apps.backups.admin_urls_v2',       namespace='admin_backups_v2')),
    path('api/v2/admin/',      include('apps.reports.admin_urls_v2',       namespace='admin_reports_v2')),
    path('api/v2/auth/',       include('apps.users.auth_urls_v2',          namespace='auth_v2')),
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


