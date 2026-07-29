"""RED→GREEN — ``SaleOrder`` gana FK ``company`` + scoping L3 (SOL-085 S3).

Rebanada del eje factura (H-API-08, sub-rebanada (b)): ``account.services``
factura una ``SaleOrder`` leyendo su empresa, pero ``SaleOrder`` no tenía FK
``company`` (PROVEN: 0 usos en ``sale/models/sale_order.py``). Este es el
primer modelo de dominio que adopta el motor de scoping L3 ya existente
(``CompanyScopedManager``, ``company/models.py:29``): FK ``company`` nullable
durante el rollout + par de managers ``objects`` (cross-company, L0 admin) /
``scoped`` (fail-closed por empresa activa, L3). Espeja el patrón de
``CompanySetting`` (``company/models.py:194-202``).
"""
import pytest

from addons.company.context import set_current_company
from addons.company.models import Company, CompanyScopedManager
from addons.sale.models import SaleOrder


@pytest.fixture
def company_a(db):
    return Company.objects.create(code='acme', name='ACME')


@pytest.fixture
def company_b(db):
    return Company.objects.create(code='globex', name='Globex')


@pytest.mark.django_db
class TestSaleOrderCompanyScoping:
    def test_saleorder_has_company_fk(self, company_a):
        order = SaleOrder.objects.create(company=company_a)
        order.refresh_from_db()
        assert order.company == company_a

    def test_company_is_nullable_during_rollout(self, db):
        # Rollout L3: filas heredadas sin empresa aún son válidas (backfill
        # las asigna a la founder company vía migración).
        order = SaleOrder.objects.create()
        order.refresh_from_db()
        assert order.company is None

    def test_scoped_manager_is_company_scoped(self):
        assert isinstance(SaleOrder.scoped, CompanyScopedManager)

    def test_scoped_filters_by_current_company(self, company_a, company_b):
        a1 = SaleOrder.objects.create(company=company_a)
        SaleOrder.objects.create(company=company_b)
        set_current_company(company_a.pk)
        try:
            scoped = list(SaleOrder.scoped.for_current_company())
        finally:
            set_current_company(None)
        assert scoped == [a1]

    def test_scoped_fail_closed_without_company(self, company_a):
        SaleOrder.objects.create(company=company_a)
        set_current_company(None)
        assert list(SaleOrder.scoped.for_current_company()) == []

    def test_objects_crosses_companies(self, company_a, company_b):
        SaleOrder.objects.create(company=company_a)
        SaleOrder.objects.create(company=company_b)
        # objects = manager L0 admin (cross-company); ve ambas.
        assert SaleOrder.objects.count() == 2
