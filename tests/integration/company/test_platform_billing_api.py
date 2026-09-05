"""Tests — L0 recurring billing API (UC-PLT-18 §7C, #180).

Los endpoints exponen el motor de facturación recurrente:

- ``GET  /api/v2/platform/billing/runs/``           — lista de corridas (lectura).
- ``POST /api/v2/platform/billing/runs/``           — dispara una corrida (emite
  facturas); gateado con ``platform.billing`` → 202.
- ``GET  /api/v2/platform/companies/{id}/invoices/`` — facturas de una company.
- ``POST /api/v2/platform/invoices/{id}/retry/``    — reintenta una factura
  ``failed``; gateado con ``platform.billing``.

Autorización data-driven (``HasCapability``, NO ``is_staff``): lectura
``platform.view``, cobro/disparo ``platform.billing``. El usuario de prueba NO es
superadmin, así que el candado se evalúa de verdad.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model

import pytest

from addons.authz.models import Capability, Module, Role, RoleAssignment
from addons.sale_subscription import services
from addons.sale_subscription.models import (
    CompanyModuleSubscription,
    SubscriptionBillingRun,
    SubscriptionInvoice,
)
from addons.base.models import ResCompany

pytestmark = pytest.mark.integration

RUNS_URL = '/api/v2/platform/billing/runs/'


def _invoices_url(company_id):
    return f'/api/v2/platform/companies/{company_id}/invoices/'


def _retry_url(invoice_id):
    return f'/api/v2/platform/invoices/{invoice_id}/retry/'


def _user_with_caps(email, codes):
    """Usuario NO-superadmin con exactamente ``codes`` vía un rol dedicado."""
    caps = []
    for code in codes:
        domain = code.split('.', 1)[0]
        module, _ = Module.objects.get_or_create(
            code=domain, defaults={'name': domain},
        )
        cap, _ = Capability.objects.get_or_create(
            code=code, defaults={'module': module, 'name': code},
        )
        caps.append(cap)
    role, _ = Role.objects.get_or_create(
        code=f'role_{"_".join(c.replace(".", "_") for c in codes)}',
        defaults={'name': 'Test billing role'},
    )
    role.capabilities.set(caps)
    u = get_user_model().objects.create_user(login=email, password='TestPass123!')
    RoleAssignment.objects.create(user=u, role=role)
    return u


def _active_priced_sub(company, code, price):
    m = Module.objects.create(code=code, name=code)
    sub = CompanyModuleSubscription(
        company=company, module=m,
        status=CompanyModuleSubscription.Status.ACTIVE,
        billing_cycle='monthly', price=Decimal(price),
    )
    sub.save()
    return sub


class TestBillingRunsEndpoint:
    def test_list_runs_requires_platform_view(self, api_client, db):
        SubscriptionBillingRun.objects.create(period='2026-08')
        # Sin capacidad → 403 (fail-closed).
        nobody = _user_with_caps('nobody@kaupamex.mx', ['account.overview'])
        api_client.force_login(nobody)
        assert api_client.get(RUNS_URL).status_code == 403
        # Con platform.view → 200.
        operator = _user_with_caps('viewer@kaupamex.mx', ['platform.view'])
        api_client.force_login(operator)
        res = api_client.get(RUNS_URL)
        assert res.status_code == 200
        rows = res.data['results'] if isinstance(res.data, dict) else res.data
        assert any(r['period'] == '2026-08' for r in rows)

    def test_trigger_run_requires_platform_billing(self, api_client, db):
        c = ResCompany.objects.create(code='acme', name='Acme')
        _active_priced_sub(c, 'catalogue', '199.00')
        # platform.view NO alcanza para disparar el cobro.
        viewer = _user_with_caps('viewer2@kaupamex.mx', ['platform.view'])
        api_client.force_login(viewer)
        assert api_client.post(RUNS_URL, {'period': '2026-08'},
                               format='json').status_code == 403
        # platform.billing → 202 + emite la factura del periodo.
        biller = _user_with_caps('biller@kaupamex.mx', ['platform.billing'])
        api_client.force_login(biller)
        res = api_client.post(RUNS_URL, {'period': '2026-08'}, format='json')
        assert res.status_code == 202
        assert res.data['period'] == '2026-08'
        assert res.data['invoices_issued'] == 1
        inv = SubscriptionInvoice.objects.get(company=c, period='2026-08')
        assert inv.status == SubscriptionInvoice.Status.ISSUED


class TestCompanyInvoicesEndpoint:
    def test_list_company_invoices_scoped_and_gated(self, api_client, db):
        c = ResCompany.objects.create(code='acme', name='Acme')
        other = ResCompany.objects.create(code='globex', name='Globex')
        sub = _active_priced_sub(c, 'catalogue', '199.00')
        run = SubscriptionBillingRun.objects.create(period='2026-08')
        SubscriptionInvoice.objects.create(
            company=c, subscription=sub, run=run, period='2026-08',
            amount=sub.price,
        )
        # Sin capacidad → 403.
        nobody = _user_with_caps('n2@kaupamex.mx', ['account.overview'])
        api_client.force_login(nobody)
        assert api_client.get(_invoices_url(c.id)).status_code == 403
        # platform.view → 200, sólo las de esa company.
        operator = _user_with_caps('v3@kaupamex.mx', ['platform.view'])
        api_client.force_login(operator)
        res = api_client.get(_invoices_url(c.id))
        assert res.status_code == 200
        rows = res.data['results'] if isinstance(res.data, dict) else res.data
        assert len(rows) == 1
        assert rows[0]['period'] == '2026-08'
        # La company sin facturas devuelve lista vacía (scope correcto).
        empty = api_client.get(_invoices_url(other.id)).data
        empty_rows = empty['results'] if isinstance(empty, dict) else empty
        assert len(empty_rows) == 0


class TestRetryInvoiceEndpoint:
    def _failed_invoice(self, company):
        sub = _active_priced_sub(company, 'catalogue', '199.00')
        run = SubscriptionBillingRun.objects.create(period='2026-08')
        return SubscriptionInvoice.objects.create(
            company=company, subscription=sub, run=run, period='2026-08',
            amount=sub.price, status=SubscriptionInvoice.Status.FAILED,
        )

    def test_retry_requires_platform_billing(self, api_client, db):
        c = ResCompany.objects.create(code='acme', name='Acme')
        inv = self._failed_invoice(c)
        viewer = _user_with_caps('v4@kaupamex.mx', ['platform.view'])
        api_client.force_login(viewer)
        assert api_client.post(_retry_url(inv.id)).status_code == 403

    def test_retry_failed_invoice_charges_and_pays(self, api_client, db,
                                                   monkeypatch):
        c = ResCompany.objects.create(code='acme', name='Acme')
        inv = self._failed_invoice(c)
        monkeypatch.setattr(services, 'charge_invoice', lambda invoice: True)
        biller = _user_with_caps('b2@kaupamex.mx', ['platform.billing'])
        api_client.force_login(biller)
        res = api_client.post(_retry_url(inv.id))
        assert res.status_code == 200
        inv.refresh_from_db()
        assert inv.status == SubscriptionInvoice.Status.PAID
        assert inv.paid_at is not None

    def test_retry_non_failed_invoice_is_409(self, api_client, db):
        c = ResCompany.objects.create(code='acme', name='Acme')
        inv = self._failed_invoice(c)
        inv.status = SubscriptionInvoice.Status.PAID
        inv.save(update_fields=['status', 'updated_at'])
        biller = _user_with_caps('b3@kaupamex.mx', ['platform.billing'])
        api_client.force_login(biller)
        res = api_client.post(_retry_url(inv.id))
        assert res.status_code == 409
        assert res.data['codigo_error'] == 'INVOICE_NOT_RETRYABLE'

    def test_retry_missing_invoice_is_404(self, api_client, db):
        biller = _user_with_caps('b4@kaupamex.mx', ['platform.billing'])
        api_client.force_login(biller)
        res = api_client.post(_retry_url(999999))
        assert res.status_code == 404
        assert res.data['codigo_error'] == 'INVOICE_NOT_FOUND'
