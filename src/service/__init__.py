"""Capa de servicio de infraestructura (hermano de ``orm`` y ``apps``).

Fiel a ``odoo/service/`` de Odoo 19 (hermano de ``odoo/orm/``): aquí vive el
runtime de servidor y los servicios transversales, separados de la máquina ORM
(``orm/``, que sólo tiene el binding ORM↔base: ``routers.py``) y del dominio
(``apps/``). Layout completo espejando ``odoo/service/`` — dos clases de módulo:

**Con lógica real (adaptación fiel, no Django):**

- ``db.py`` (≙ ``odoo/service/db.py`` + bits de ``http.py``/``sql_db.py``) —
  administración de bases DB-per-company (SOL-091): create/drop/duplicate/rename/
  exist/list/dump, adaptado a MariaDB.
- ``retry.py`` (≙ ``odoo/service/model.py::retrying``) — reintento ante deadlock
  1213 con backoff+jitter (H-API-INFRA-01, DEC-KX-03).

**Stubs finos documentados (infra RPC/servidor que Django/DRF/WSGI ya proveen):**

- ``common.py`` (≙ ``odoo/service/common.py``) — RPC común (login/version) →
  auth DRF (JWT/sesión) + router de URLs.
- ``model.py`` (≙ ``odoo/service/model.py``) — dispatch ``execute_kw`` → vistas/
  serializers DRF; allowlist ``get_public_method`` → ``HasCapability``; el retry
  vive en ``retry.py``.
- ``security.py`` (≙ ``odoo/service/security.py``) — integridad de sesión →
  sesiones Django + JWT firmado; autorización → capacidades (DEC-11) + record
  rules (DEC-KX-02).
- ``server.py`` (≙ ``odoo/service/server.py``) — runtime WSGI/workers/cron →
  Apache+mod_wsgi (prod) / runserver (dev) + ``ir.cron`` + router multi-DB.
"""
