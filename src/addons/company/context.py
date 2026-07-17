"""Contexto de company del request (L3 core, SOL-085).

En MariaDB 11.8 no hay RLS tipo Postgres: el aislamiento de fila L3 se hace en
la capa de aplicación. Un ``ContextVar`` guarda la company L1 del request en
curso; ``CompanyScopedManager.for_current_company()`` (en ``models``) filtra por
ella, **fail-closed** (sin company → queryset vacío).

Es un ``ContextVar`` (no un global) para ser seguro bajo async/threads: cada
request tiene su propio valor. El middleware subdominio→company (UC-PLT-06) lo
fijará por request; hasta entonces se fija explícito (tests / servicios).
"""
from contextlib import contextmanager
from contextvars import ContextVar

_current_company: ContextVar = ContextVar('current_company', default=None)


def get_current_company():
    """PK de la ``Company`` del request en curso, o ``None`` si no hay."""
    return _current_company.get()


def set_current_company(company_id):
    """Fija (o limpia con ``None``) la company del contexto actual."""
    _current_company.set(company_id)


@contextmanager
def company_scope(company_id):
    """Fija la company en el bloque y **restaura** el valor previo al salir."""
    token = _current_company.set(company_id)
    try:
        yield
    finally:
        _current_company.reset(token)
