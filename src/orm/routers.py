"""Router multi-DB DB-per-company (SOL-091, Palanca B) — infraestructura ORM.

Paquete ``orm`` top-level (hermano de ``apps``), fiel a ``odoo/orm/`` de Odoo 19
(hermano de ``addons``): aquí vive la máquina multi-DB, separada del dominio
(``apps.*``).

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
import re

from django.conf import settings
from django.db import DEFAULT_DB_ALIAS

from orm.environments import get_current_company


class CompanyContextRequired(Exception):
    """Fail-closed duro (T-091-05): dominio sin empresa activa bajo N>1.

    Bajo multi-DB (hay bases ``company_<N>_db`` configuradas), una operación de
    dominio sin empresa en contexto **no** puede caer a ``default`` (filtraría
    los datos de una empresa al plano de control). El wiring convierte ese
    ``None`` del router en este rechazo explícito. Bajo N=1 (sin bases company)
    el guard está dormido y se preserva la caída a ``default``.
    """


# Forma canónica del alias de base de empresa (== ``company_db_alias``).
_COMPANY_ALIAS_RE = re.compile(r'^company_\d+_db$')

# Plano de control L0 (vive en 'default'): apps de infra que NO se particionan
# por empresa. Todo lo demás (dominio) va a company_<N>_db. La lista de bases
# de empresa NO es un modelo (Odoo la lee de pg_database, no de una tabla
# aplicativa); en Django la leemos de information_schema (ver
# ``service.db.list_company_db_names``), así que ``orm`` no registra ninguna
# entidad y no es INSTALLED_APP.
_CONTROL_PLANE_APPS = frozenset(getattr(
    settings, 'MULTIDB_CONTROL_PLANE_APPS', ('sessions', 'contenttypes')))
_CONTROL_PLANE_MODELS = frozenset(m.lower() for m in getattr(
    settings, 'MULTIDB_CONTROL_PLANE_MODELS', ()))


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


def _has_company_databases():
    """¿Hay bases ``company_<N>_db`` en ``settings.DATABASES``? (N>1).

    Activa el fail-closed automáticamente: en cuanto el loader (T-091-05) puebla
    aliases ``company_*``, el router deja de tolerar dominio-sin-empresa. En N=1
    (sólo ``default``) devuelve ``False`` y el guard queda dormido.
    """
    return any(_COMPANY_ALIAS_RE.match(alias) for alias in settings.DATABASES)


class CompanyDatabaseRouter:
    """Enruta cada modelo a ``default`` (control L0) o ``company_<N>_db`` (dominio)."""

    def _target(self, model):
        meta = model._meta
        if _is_control_plane(meta.app_label, meta.model_name):
            return DEFAULT_DB_ALIAS
        company_id = get_current_company()
        if company_id is None:
            # Sin empresa activa -> None (N=1 cae a default; N>1 fail-closed en
            # ``_route``).
            return None
        alias = company_db_alias(company_id)
        # Degeneración N=1 (H-API-091-06): si la base de la empresa aún NO está
        # provisionada/registrada en ``settings.DATABASES``, el dominio vive en
        # ``default`` y el **row-scoping SOL-085** (filtro por columna
        # ``company_id``) aísla intra-base. El routing DB-per-company sólo activa
        # cuando la base existe (N>1). Sin este guard, una query bajo
        # ``company_scope(X)`` en N=1 iría a un alias inexistente y rompería
        # SOL-085 (regresión observada al cablear ``DATABASE_ROUTERS``).
        if alias in settings.DATABASES:
            return alias
        return None

    def _route(self, model):
        """``_target`` + guard fail-closed duro para dominio-sin-empresa bajo N>1.

        ``_target`` devuelve ``None`` **sólo** para dominio sin empresa activa
        (control-plane devuelve ``default``; dominio-con-empresa devuelve su
        alias). Ese ``None`` cae a ``default``: correcto en N=1, fuga en N>1 →
        se rechaza.
        """
        target = self._target(model)
        if target is None and _has_company_databases():
            meta = model._meta
            raise CompanyContextRequired(
                'operacion de dominio %s.%s sin empresa activa bajo multi-DB '
                '(N>1); fijar company_scope antes de leer/escribir'
                % (meta.app_label, meta.model_name)
            )
        return target

    def db_for_read(self, model, **hints):
        # Hook de réplica futura (Odoo ``_db_readonly``); hoy = primaria.
        return self._route(model)

    def db_for_write(self, model, **hints):
        return self._route(model)

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
