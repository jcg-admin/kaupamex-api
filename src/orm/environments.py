"""``Environment`` — fiel a ``odoo/orm/environments.py`` (Odoo 19).

En Odoo el ``Environment`` (``self.env``) es el contexto de ejecución que ata
tres cosas a cada recordset: el **cursor** de la transacción (``env.cr``), el
**usuario** actual (``env.uid`` / ``env.user`` / ``env.su`` para sudo) y el
**contexto** (``env.context``, dict de solo lectura). Además indexa los modelos
por nombre (``env['res.partner']``) y cachea registros dentro de la transacción.

Mapeo a Django — **cada pieza del Environment ya existe en Django**, dispersa en
distintos lugares en vez de un único objeto:

=====================  =========================================================
Odoo ``env.*``         Equivalente Django
=====================  =========================================================
``env.cr`` (cursor)    ``django.db.connection`` / ``connections[alias]``;
                       la transacción se maneja con ``transaction.atomic``
``env.uid`` / ``.user``  ``request.user`` (autenticación DRF/Django)
``env.su`` (sudo)      ``user.is_superuser`` / correr sin filtros de permiso
``env.context``        ``request`` + ``get_language()`` (i18n) + kwargs de vista
``env['model.name']``  ``apps.get_model(...)`` / import directo del modelo
cache por transacción  el ORM de Django gestiona su propio caché de queries
=====================  =========================================================

Por eso este archivo es un **stub delgado y documentado, no una
reimplementación**: recrear ``Environment`` sobre Django duplicaría el registro
de apps, el manejo de conexiones y la autenticación que Django ya provee. Un
addon portado que en Odoo escribía ``self.env.user`` se adapta a
``request.user``; ``self.env['res.partner']`` a ``apps.get_model('base',
'ResPartner')`` o al import directo del modelo. Cuando un flujo concreto necesite
azúcar de acceso (p. ej. un helper ``env(request)`` que exponga ``user`` +
``lang`` + ``company``), se añade aquí como conveniencia sobre las piezas
nativas, sin reintroducir el motor.
"""
from contextlib import contextmanager
from contextvars import ContextVar

from django.apps import apps
from django.db import connection, connections, models

# === Canal del DATO: la compañía activa del request ========================
# Análogo de ``env.companies``/``env.company`` (``odoo19c:
# odoo/orm/environments.py:246``; en 18c el símbolo vive en ``odoo/api.py`` —
# citar por símbolo, no por ruta). Es el canal del **dato**: qué compañía
# está activa. La **elevación** es el otro canal (``env.su``) y NO pasa por
# aquí (DEC-AISL-04) — el acceso cross-company del operador se hace explícito
# con el manager por defecto, nunca "limpiando" el contexto.
#
# ``ContextVar`` (no un global) para ser seguro bajo async/threads: cada
# request tiene su propio valor. Lo puebla ``CompanyContextMiddleware``
# (``addons.base.models.ir_http`` — allá vive el enlace request→entorno,
# como ``ir.http`` en la referencia).

_current_company: ContextVar = ContextVar('current_company', default=None)


def get_current_company():
    """PK de la compañía del request en curso, o ``None`` si no hay."""
    return _current_company.get()


def set_current_company(company_id):
    """Fija (o limpia con ``None``) la compañía del contexto actual."""
    _current_company.set(company_id)


@contextmanager
def company_scope(company_id):
    """Fija la compañía en el bloque y **restaura** el valor previo al salir."""
    token = _current_company.set(company_id)
    try:
        yield
    finally:
        _current_company.reset(token)


class CompanyScopedManager(models.Manager):
    """Aislamiento de fila por compañía — TRANSITORIO (muere en DEC-AISL-04 §4).

    En la referencia este filtrado es **dato** (``ir.rule`` con
    ``company_ids``), evaluado por el ORM; aquí es un manager codificado.
    ``for_current_company()`` filtra por la compañía del contexto,
    fail-closed: sin compañía en contexto → queryset vacío, nunca "todo".
    Requiere FK ``company`` (columna ``company_id``) en el modelo. El acceso
    cross-company del operador usa ``objects`` (explícito). Se retira al
    cablear ``ir_rule`` (tarea #31).
    """

    def for_current_company(self):
        company_id = get_current_company()
        if company_id is None:
            return self.get_queryset().none()
        return self.get_queryset().filter(company_id=company_id)


__all__ = [
    'apps', 'connection', 'connections',
    'get_current_company', 'set_current_company', 'company_scope',
    'CompanyScopedManager',
]
