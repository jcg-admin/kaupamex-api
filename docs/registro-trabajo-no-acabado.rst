==================================
Registro de trabajo no acabado
==================================

Bitácora canónica de los pendientes (P-NN) detectados durante la
revisión sprint-a-sprint. Las entradas aquí listadas se actualizan al
cerrar cada pendiente con el SHA del commit o conjunto de commits que
materializan la cobertura completa (modelos + migraciones + vistas +
URLs + tests integración verdes).

Convención de identificadores y mensajes de commit: DEC-DOC-005
(identificadores en inglés), DEC-DOC-006 (códigos de negocio en
español), DEC-DOC-007 (soft delete obligatorio salvo tablas
append-only), DEC-DOC-008 (errores ruidosos).

----

P-13 — Logística (UC-LOG-01..09) + UC-CFG-04 contenido estático
================================================================

**Estado:** CLOSED

**Alcance entregado:**

* ``GET /api/v1/logistics/`` panel con grupos A (órdenes pagadas sin
  ``ShipmentGuide``) y B (guías activas con ``last_event`` anotado),
  acepta ``?courier_id=`` para filtrar.
* ``POST /api/v1/logistics/guides/<id>/confirm-delivery/`` —
  idempotente (devuelve ``already_delivered`` en repetición),
  bloquea guías canceladas con ``GUIA_CANCELADA``.
* ``GET /api/v1/logistics/couriers/`` lista de paqueterías activas.
* ``POST /api/v1/logistics/guides/`` crea guía (valida tracking
  duplicado y guía duplicada por orden).
* ``PATCH /api/v1/logistics/guides/<id>/`` actualiza estado y emite
  ``ShipmentEvent`` append-only (DEC-DOC-007 exception).
* ``GET /api/v1/admin/static-content/`` y
  ``GET|PATCH /api/v1/admin/static-content/<slug>/`` con historial
  via ``StaticContentVersion``.

**Commits (cronológico):**

* ``b7628c8`` — feat(logistics): add Courier, ShipmentGuide and
  ShipmentEvent models.
* ``65f14fd`` — feat(logistics): wire panel, guides CRUD and
  confirm-delivery endpoints.
* ``e9086e3`` — test(logistics): cover UC-LOG-01..09 endpoints with
  14 integration tests.
* ``64b8482`` — feat(static-content): add StaticContent with
  versioned admin endpoints.
* ``7d8fa26`` — feat(urls): mount logistics, reviews, search and
  catalogue browse routes (también monta static-content).

----

P-14 — Reseñas de productos (UC-REV-01..03)
============================================

**Estado:** CLOSED

**Alcance entregado:**

* ``GET /api/v1/products/<product_id>/reviews/`` solo expone
  ``APPROVED`` y emite ``average_rating``, ``total_reviews`` y
  ``rating_breakdown``.
* ``POST /api/v1/products/<product_id>/reviews/`` 201 PENDING_MODERATION;
  403 ``PRODUCTO_NO_COMPRADO`` (verificación dueño orden + item);
  409/400 ``RESENA_DUPLICADA`` (unique(user, product)).
* ``GET /api/v1/admin/reviews/?status=PENDING_MODERATION`` cola FIFO.
* ``POST /api/v1/admin/reviews/<id>/approve/`` idempotente
  (``already_approved`` en repetición; bloquea si está rechazada).
* ``POST /api/v1/admin/reviews/<id>/reject/`` con enum
  ``CONTENIDO_INAPROPIADO|SPAM|IDIOMA_NO_SOPORTADO|NO_RELACIONADA``.
* ``ReviewModerationLog`` append-only — satisface RNF-AUDIT-001.

**Commits (cronológico):**

* ``ed75824`` — feat(reviews): add Review and ReviewModerationLog
  models.
* ``42a5123`` — feat(reviews): expose public listing, submission
  and admin moderation.
* ``a3a2845`` — test(reviews): cover UC-REV-01..03 with 11
  integration tests.
* ``7d8fa26`` — feat(urls): mount logistics, reviews, search and
  catalogue browse routes.

----

P-17 — Catálogo browse + búsqueda + price-sync
================================================

**Estado:** CLOSED

**Alcance entregado:**

* ``GET /api/v1/products/<slug>/related/`` (UC-CAT-07) — misma
  categoría, excluye self, orden por featured + reciente, máx 8.
* ``GET /api/v1/categories/`` (UC-CAT-08) — alias público del árbol
  cacheado.
* ``GET /api/v1/catalogue/`` ya existía — UC-CAT-04/05 con resolución
  de subárbol de categorías.
* ``GET /api/v1/catalogue/search/`` reescrito sobre el legacy view:
  retorna ``normalized_query``, mantiene ``active_filters`` /
  ``highlighted_name`` / ``is_featured`` y persiste analíticas en
  ``apps.search_history.SearchEntry`` adicionalmente al historial
  legacy en ``catalogue.SearchHistory``.
* ``GET /api/v1/search/history/`` (UC-SRCH-03) — 20 más recientes
  del usuario.
* ``DELETE /api/v1/search/history/`` (Alt-B) limpia todo.
* ``DELETE /api/v1/search/history/<id>/`` (Alt-A) entrada puntual,
  404 ``ENTRADA_NO_ENCONTRADA`` para entradas ajenas (RNF-SEC-003).
* ``POST /api/v1/admin/price-sync/preview-csv/`` (multipart).
* ``POST /api/v1/admin/price-sync/apply-csv/`` (token sesión).
* ``POST /api/v1/admin/price-sync/preview-percentage/``.
* ``POST /api/v1/admin/price-sync/apply-percentage/``.
* ``GET /api/v1/admin/price-sync/template.csv`` (UC-CAT-12 Alt-C).

**Commits (cronológico):**

* ``0e4a883`` — feat(search-history): add append-only SearchEntry
  with owner endpoints.
* ``978f339`` — feat(catalogue): expose browse, related and
  price-sync at UI URLs.
* ``7d8fa26`` — feat(urls): mount logistics, reviews, search and
  catalogue browse routes (incluye 22 tests de integración para
  search_history, static_content y catalogue browse).

----

Resumen pytest
==============

Línea base previa al cierre: **945 passed**.
Línea base final tras P-13 + P-14 + P-17: **992 passed, 0 failed,
0 errors** (``pytest -p no:randomly``).
Delta: **+47 tests** (14 logística, 11 reseñas, 5 search history,
6 static content, 11 catálogo browse + price-sync).
