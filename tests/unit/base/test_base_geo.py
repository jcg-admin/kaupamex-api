"""Contrato de ``ResCurrency`` / ``ResCountry`` / ``ResCountryState`` — portación
fiel del núcleo geográfico/monetario de Odoo ``base``.

Cada test verifica un comportamiento del original Odoo (``res_currency.py`` +
``res_country.py``, v18/v19 idénticos, cross-referenciados en SOL-096):

- ``name`` ISO 4217 único (res.currency.name, size 3, required).
- ``decimal_places`` computado de ``rounding`` = ``ceil(log10(1/rounding))``
  (``_compute_decimal_places`` o18:163-168 / o19:163-168): 0.01→2, 0.001→3,
  0.05→2, 1→0.
- ``ResCountry.code`` ISO alpha-2 único; ``currency`` FK con SET_NULL.
- ``ResCountryState`` único (country, code) (``_sql_constraints`` name_code_uniq).
"""
import math
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from addons.base.models import ResCountry, ResCountryState, ResCurrency

pytestmark = pytest.mark.django_db


class TestResCurrency:
    def test_name_iso4217_unique(self):
        # get_or_create: MXN puede pre-existir (semilla de compañías de tests
        # transaction=True comprometidos en la DB reutilizada).
        ResCurrency.objects.get_or_create(name='MXN', defaults={'symbol': '$'})
        with transaction.atomic(), pytest.raises(IntegrityError):
            ResCurrency.objects.create(name='MXN', symbol='$')

    @pytest.mark.parametrize('rounding,expected', [
        (Decimal('0.01'), 2),
        (Decimal('0.001'), 3),
        (Decimal('0.05'), 2),
        (Decimal('1'), 0),
        (Decimal('0.1'), 1),
    ])
    def test_decimal_places_computed_from_rounding(self, rounding, expected):
        # Fiel a Odoo _compute_decimal_places: ceil(log10(1/rounding)) si
        # 0<rounding<=1, si no 0.
        cur = ResCurrency.objects.create(
            name='T' + str(int(rounding * 1000)).zfill(2)[:2], symbol='$',
            rounding=rounding,
        )
        assert cur.decimal_places == expected

    def test_decimal_places_zero_when_rounding_gt_one(self):
        cur = ResCurrency.objects.create(
            name='BIG', symbol='$', rounding=Decimal('5'),
        )
        assert cur.decimal_places == 0

    def test_position_default_after(self):
        cur = ResCurrency.objects.create(name='USD', symbol='$')
        assert cur.position == ResCurrency.POSITION_AFTER

    def test_str_returns_iso_code(self):
        cur = ResCurrency.objects.create(name='EUR', symbol='€')
        assert str(cur) == 'EUR'


class TestResCountry:
    def test_code_alpha2_unique(self):
        ResCountry.objects.get_or_create(code='MX', defaults={'name': 'México'})[0]
        with transaction.atomic(), pytest.raises(IntegrityError):
            ResCountry.objects.create(name='Otro', code='MX')

    def test_currency_fk_set_null_on_delete(self):
        # XTS (código ISO de prueba): MXN puede estar referenciada con PROTECT
        # por compañías comprometidas en la DB reutilizada.
        xts = ResCurrency.objects.create(name='XTS', symbol='X')
        # El catálogo de `base/0017` ya trae MX: se le reapunta la moneda en vez
        # de crear un segundo país, que ahora choca con `res_country_code_key`.
        mx = ResCountry.objects.get_or_create(
            code='MX', defaults={'name': 'México'})[0]
        mx.currency = xts
        mx.save(update_fields=['currency'])
        xts.delete()
        mx.refresh_from_db()
        assert mx.currency is None

    def test_state_ids_reverse_relation(self):
        mx = ResCountry.objects.get_or_create(code='MX', defaults={'name': 'México'})[0]
        ResCountryState.objects.create(country=mx, name='Jalisco', code='JAL')
        ResCountryState.objects.create(country=mx, name='Nuevo León', code='NLE')
        assert mx.state_ids.count() == 2


class TestResCountryState:
    def test_unique_country_code(self):
        mx = ResCountry.objects.get_or_create(code='MX', defaults={'name': 'México'})[0]
        ResCountryState.objects.create(country=mx, name='Jalisco', code='JAL')
        with transaction.atomic(), pytest.raises(IntegrityError):
            ResCountryState.objects.create(country=mx, name='Otro', code='JAL')

    def test_same_code_different_country_allowed(self):
        mx = ResCountry.objects.get_or_create(code='MX', defaults={'name': 'México'})[0]
        us = ResCountry.objects.get_or_create(code='US', defaults={'name': 'USA'})[0]
        s1 = ResCountryState.objects.create(country=mx, name='Jalisco', code='JA')
        s2 = ResCountryState.objects.create(country=us, name='Georgia', code='JA')
        assert s1.pk != s2.pk

    def test_cascade_delete_with_country(self):
        mx = ResCountry.objects.get_or_create(code='MX', defaults={'name': 'México'})[0]
        ResCountryState.objects.create(country=mx, name='Jalisco', code='JAL')
        mx.delete()
        assert ResCountryState.objects.count() == 0
