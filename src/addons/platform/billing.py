"""Billing run L0 — cobro company→Kaupamex (SOL-085 S4-b / #180, DEC-KX-07).

Ciclo de cobro de la plataforma: cuánto debe cada company por sus módulos
contratados, qué factura se emite por período y qué pasa si el cobro falla. El
**cobro real** (crear el pago en MercadoPago reusando la pasarela ya integrada
en ``apps.payments``) se inyecta como el callable ``charge`` — así esta lógica
es testeable sin egress y el adaptador MP es una pieza delgada de integración
aparte.

Dos flujos de dinero distintos conviven (no confundir): comprador→company (la
tienda, ya en producción) vs. company→Kaupamex (este módulo, la renta de los
módulos). Ver :ref:`diseno-motor-facturacion-recurrente-l0`.

**Persistencia (H-API-02, slice 2):** ``run_billing`` ya no devuelve sólo un
dict efímero — **crea** una ``SubscriptionBillingRun`` (resumen auditable) y una
``SubscriptionInvoice`` por suscripción y período (documento de cobro, idempotente
por ``(subscription, period)``, con el precio **congelado**). El dict de retorno
se conserva para compatibilidad.
"""
from decimal import Decimal

from django.utils import timezone

from addons.platform.models import (
    Company,
    CompanyModuleSubscription,
    SubscriptionBillingRun,
    SubscriptionInvoice,
)


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


def _billable_subscriptions(company, at):
    """Suscripciones activas y con tarifa de la company (las que se facturan)."""
    return [
        sub for sub in company.subscriptions.all()
        if sub.is_active(at) and sub.price is not None
    ]


def run_billing(charge, at=None, companies=None, period=None,
                triggered_by=SubscriptionBillingRun.TriggeredBy.TIME):
    """Corre el ciclo de cobro sobre ``companies`` (default: todas menos la
    system company) para ``period`` (default: el mes de ``at``).

    Persiste una ``SubscriptionBillingRun`` y, por cada suscripción facturable,
    una ``SubscriptionInvoice`` idempotente por período (el ``amount`` se congela
    del ``subscription.price``). El cobro se delega a
    ``charge(company, amount) -> bool``: éxito → factura ``paid``; fallo →
    factura ``failed`` + ``suspend_company_billing`` + estado ``suspended``. Una
    factura ya ``paid`` de un período no se re-cobra (EX-04).

    Devuelve, por compatibilidad, ``{company_code: 'charged'|'suspended'|'skipped'}``.
    """
    if at is None:
        at = timezone.now()
    if period is None:
        period = at.strftime('%Y-%m')
    if companies is None:
        companies = Company.objects.filter(is_system=False)

    run = SubscriptionBillingRun.objects.create(
        period=period, triggered_by=triggered_by,
    )
    results = {}
    for company in companies:
        subs = _billable_subscriptions(company, at)
        if not subs:
            results[company.code] = 'skipped'
            continue

        company_failed = False
        charged_any = False
        for sub in subs:
            invoice, _created = SubscriptionInvoice.objects.get_or_create(
                subscription=sub, period=period,
                defaults={
                    'company': company, 'run': run, 'amount': sub.price,
                },
            )
            if invoice.status == SubscriptionInvoice.Status.PAID:
                continue  # idempotente: ya cobrada este período
            invoice.status = SubscriptionInvoice.Status.ISSUED
            invoice.issued_at = at
            if charge(company, invoice.amount):
                invoice.status = SubscriptionInvoice.Status.PAID
                invoice.paid_at = at
                invoice.save()
                run.invoices_issued += 1
                run.amount_charged += invoice.amount
                charged_any = True
            else:
                invoice.status = SubscriptionInvoice.Status.FAILED
                invoice.failure_reason = 'Cobro rechazado por la pasarela'
                invoice.save()
                run.failures += 1
                company_failed = True

        if company_failed:
            suspend_company_billing(company)
            results[company.code] = 'suspended'
        elif charged_any:
            results[company.code] = 'charged'
        else:
            results[company.code] = 'skipped'  # todo el período ya estaba pagado

    run.finished_at = timezone.now()
    run.save()
    return results


def issue_billing_run(at=None, companies=None, period=None,
                      triggered_by=SubscriptionBillingRun.TriggeredBy.OPERATOR):
    """Emite (sin cobrar) las facturas del período: crea la corrida y una
    ``SubscriptionInvoice`` ``issued`` idempotente por suscripción facturable.

    El **cobro real** (mover dinero por la pasarela MP) es un paso posterior —
    ``charge_invoice`` / el scheduler con el adaptador MP (pieza de integración
    aparte, H-API-03). Este flujo es el que dispara el endpoint ``POST
    /billing/runs`` → 202 (encolada): deja las facturas listas para cobrar sin
    egress. Devuelve la ``SubscriptionBillingRun``.
    """
    if at is None:
        at = timezone.now()
    if period is None:
        period = at.strftime('%Y-%m')
    if companies is None:
        companies = Company.objects.filter(is_system=False)

    run = SubscriptionBillingRun.objects.create(
        period=period, triggered_by=triggered_by,
    )
    for company in companies:
        for sub in _billable_subscriptions(company, at):
            invoice, created = SubscriptionInvoice.objects.get_or_create(
                subscription=sub, period=period,
                defaults={
                    'company': company, 'run': run, 'amount': sub.price,
                    'status': SubscriptionInvoice.Status.ISSUED,
                    'issued_at': at,
                },
            )
            if created:
                run.invoices_issued += 1
    run.finished_at = timezone.now()
    run.save()
    return run


class BillingGatewayNotConfigured(Exception):
    """No hay pasarela de cobro cableada para el billing L0 (H-API-03).

    El cobro real company→Kaupamex reutiliza el eje ``payment`` del O2C
    (DEC-KX-07); el adaptador concreto (crear el pago en MP) es una pieza de
    integración aparte que aún no se cabló. Hasta entonces, ``charge_invoice``
    la levanta y el endpoint la traduce a 503.
    """


def charge_invoice(invoice):
    """Cobra una ``SubscriptionInvoice`` por la pasarela (seam de integración).

    **Deferido (H-API-03):** el adaptador MP (egress real) no está cableado; por
    defecto levanta ``BillingGatewayNotConfigured``. Los tests inyectan un doble
    (``monkeypatch``). Devuelve ``bool`` (aprobado/rechazado) cuando esté cableado.
    """
    raise BillingGatewayNotConfigured(
        'Adaptador de cobro MP no cableado para billing L0 (H-API-03).')


def retry_invoice(invoice, at=None):
    """Reintenta el cobro de una factura ``failed`` vía ``charge_invoice``.

    Éxito → ``paid`` (``paid_at``); rechazo → sigue ``failed`` con motivo. El
    llamador (endpoint) ya validó que la factura estaba ``failed`` (si no, 409).
    Devuelve la factura actualizada.
    """
    if at is None:
        at = timezone.now()
    invoice.issued_at = invoice.issued_at or at
    if charge_invoice(invoice):
        invoice.status = SubscriptionInvoice.Status.PAID
        invoice.paid_at = at
        invoice.failure_reason = ''
    else:
        invoice.status = SubscriptionInvoice.Status.FAILED
        invoice.failure_reason = 'Cobro rechazado por la pasarela'
    invoice.save()
    return invoice
