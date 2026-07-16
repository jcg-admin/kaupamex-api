"""Router multi-DB DB-per-company (SOL-091, Palanca B) — infraestructura ORM.

Hermano de ``apps.platform.company`` (dominio); aquí vive la máquina multi-DB,
siguiendo la estructura ``orm/`` de Odoo 19 (``odoo/orm/``).

Adaptación fiel (``analisis-adaptacion-odoo-multidb``):

- **F-ODOO-06:** la Registry de Odoo hace ``self._db = sql_db.db_connect(db_name)``
  y ``cursor(readonly)`` separa primaria/réplica
  (``odoo19x/orm/registry.py:244-249, 1165-1186``). En Django la conexión por
  base es ``connections[alias]`` y ese split lectura/escritura son
  ``db_for_read`` / ``db_for_write``. Este router es la forma Django nativa de
  ese binding; no se re-implementa ni el pool ni el registry-per-DB (F-ODOO-04:
  el schema por empresa es idéntico).

- **F-DJ-01 (tuning):** el ``ConnectionRouter`` de Django
  (``db/utils.py:220-243``) usa *truthiness* — ``if chosen_db: return chosen_db``;
  si ``db_for_read/write`` devuelven ``None`` (o todos los routers se abstienen)
  cae a ``DEFAULT_DB_ALIAS``. Django **no** expresa "fail-closed" con ``None``:
  ``None`` = "sin base específica" ⇒ ``default``. Para **N=1** eso es correcto
  (el dominio vive en ``default``). El fail-closed **duro** bajo N>1 (rechazar
  escritura de dominio sin empresa activa, para no filtrar a ``default``) se
  añade como guard explícito en el wiring (T-091-05), no aquí — este router se
  mantiene como decisión de ruteo pura.

Ver diseño: ``at-aislamiento-multi-db-per-company`` (D-091-1..5).
"""
from django.conf import settings
from django.db import DEFAULT_DB_ALIAS

from apps.platform.company.context import get_current_company

# Plano de control L0 (vive en 'default'): el registro de bases + apps de infra
# que NO se particionan por empresa. Todo lo demás (dominio) va a company_<N>_db.
_CONTROL_PLANE_APPS = frozenset(getattr(
    settings, 'MULTIDB_CONTROL_PLANE_APPS', ('sessions', 'contenttypes')))
_CONTROL_PLANE_MODELS = frozenset(m.lower() for m in getattr(
    settings, 'MULTIDB_CONTROL_PLANE_MODELS', ('orm.companydatabase',)))


def company_db_alias(company_id):
    """Alias Django de la base de una empresa, o ``None`` si no hay empresa activa.

    ``5`` -> ``'company_5_db'`` (equivalente al ``db_name`` que Odoo pasa a
    ``sql_db.db_connect``). ``None`` -> ``None`` (sin base resoluble).
    """
    if company_id is None:
        return None
    return 'company_%s_db' % company_id


def _is_control_plane(app_label, model_name):
    if app_label in _CONTROL_PLANE_APPS:
        return True
    return ('%s.%s' % (app_label, model_name or '')).lower() in _CONTROL_PLANE_MODELS


class CompanyDatabaseRouter:
    """Enruta cada modelo a ``default`` (control L0) o ``company_<N>_db`` (dominio)."""

    def _target(self, model):
        meta = model._meta
        if _is_control_plane(meta.app_label, meta.model_name):
            return DEFAULT_DB_ALIAS
        # Dominio: la base de la empresa activa (o None -> Django cae a default,
        # correcto para N=1; ver F-DJ-01).
        return company_db_alias(get_current_company())

    def db_for_read(self, model, **hints):
        # Hook de réplica futura (Odoo ``_db_readonly``); hoy = primaria.
        return self._target(model)

    def db_for_write(self, model, **hints):
        return self._target(model)

    def allow_relation(self, obj1, obj2, **hints):
        # Sólo relaciones dentro del mismo alias resuelto (sin joins cross-DB,
        # que Django no soporta). ``None`` = sin opinión -> Django compara
        # ``obj._state.db`` (db/utils.py:244-256).
        db1 = self._target(obj1)
        db2 = self._target(obj2)
        if db1 is None or db2 is None:
            return None
        return db1 == db2

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if _is_control_plane(app_label, model_name):
            # El plano de control (registro L0, sesiones) sólo existe en 'default'.
            return db == DEFAULT_DB_ALIAS
        # Dominio: migra a 'default' (degeneración N=1) y a cualquier company_<N>_db.
        return db == DEFAULT_DB_ALIAS or db.startswith('company_')
