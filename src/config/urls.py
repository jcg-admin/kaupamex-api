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

# Catálogos públicos de envío (GAP-C1 / H-12). Se importan explícitamente
# porque las rutas son anónimas y viven en el URLconf raíz, no bajo el
# ``include`` de ``delivery`` (que es todo admin/comprador autenticado).
from addons.delivery.views import (
    ShippingMethodListPublicView,
    ShippingZoneListPublicView,
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
    path('api/v1/logistics/', include('addons.delivery.webhook_urls')),

    # --- API v2 ---
    # chartsize_v2 ANTES de catalogue_v2: más específico (/products/<slug>/variants/)
    # debe resolverse antes del catch-all de catalogue_v2 (/products/<slug>/).

    # ─── API v2 (F2: cart, wishlist, referral, notifications) ───────────────────
    # SOL-011 T-06: logs tecnicos read-only (UC-ADM-06, DEC-LOG-08 revisada).
    path('api/v2/admin/',          include(('addons.observability.admin_urls', 'admin_core'), namespace='admin_core_v2')),
    path('api/v2/notifications/',  include(('addons.mail.urls', 'notifications'),     namespace='notifications_v2')),
    path('api/v2/bus/',            include(('addons.bus.urls', 'bus'),                 namespace='bus_v2')),
    path('api/v2/admin/',          include(('addons.mail.admin_notifications', 'admin_notifications'),
                                           namespace='admin_notifications_v2')),

    # ─── Retirados (SOL-098 aplicada a las familias) ──────────────────────────
    # ``contact`` · ``referral`` · ``returns`` · ``reviews`` · ``wishlist`` se
    # retiraron del
    # árbol: eran superficie REST con 0 modelos, y su dominio ya vive en el
    # addon destino. Sus rutas vuelven con la familia que las hospeda —
    # ``contacts``, ``website_sale``, ``stock``, ``rating`` y
    # ``website_sale_wishlist`` respectivamente.

    # ─── API v2 (F3: support) ──────────────────────────────
    # El recorrido del comprador sobre su venta lo sirve ``sale`` — es donde
    # la referencia lo pone (``sale/controllers/portal.py`` → ``/my/orders``).
    # El prefijo público sigue siendo ``/orders/``: el comprador habla de sus
    # pedidos, no de las ventas de la tienda.
    path('api/v2/orders/',                include(('addons.sale.urls', 'sale'),                   namespace='sale_v2')),
    # El backoffice es de ``sale_management`` — la referencia separa gestionar
    # de comprar, y el espejo las mezclaba en un solo addon.
    path('api/v2/admin/',                 include(('addons.sale_management.admin_urls', 'admin_sale'),
                                                  namespace='admin_sale_v2')),
    path('api/v2/support/',               include(('addons.helpdesk.urls', 'support'),             namespace='support_v2')),

    # ─── API v2 (F4: inventory admin + catalogue admin) ───────────────────────

    # ─── API v2 (F5: logistics/shipments, newsletter, contact, pages, backups,
    #             reports, auth §2.1) ────────────────────────────────────────
    path('api/v2/',            include(('addons.delivery.urls', 'logistics'), namespace='logistics_v2')),
    path('api/v2/newsletter/', include(('addons.website_mass_mailing.urls', 'website_mass_mailing'), namespace='newsletter_v2')),
    path('api/v2/admin/',      include(('addons.mass_mailing.admin_urls', 'admin_newsletter'),   namespace='admin_newsletter_v2')),
    path('api/v2/admin/',      include(('addons.auto_backup.admin_urls', 'admin_backups'),         namespace='admin_backups_v2')),
    # T-214: consulta pública SEPOMEX de CP → asentamientos (autocompletado de direcciones)
    # DEC-08/09: capacidades del usuario + menú admin dinámico (podado por capacidad)
    path('api/v2/authz/',      include(('addons.authz.urls', 'authz'),                         namespace='authz_v2')),
    # DEC-01 (~authz_totp): gestión del 2FA TOTP del usuario autenticado
    path('api/v2/authz/totp/', include(('addons.authz_totp.urls', 'authz_totp'),               namespace='authz_totp_v2')),
    # ~auth_ldap: CRUD de configuraciones LDAP por Company (permissions.ldap)
    path('api/v2/authz/',      include(('addons.authz_ldap.urls', 'authz_ldap'),               namespace='authz_ldap_v2')),
    # ~auth_oauth: login federado OAuth2 + proveedores (permissions.oauth)
    path('api/v2/authz/',      include(('addons.authz_oauth.urls', 'authz_oauth'),             namespace='authz_oauth_v2')),
    # ~auth_totp_mail: código 2FA por correo + invitación
    path('api/v2/authz/totp-mail/', include(('addons.authz_totp_mail.urls', 'authz_totp_mail'), namespace='authz_totp_mail_v2')),
    # ~auth_passkey: login WebAuthn + gestión de passkeys (account.security)
    path('api/v2/authz/',      include(('addons.authz_passkey.urls', 'authz_passkey'),         namespace='authz_passkey_v2')),
    # ~auth_signup: alta/set-password/reset por token firmado (pre-auth)
    path('api/v2/authz/',      include(('addons.authz_signup.controllers.urls', 'authz_signup'),           namespace='authz_signup_v2')),
    # G-PERM-01: catálogo de roles para el selector de /admin/permissions (UC-ADM-02)
    path('api/v2/admin/',      include(('addons.authz.admin_urls', 'admin_authz'),             namespace='admin_authz_v2')),
    # UC-PLT-12: consola L0 del operador Kaupamex — directorio de tenants (platform.provision)
    path('api/v2/platform/',   include(('addons.company.urls', 'company'),                     namespace='company')),

    # ─── API v2 (F6: payments + checkout) ─────────────────────────────────────
    # GAP-C1: public shipping methods for checkout (unauthenticated)
    path('api/v2/shipping-methods/', ShippingMethodListPublicView.as_view(), name='public-shipping-methods'),
    # H-12: public shipping zones + delivery-time catalog (unauthenticated)
    path('api/v2/shipping-zones/', ShippingZoneListPublicView.as_view(), name='public-shipping-zones'),

    # ─── API v2 (§4 same-path passthrough: remaining apps not yet in v2) ────
    # These keep the same URL structure — only prefix changes from v1 to v2.
    # DEC-V2-05 sancionados (login, register, refresh, logout, change-password)
    # appear here via users.urls — correct behaviour (same at both v1 and v2).
    # F6 (payments initiate/checkout) excluded — those are Tier B.
    path('api/v2/admin/',   include(('addons.loyalty.urls', 'admin_voucher'),                           namespace='admin_voucher_v2')),
    path('api/v2/admin/',   include(('addons.helpdesk.admin_urls', 'admin_support'),                     namespace='admin_support_v2')),
    path('api/v2/admin/',   include(('addons.website.admin_urls', 'admin_static_content'),      namespace='admin_static_content_v2')),
    # Chartsize admin (variants) after catalogue CRUD so POST /api/v2/admin/products/
    # resolves to ProductAdminViewSet, not chartsize DefaultRouter root (GET-only).
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
            f'Ejecuta: npm run build en kaupamex-ui'
        )
    return FileResponse(open(index_path, 'rb'), content_type='text/html')


if getattr(settings, 'UI_DIST', None):
    urlpatterns += [
        re_path(r'^(?!api/|admin/|static/|media/|.*\.(?:js|css|map|ico|png|jpg|svg|woff2?|ttf|eot)).*$', serve_spa),
    ]


