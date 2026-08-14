"""Tests — vigencia de la cotización (tarea #256).

Este archivo probaba ``cancel_timeout_orders``/``ORDER_PAYMENT_TIMEOUT_MINUTES``
(UC-SYS-01), retirados con el addon ``orders`` (SOL-098, ``api@77bd1f0``) sin
redomiciliar — 0 hits en ``src/``. El ``pytest.skip`` de módulo documentaba
esa ausencia como trabajo abierto; se retira aquí, no porque el mecanismo de
timeout se haya redomiciliado (sigue sin existir), sino porque la tarea #256
reutiliza este archivo para el mecanismo NUEVO que sí aterrizó en el mismo
pase: ``SaleOrder.is_expired`` (Odoo ``sale/models/sale_order.py:305,
758-764``) sobre ``validity_date`` (``:135-139,366-374``), calculada desde
``ResCompany.quotation_validity_days`` (``sale/models/res_company.py:22-27``).

``cancel_timeout_orders`` sigue sin redomiciliar — no es objeto de este
archivo desde este pase; su ausencia queda registrada en el mapa de rotura
de la demolición que el docstring anterior citaba.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from addons.base.models import ResCompany
from addons.sale.models import SaleOrder

pytestmark = pytest.mark.django_db


@pytest.fixture
def company():
    return ResCompany.objects.create(code='acme-256', name='ACME 256')


class TestSaleOrderIsExpired:

    def test_is_expired_true_con_validity_date_pasada(self, company):
        ayer = timezone.now().date() - timedelta(days=1)
        order = SaleOrder.objects.create(
            state=SaleOrder.STATE_DRAFT, company=company, validity_date=ayer,
        )
        assert order.is_expired is True

    def test_is_expired_false_con_validity_date_futura(self, company):
        manana = timezone.now().date() + timedelta(days=1)
        order = SaleOrder.objects.create(
            state=SaleOrder.STATE_DRAFT, company=company,
            validity_date=manana,
        )
        assert order.is_expired is False

    def test_is_expired_false_cuando_quotation_validity_days_es_cero(self):
        # quotation_validity_days=0 desactiva el vencimiento automático
        # (Odoo, res_company.py:22-27): la empresa no fija validity_date.
        company_sin_vencimiento = ResCompany.objects.create(
            code='acme-256-sin-vencimiento', name='ACME 256 sin vencimiento',
            quotation_validity_days=0,
        )
        order = SaleOrder.objects.create(
            state=SaleOrder.STATE_DRAFT, company=company_sin_vencimiento,
        )
        assert order.validity_date is None
        assert order.is_expired is False

    def test_validity_date_se_calcula_del_plazo_de_la_empresa(self, company):
        # Empresa por defecto: quotation_validity_days=30 (Odoo default).
        #
        # `localdate()`, no `now().date()`: `_compute_validity_date` usa la
        # fecha en `settings.TIME_ZONE` (America/Mexico_City) por divergencia
        # DECLARADA — "hoy donde opera la empresa", el análogo de
        # `fields.Date.context_today` de la referencia. Medir con UTC hacía que
        # el test fallara sólo en la ventana entre la medianoche UTC y la
        # local: 2026-08-14T00:20 UTC dio `2026-09-12` contra un esperado
        # `2026-09-13`. El código no estaba mal; el instrumento medía otro huso.
        hoy = timezone.localdate()
        order = SaleOrder.objects.create(
            state=SaleOrder.STATE_DRAFT, company=company,
        )
        assert order.validity_date == hoy + timedelta(
            days=company.quotation_validity_days)

    def test_is_expired_false_cuando_orden_confirmada(self, company):
        # Odoo _compute_is_expired: sólo draft/sent vencen — una orden ya
        # confirmada (sale) no se marca vencida aunque la fecha haya pasado.
        ayer = timezone.now().date() - timedelta(days=1)
        order = SaleOrder.objects.create(
            state=SaleOrder.STATE_SALE, company=company, validity_date=ayer,
            amount_total=Decimal('0.00'),
        )
        assert order.is_expired is False
