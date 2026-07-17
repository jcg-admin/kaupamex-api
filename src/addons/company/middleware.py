"""Middleware de contexto de company (L3, SOL-085).

Puebla el ``current_company`` (ContextVar) por request desde la company del
usuario autenticado (``request.user.company``), de modo que
``CompanyScopedManager.for_current_company()`` filtre las filas de ese request.
Lo limpia al terminar (``finally``) para no filtrar contexto entre requests que
comparten hilo (WSGI).

Resolutor L1 = **user→company** (el usuario pertenece a una company). Es el
resolutor que funciona hoy: ``IdentityUser.company`` ya existe. El resolutor
**subdominio→company** (``dbfilter`` de Odoo, UC-PLT-06) es una capa adicional
de la iniciativa multidomain; cuando llegue, fijará el contexto ANTES por host y
este middleware lo respetará (el operador L0 cross-company queda con
``company=None`` → sin scope, acceso explícito por el manager por defecto).

Ubicar DESPUÉS de ``AuthenticationMiddleware`` (necesita ``request.user``).
"""
from addons.company.context import set_current_company


class CompanyContextMiddleware:
    """Fija ``current_company`` = ``request.user.company_id`` durante el request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        company_id = None
        if user is not None and getattr(user, 'is_authenticated', False):
            company_id = getattr(user, 'company_id', None)
        set_current_company(company_id)
        try:
            return self.get_response(request)
        finally:
            set_current_company(None)
