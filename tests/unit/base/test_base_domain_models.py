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
from addons.base.models import ResCompany

pytestmark = pytest.mark.django_db


class TestResLang:
    # Los dos usan un locale INVENTADO (``zz_ZZ``) y no uno real. Desde que
    # ``base/0026_seed_langs`` siembra los 93 idiomas de la referencia, el
    # catálogo ya NO nace vacío: crear ``es_MX`` o ``en_US`` choca con la
    # semilla y el fallo no habla de lo que el test quiere probar. ``zz_ZZ`` no
    # está en ``odoo19c: base/data/res.lang.csv`` (medido), así que el test mide
    # el modelo y no el catálogo.
    def test_defaults(self):
        lang = ResLang.objects.create(name='Idioma de prueba', code='zz_ZZ', url_code='zz')
        assert lang.direction == 'ltr'
        assert lang.week_start == '7'
        assert lang.grouping == '[3,0]'
        assert lang.decimal_point == '.'

    def test_code_unique(self):
        ResLang.objects.create(name='Idioma de prueba', code='zz_ZZ', url_code='zz')
        with transaction.atomic(), pytest.raises(IntegrityError):
            ResLang.objects.create(name='Otro', code='zz_ZZ', url_code='zz_alt')


class TestResCountryGroup:
    def test_m2m_countries(self):
        mx = ResCountry.objects.get_or_create(code='MX', defaults={'name': 'México'})[0]
        us = ResCountry.objects.get_or_create(code='US', defaults={'name': 'USA'})[0]
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
        acme = ResCompany.objects.create(code='acme-fx', name='ACME FX')
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
        mx = ResCountry.objects.get_or_create(code='MX', defaults={'name': 'México'})[0]
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
