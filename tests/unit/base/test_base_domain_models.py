"""Contrato de los modelos de dominio + control portados a ``base`` (Odoo 18/19).

Completa el ``base`` fundacional con los modelos que faltaban del núcleo Odoo:

- ``ResLang``: locale único; formatos/separadores por defecto.
- ``ResCountryGroup``: M2M a ``ResCountry``.
- ``ResCurrencyRate``: tasa por (moneda, empresa, fecha); único por día.
- ``DecimalPrecision``: dígitos por uso; nombre único.
- ``ResBank``: institución con BIC + país/estado.
- ``IrSequence``: control de numeración (prefijo/padding/sufijo/incremento) —
  ``get_next`` fiel a Odoo ``_next``.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from addons.base.models import (
    DecimalPrecision,
    IrSequence,
    ResBank,
    ResCountry,
    ResCountryGroup,
    ResCurrency,
    ResCurrencyRate,
    ResLang,
)
from addons.platform.models import Company

pytestmark = pytest.mark.django_db


class TestResLang:
    def test_defaults(self):
        lang = ResLang.objects.create(name='Español (México)', code='es_MX', url_code='es_MX')
        assert lang.direction == 'ltr'
        assert lang.week_start == '7'
        assert lang.grouping == '[3,0]'
        assert lang.decimal_point == '.'

    def test_code_unique(self):
        ResLang.objects.create(name='English', code='en_US', url_code='en')
        with transaction.atomic(), pytest.raises(IntegrityError):
            ResLang.objects.create(name='English (UK)', code='en_US', url_code='en_gb')


class TestResCountryGroup:
    def test_m2m_countries(self):
        mx = ResCountry.objects.create(name='México', code='MX')
        us = ResCountry.objects.create(name='USA', code='US')
        grp = ResCountryGroup.objects.create(name='NAFTA', code='NAFTA')
        grp.country_ids.add(mx, us)
        assert grp.country_ids.count() == 2
        assert mx.country_groups.first() == grp


class TestResCurrencyRate:
    def test_rate_stored(self):
        usd = ResCurrency.objects.create(name='USD')
        r = ResCurrencyRate.objects.create(
            name=date(2026, 7, 18), rate=Decimal('17.5'), currency=usd)
        assert r.rate == Decimal('17.5')

    def test_unique_per_day(self):
        # La unicidad (moneda, empresa, fecha) sólo aplica con empresa fijada:
        # con company NULL, SQL NULL != NULL no dispara (fiel a Odoo, misma
        # semántica que su unique(name,currency_id,company_id)).
        usd = ResCurrency.objects.create(name='USD')
        acme = Company.objects.create(code='acme-fx', name='ACME FX')
        ResCurrencyRate.objects.create(
            name=date(2026, 7, 18), rate=Decimal('17'), currency=usd, company=acme)
        with transaction.atomic(), pytest.raises(IntegrityError):
            ResCurrencyRate.objects.create(
                name=date(2026, 7, 18), rate=Decimal('18'), currency=usd, company=acme)


class TestDecimalPrecision:
    def test_default_digits(self):
        dp = DecimalPrecision.objects.create(name='Product Price')
        assert dp.digits == 2

    def test_name_unique(self):
        DecimalPrecision.objects.create(name='Account', digits=2)
        with transaction.atomic(), pytest.raises(IntegrityError):
            DecimalPrecision.objects.create(name='Account', digits=4)


class TestResBank:
    def test_bank_with_country(self):
        mx = ResCountry.objects.create(name='México', code='MX')
        bank = ResBank.objects.create(name='BBVA', bic='BCMRMXMM', country=mx)
        assert bank.active is True
        assert bank.country == mx
        assert str(bank) == 'BBVA - BCMRMXMM'


class TestIrSequence:
    def test_get_next_padding_prefix_suffix(self):
        seq = IrSequence.objects.create(
            name='Factura', code='account.invoice', prefix='INV/', suffix='/26',
            padding=5, number_next=1, number_increment=1)
        assert seq.get_next() == 'INV/00001/26'
        seq.refresh_from_db()
        assert seq.number_next == 2
        assert seq.get_next() == 'INV/00002/26'

    def test_get_next_increment_step(self):
        seq = IrSequence.objects.create(
            name='Pick', prefix='WH/OUT/', padding=4, number_next=10, number_increment=5)
        assert seq.get_next() == 'WH/OUT/0010'
        seq.refresh_from_db()
        assert seq.number_next == 15

    def test_date_interpolation(self):
        seq = IrSequence.objects.create(
            name='Orden', prefix='SO/%(year)s/', padding=3, number_next=7)
        out = seq.get_next(for_date=date(2026, 7, 18))
        assert out == 'SO/2026/007'
