"""Billing run L0 — cobro company→Kaupamex (SOL-085 S4-b / #180, DEC-T6).

Lógica pura del ciclo de cobro de la plataforma: cuánto debe cada company por
sus módulos contratados y qué pasa si el cobro falla. El **cobro real** (crear
el pago en MercadoPago reusando la pasarela ya integrada en ``apps.payments``)
se inyecta como el callable ``charge`` — así esta lógica es testeable sin
egress y el adaptador MP es una pieza delgada de integración aparte.

Dos flujos de dinero distintos conviven (no confundir): comprador→company (la
tienda, ya en producción) vs. company→Kaupamex (este módulo, la renta de los
módulos). Ver :ref:`diseno-eje-tenant-restricciones-billing`, sección "Billing".
"""
from decimal import Decimal

from apps.platform.company.models import Company, CompanyModuleSubscription


def amount_due(company, at=None):
    """Suma el ``price`` de las suscripciones **activas y con tarifa** de la
    company (lo que se cobra en el ciclo). Excluye trial/suspended/cancelled y
    las activas sin precio (free / sin tarifa sembrada). Devuelve ``Decimal``.
    """
    total = Decimal('0.00')
    for sub in company.subscriptions.all():
        if sub.is_active(at) and sub.price is not None:
            total += sub.price
    return total


def suspend_company_billing(company):
    """Transiciona a ``suspended`` las suscripciones ``active`` de la company
    (impago). NO ``cancelled``: permite reactivar sin perder historial y saca a
    la company del ∩ L1 (DEC-T4) sin tocar el resolver.
    """
    for sub in company.subscriptions.filter(
        status=CompanyModuleSubscription.Status.ACTIVE,
    ):
        sub.status = CompanyModuleSubscription.Status.SUSPENDED
        sub.save(update_fields=['status', 'updated_at'])


def run_billing(charge, at=None, companies=None):
    """Corre el ciclo de cobro sobre ``companies`` (default: todas menos la
    system company).

    ``charge(company, amount) -> bool``: crea el cobro (MP) y devuelve si tuvo
    éxito. Éxito → ``charged``; fallo → ``suspend_company_billing`` +
    ``suspended``; nada que cobrar → ``skipped``.

    Devuelve ``{company_code: 'charged'|'suspended'|'skipped'}``.
    """
    if companies is None:
        companies = Company.objects.filter(is_system=False)
    results = {}
    for company in companies:
        amount = amount_due(company, at)
        if amount <= 0:
            results[company.code] = 'skipped'
            continue
        if charge(company, amount):
            results[company.code] = 'charged'
        else:
            suspend_company_billing(company)
            results[company.code] = 'suspended'
    return results
