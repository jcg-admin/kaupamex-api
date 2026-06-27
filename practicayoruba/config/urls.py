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

    # --- API v2 — Checkout API (ADR-018) ---
    # Solo endpoints nuevos de pago en sitio. Los webhooks siguen en v1
    # por DEC-V2-02: /api/v1/payments/webhooks/* permanecen en v1 SIEMPRE.
    path('api/v2/payments/', include('apps.payments.v2_urls',
                                     namespace='payments_v2')),

    # ─── Orders bajo /api/v1/orders/ (DEC-ORD-01: alineado con UI productiva
    #     y convencion REST estandar; antes era catch-all en /api/v1/).
    path('api/v1/orders/',   include('apps.orders.urls',       namespace='orders')),
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


