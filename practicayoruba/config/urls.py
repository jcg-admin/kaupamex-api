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

    # --- API v1 — auth + config (DEC-V2-05: auth stays on v1 forever) ---
    path('api/v1/auth/',      include('apps.users.urls')),
    path('api/v1/config/',    include('apps.settings_app.urls',        namespace='settings_app')),
    path('api/v1/admin/',     include('apps.users.admin_urls',         namespace='admin_users')),
    path('api/v1/admin/',     include('apps.settings_app.admin_urls',  namespace='admin_settings')),

    # --- API v1 — cart, voucher, referral, wishlist, payments ---
    path('api/v1/cart/',      include('apps.cart.urls',        namespace='cart')),
    path('api/v1/admin/',     include('apps.voucher.urls',     namespace='admin_voucher')),
    path('api/v1/account/',   include('apps.referral.urls',    namespace='referral')),
    path('api/v1/wishlist/',  include('apps.wishlist.urls',    namespace='wishlist')),
    path('api/v1/payments/', include('apps.payments.urls',     namespace='payments')),
    path('api/v1/checkout/', include('apps.payments.checkout_urls')),

    # --- API v1 — catalogue (chartsize + browse_product only; main catalogue moved to v2) ---
    path('api/v1/catalogue/', include('apps.chartsize.urls',   namespace='chartsize')),
    path('api/v1/admin/',     include('apps.chartsize.admin_urls', namespace='admin_chartsize')),
    path('api/v1/products/',  include('apps.catalogue.browse_product_urls',
                                      namespace='catalogue_browse_product')),

    # --- API v1 — notifications, questions, reports, static content, reviews, search, backups ---
    path('api/v1/notifications/', include('apps.notifications.urls',    namespace='notifications')),
    path('api/v1/admin/',     include('apps.notifications.admin_urls',  namespace='admin_notifications')),
    path('api/v1/products/',  include('apps.questions.urls',            namespace='questions')),
    path('api/v1/admin/',     include('apps.questions.admin_urls',      namespace='admin_questions')),
    path('api/v1/admin/',     include('apps.reports.admin_urls',        namespace='admin_reports')),
    path('api/v1/admin/',     include('apps.static_content.admin_urls', namespace='admin_static_content')),
    path('api/v1/products/',  include('apps.reviews.urls',              namespace='reviews')),
    path('api/v1/admin/',     include('apps.reviews.admin_urls',        namespace='admin_reviews')),
    path('api/v1/search/',    include('apps.search_history.urls',       namespace='search_history')),
    path('api/v1/admin/',     include('apps.backups.admin_urls',        namespace='admin_backups')),
    path('api/v1/admin/',     include('apps.payments.admin_urls',       namespace='admin_payments')),

    # --- API v1 — logistics webhook (DEC-V2-02: stays on v1 FOREVER) ---
    path('api/v1/logistics/', include('apps.logistics.webhook_urls')),

    # --- API v2 — Payments (ADR-018 Checkout API; webhooks stay on v1 per DEC-V2-02) ---
    path('api/v2/payments/', include('apps.payments.v2_urls',
                                     namespace='payments_v2')),

    # --- API v2 — Catalogue (M-02) ---
    path('api/v2/catalogue/', include('apps.catalogue.urls',
                                      namespace='catalogue_v2')),
    path('api/v2/admin/',     include('apps.catalogue.admin_urls',
                                      namespace='admin_catalogue_v2')),
    # chartsize: nested variants + price under /api/v2/admin/products/ and /variants/
    path('api/v2/admin/',     include('apps.chartsize.admin_urls',
                                      namespace='admin_chartsize_v2')),

    # --- API v2 — Orders (M-03) ---
    path('api/v2/orders/',    include('apps.orders.urls',
                                      namespace='orders_v2')),
    path('api/v2/admin/',     include('apps.orders.admin_urls',
                                      namespace='admin_orders_v2')),

    # --- API v2 — Inventory (M-04) ---
    path('api/v2/admin/',     include('apps.inventory.urls',
                                      namespace='admin_inventory_v2')),

    # --- API v2 — Support (M-05) ---
    path('api/v2/support/',    include('apps.support.urls',
                                       namespace='support_v2')),
    path('api/v2/admin/',      include('apps.support.admin_urls',
                                       namespace='admin_support_v2')),

    # --- API v2 — Returns (M-05) ---
    path('api/v2/return-requests/', include('apps.returns.urls',
                                            namespace='returns_v2')),
    path('api/v2/admin/',      include('apps.returns.admin_urls',
                                       namespace='admin_returns_v2')),

    # --- API v2 — Newsletter (M-05) ---
    path('api/v2/newsletter/', include('apps.newsletter.urls',
                                       namespace='newsletter_v2')),
    path('api/v2/admin/',      include('apps.newsletter.admin_urls',
                                       namespace='admin_newsletter_v2')),

    # --- API v2 — Contact (M-05) ---
    path('api/v2/contact/',    include('apps.contact.urls',
                                       namespace='contact_v2')),
    path('api/v2/admin/',      include('apps.contact.admin_urls',
                                       namespace='admin_contact_v2')),

    # --- API v2 — Logistics (M-05; webhook excluded per DEC-V2-02) ---
    path('api/v2/logistics/',  include('apps.logistics.urls',
                                       namespace='logistics_v2')),
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
