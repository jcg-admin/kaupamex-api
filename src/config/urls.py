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
from addons.delivery.controllers.main import (
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
    path('api/v1/logistics/', include('addons.delivery.controllers.webhook_urls')),
    # Webhook de base.automation (≙ `/web/hook/<uuid>` de la referencia; el
    # prefijo v1 sigue el precedente del webhook de logistics).
    path('api/v1/automation/', include('addons.base_automation.controllers.urls')),

    # Despacho genérico por modelo/método (≙ `addons/rpc` de la referencia).
    # Va FUERA de `api/v2/`: la referencia lo monta en `/json/2`, y ese prefijo
    # es el contrato que un cliente programático ya conoce. Su catch-all es
    # `re_path(r'.*')`, así que tiene que ir después de las rutas concretas de
    # su propio include, no de las del proyecto — por eso el include es uno.
    path('json/2/', include(('addons.rpc.controllers.urls', 'rpc'), namespace='rpc_v2')),

    # --- API v2 ---
    # chartsize_v2 ANTES de catalogue_v2: más específico (/products/<slug>/variants/)
    # debe resolverse antes del catch-all de catalogue_v2 (/products/<slug>/).

    # ─── API v2 (F2: cart, wishlist, referral, notifications) ───────────────────
    # SOL-011 T-06: logs tecnicos read-only (UC-ADM-06, DEC-LOG-08 revisada).
    path('api/v2/admin/',          include(('addons.base.controllers.admin_urls', 'admin_core'), namespace='admin_core_v2')),
    path('api/v2/notifications/',  include(('addons.mail.controllers.urls', 'notifications'),     namespace='notifications_v2')),
    path('api/v2/bus/',            include(('addons.bus.controllers.urls', 'bus'),                 namespace='bus_v2')),
    path('api/v2/admin/',          include(('addons.mail.controllers.admin_notifications', 'admin_notifications'),
                                           namespace='admin_notifications_v2')),
    # Carrito del escaparate — ``website_sale`` (tarea #42; adaptacion de
    # ``odoo19c: website_sale/controllers/cart.py``). El carrito ES la
    # ``SaleOrder`` en borrador; el addon solo aporta la capa HTTP.
    path('api/v2/cart/',           include(('addons.website_sale.controllers.urls', 'cart'),
                                           namespace='cart_v2')),
    # Escaparate de la misma familia (``odoo19c:
    # website_sale/controllers/main.py``): listado, ficha, categorias y
    # busqueda. Se monta en la raiz de v2 porque cuelga de tres prefijos
    # distintos; mismo patron que ``logistics``. Va DESPUES de las resenas de
    # ``rating`` para que ``products/<int>/reviews/`` resuelva primero.
    path('api/v2/',                include(('addons.website_sale.controllers.shop_urls', 'shop'),
                                           namespace='shop_v2')),
    # Historial de busquedas del comprador — vive en ``website`` porque ahi
    # vive ``SearchEntry``; lo escribe el buscador del escaparate.
    path('api/v2/search/',         include(('addons.website.controllers.search_urls', 'search'),
                                           namespace='search_v2')),
    # Checkout express de la misma familia (``website_sale/controllers/
    # payment.py``): confirma el carrito en un paso.
    path('api/v2/checkout/',       include(('addons.website_sale.controllers.checkout_urls', 'checkout'),
                                           namespace='checkout_v2')),
    # Cobro — superficie del comprador (``payment/controllers/portal.py``).
    path('api/v2/payments/',       include(('addons.payment.controllers.urls', 'payments'),
                                           namespace='payments_v2')),
    # Panel de inventario del operador (``stock/controllers/``).
    path('api/v2/admin/',          include(('addons.stock.controllers.admin_urls', 'admin_inventory'),
                                           namespace='admin_inventory_v2')),
    # Programa de referidos — superavit local declarado (ver
    # analisis-familia-loyalty:158-159). Vive en ``loyalty`` porque cada
    # codigo se respalda como Voucher tipo REFERRAL.
    path('api/v2/account/referral/', include(('addons.loyalty.controllers.urls', 'referral'),
                                           namespace='referral_v2')),
    # Wishlist — la familia que la hospeda (tarea #41; adaptacion de
    # ``odoo19c: website_sale_wishlist/controllers/main.py``).
    path('api/v2/wishlist/',       include(('addons.website_sale_wishlist.controllers.urls', 'wishlist'),
                                           namespace='wishlist_v2')),
    path('api/v2/admin/',          include(('addons.website_sale_wishlist.controllers.admin_urls', 'admin_wishlist'),
                                           namespace='admin_wishlist_v2')),
    # Reseñas — superficie de ``rating`` (tarea #43; reparto de
    # ``odoo19c: portal_rating``: el dato es de rating, el portal la expone).
    path('api/v2/products/',       include(('addons.rating.controllers.urls', 'reviews'),
                                           namespace='reviews_v2')),
    path('api/v2/admin/',          include(('addons.rating.controllers.admin_urls', 'admin_reviews'),
                                           namespace='admin_reviews_v2')),
    # Contacto — captura en ``crm`` (tarea #45; reparto de
    # ``odoo19c: website_crm``: la página es del sitio, la captura del CRM).
    path('api/v2/contact/',        include(('addons.crm.controllers.urls', 'contact'),
                                           namespace='contact_v2')),
    # Ajustes generales — familia ``base_setup`` (tarea #46). La referencia
    # declara el modelo en ``base`` pero SIRVE la superficie desde
    # ``base_setup`` (medido en 19c y 18c; 117/113 addons la extienden).
    path('api/v2/config/',         include(('addons.base_setup.controllers.urls', 'config'),
                                           namespace='config_v2')),
    # Páginas estáticas versionadas — el sitio es su dueño (tarea #46).
    path('api/v2/config/',         include(('addons.website.controllers.urls', 'public_pages'),
                                           namespace='public_pages_v2')),
    path('api/v2/admin/',          include(('addons.website.controllers.admin_urls', 'admin_pages'),
                                           namespace='admin_pages_v2')),
    path('api/v2/admin/',          include(('addons.crm.controllers.admin_urls', 'admin_contact'),
                                           namespace='admin_contact_v2')),

    # ─── Retirados (SOL-098 aplicada a las familias) ──────────────────────────
    # ``contact`` · ``referral`` · ``returns`` · ``reviews`` se retiraron del
    # árbol: eran superficie REST con 0 modelos, y su dominio ya vive en el
    # addon destino. Sus rutas vuelven con la familia que las hospeda —
    # ``contacts``, ``website_sale``, ``stock`` y ``rating`` respectivamente
    # (``wishlist`` ya volvió: ``website_sale_wishlist``, arriba).

    # ─── API v2 (F3: support) ──────────────────────────────
    # El recorrido del comprador sobre su venta lo sirve ``sale`` — es donde
    # la referencia lo pone (``sale/controllers/portal.py`` → ``/my/orders``).
    # El prefijo público sigue siendo ``/orders/``: el comprador habla de sus
    # pedidos, no de las ventas de la tienda.
    path('api/v2/orders/',                include(('addons.sale.controllers.urls', 'sale'),                   namespace='sale_v2')),
    # El backoffice es de ``sale_management`` — la referencia separa gestionar
    # de comprar, y el espejo las mezclaba en un solo addon.
    path('api/v2/admin/',                 include(('addons.sale_management.controllers.admin_urls', 'admin_sale'),
                                                  namespace='admin_sale_v2')),
    path('api/v2/support/',               include(('addons.helpdesk.controllers.urls', 'support'),             namespace='support_v2')),

    # ─── API v2 (F4: inventory admin + catalogue admin) ───────────────────────

    # ─── API v2 (F5: logistics/shipments, newsletter, contact, pages, backups,
    #             reports, auth §2.1) ────────────────────────────────────────
    path('api/v2/',            include(('addons.delivery.controllers.urls', 'logistics'), namespace='logistics_v2')),
    path('api/v2/newsletter/', include(('addons.website_mass_mailing.controllers.urls', 'website_mass_mailing'), namespace='newsletter_v2')),
    path('api/v2/admin/',      include(('addons.mass_mailing.controllers.admin_urls', 'admin_newsletter'),   namespace='admin_newsletter_v2')),
    path('api/v2/admin/',      include(('addons.auto_backup.controllers.admin_urls', 'admin_backups'),         namespace='admin_backups_v2')),
    # DEC-08/09: capacidades del usuario + menú admin dinámico (podado por capacidad)
    path('api/v2/authz/',      include(('addons.authz.controllers.urls', 'authz'),                         namespace='authz_v2')),
    # DEC-01 (~authz_totp): gestión del 2FA TOTP del usuario autenticado
    path('api/v2/authz/totp/', include(('addons.authz_totp.controllers.urls', 'authz_totp'),               namespace='authz_totp_v2')),
    # ~auth_ldap: CRUD de configuraciones LDAP por ResCompany (permissions.ldap)
    path('api/v2/authz/',      include(('addons.authz_ldap.controllers.urls', 'authz_ldap'),               namespace='authz_ldap_v2')),
    # ~auth_oauth: login federado OAuth2 + proveedores (permissions.oauth)
    path('api/v2/authz/',      include(('addons.authz_oauth.controllers.urls', 'authz_oauth'),             namespace='authz_oauth_v2')),
    # ~auth_totp_mail: código 2FA por correo + invitación
    path('api/v2/authz/totp-mail/', include(('addons.authz_totp_mail.controllers.urls', 'authz_totp_mail'), namespace='authz_totp_mail_v2')),
    # ~auth_passkey: login WebAuthn + gestión de passkeys (account.security)
    path('api/v2/authz/',      include(('addons.authz_passkey.controllers.urls', 'authz_passkey'),         namespace='authz_passkey_v2')),
    # ~auth_signup: alta/set-password/reset por token firmado (pre-auth)
    path('api/v2/authz/',      include(('addons.authz_signup.controllers.urls', 'authz_signup'),           namespace='authz_signup_v2')),
    # ~auth_timeout: confirmar identidad al vencer el candado por tiempo.
    # El prefijo es el que `authz_timeout/exceptions.py::CHECK_IDENTITY_URL`
    # publica en el cuerpo del 403 CHECK_IDENTITY_REQUIRED — si uno cambia,
    # cambia el otro.
    path('api/v2/authz/timeout/', include(('addons.authz_timeout.controllers.urls', 'authz_timeout'),      namespace='authz_timeout_v2')),
    # Consulta pública de CP → asentamientos (autocompletado de dirección).
    # FORMA PROPIA: la referencia no expone superficie de códigos postales
    # (base_address_extended y base_geolocalize sin controllers/). Ver el
    # docstring de base_address_extended/controllers/main.py.
    path('api/v2/geo/',        include(('addons.base_address_extended.controllers.urls', 'geo'), namespace='geo_v2')),
    # ~web: sesión del cliente — ≙ /web/session/{authenticate,destroy,logout}
    # de odoo19c: web/controllers/session.py (LGPL-3). Es la puerta que abre la
    # sesión de servidor que ADR-018 declara como autenticación por defecto.
    path('api/v2/web/',        include(('addons.web.controllers.urls', 'web'),                             namespace='web_v2')),
    # ~portal: cuenta propia — ≙ /my/account · /my/addresses · /my/security ·
    # /my/deactivate_account de odoo19c: portal (LGPL-3)
    path('api/v2/portal/',     include(('addons.portal.controllers.urls', 'portal'),                       namespace='portal_v2')),
    # G-PERM-01: catálogo de roles para el selector de /admin/permissions (UC-ADM-02)
    path('api/v2/admin/',      include(('addons.authz.controllers.admin_urls', 'admin_authz'),             namespace='admin_authz_v2')),
    # UC-PLT-12: consola L0 del operador Kaupamex — directorio de tenants (platform.provision)
    path('api/v2/platform/',   include(('addons.sale_subscription.controllers.urls', 'company'),                     namespace='company')),
    # `api/v2/admin/finance/` — prefijo compartido: ninguno de los addons
    # que cuelgan aquí es dueño exclusivo del módulo `finance` (lo dueña
    # `account`), así que un `include` por addon vive en este mismo bloque.
    #
    # UC-PAY-14 (H-API-408, tarea #55): registro de pago (abono/pago
    # completo) sobre una factura. Primer endpoint DRF del propio addon
    # `account`.
    path('api/v2/admin/finance/', include(('addons.account.controllers.urls', 'admin_finance_invoices'),
                                          namespace='admin_finance_invoices_v2')),
    # UC-FIN-09/10/11 (H-API-406, tareas #50/#51/#52): los tres wizards de la
    # familia `account` portados sin capa DRF.
    path('api/v2/admin/finance/', include(('addons.account_check_printing.controllers.urls', 'admin_finance_checks'),
                                          namespace='admin_finance_checks_v2')),
    path('api/v2/admin/finance/', include(('addons.account_debit_note.controllers.urls', 'admin_finance_debit_notes'),
                                          namespace='admin_finance_debit_notes_v2')),
    path('api/v2/admin/finance/', include(('addons.account_update_tax_tags.controllers.urls', 'admin_finance_tax_tags'),
                                          namespace='admin_finance_tax_tags_v2')),

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
    path('api/v2/admin/',   include(('addons.loyalty.controllers.admin_urls', 'admin_voucher'),                           namespace='admin_voucher_v2')),
    path('api/v2/admin/',   include(('addons.helpdesk.controllers.admin_urls', 'admin_support'),                     namespace='admin_support_v2')),
    path('api/v2/admin/',   include(('addons.website.controllers.static_content_urls', 'admin_static_content'),      namespace='admin_static_content_v2')),
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


