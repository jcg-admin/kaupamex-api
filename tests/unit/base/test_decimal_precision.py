"""Gate de ``decimal.precision`` = ``odoo/addons/base/models/decimal_precision.py``.

Escrito antes que la implementación (TDD). Cubre las cuatro piezas que el gate
de porte reportaba ausentes —``create``, ``write``, ``unlink`` y
``_onchange_digits_warning``— más el caché de ``precision_get``, que la fuente
declara con ``@ormcache('application', cache='stable')`` y aquí no existía.
"""
import pytest
from django.db import IntegrityError, transaction

from addons.base.models.decimal_precision import DecimalPrecision
from orm import registry


@pytest.mark.django_db
class TestPrecisionGet:
    """``precision_get`` — dígitos por uso, memorizados."""

    def setup_method(self):
        registry.clear_all_caches()

    def test_an_unseeded_usage_falls_back_to_two(self):
        assert DecimalPrecision.precision_get('Uso Inexistente') == 2

    def test_it_reads_the_declared_digits(self):
        DecimalPrecision.create([{'name': 'Product Price', 'digits': 4}])
        assert DecimalPrecision.precision_get('Product Price') == 4

    def test_the_second_read_does_not_touch_the_database(self, django_assert_num_queries):
        DecimalPrecision.create([{'name': 'Product Price', 'digits': 4}])
        DecimalPrecision.precision_get('Product Price')
        with django_assert_num_queries(0):
            assert DecimalPrecision.precision_get('Product Price') == 4


@pytest.mark.django_db
class TestCacheInvalidation:
    """Las tres mutaciones vacían la caché ``stable``, como la fuente."""

    def setup_method(self):
        registry.clear_all_caches()

    def test_create_invalidates_what_precision_get_had_cached(self):
        assert DecimalPrecision.precision_get('Account') == 2
        DecimalPrecision.create([{'name': 'Account', 'digits': 6}])
        assert DecimalPrecision.precision_get('Account') == 6

    def test_write_invalidates_it(self):
        (registro,) = DecimalPrecision.create([{'name': 'Account', 'digits': 6}])
        assert DecimalPrecision.precision_get('Account') == 6
        registro.write({'digits': 3})
        assert DecimalPrecision.precision_get('Account') == 3

    def test_unlink_invalidates_it(self):
        (registro,) = DecimalPrecision.create([{'name': 'Account', 'digits': 6}])
        assert DecimalPrecision.precision_get('Account') == 6
        registro.unlink()
        assert DecimalPrecision.precision_get('Account') == 2

    def test_a_plain_save_invalidates_it_too(self):
        (registro,) = DecimalPrecision.create([{'name': 'Account', 'digits': 6}])
        assert DecimalPrecision.precision_get('Account') == 6
        registro.digits = 5
        registro.save()
        assert DecimalPrecision.precision_get('Account') == 5


@pytest.mark.django_db
class TestCreate:
    """``create`` — la firma multi de la fuente (``@api.model_create_multi``)."""

    def test_it_takes_a_list_and_returns_the_records(self):
        creados = DecimalPrecision.create([
            {'name': 'Product Price', 'digits': 4},
            {'name': 'Product Unit', 'digits': 3},
        ])
        assert [r.name for r in creados] == ['Product Price', 'Product Unit']
        assert DecimalPrecision.objects.count() == 2

    def test_a_single_dict_also_works(self):
        creados = DecimalPrecision.create({'name': 'Account', 'digits': 6})
        assert len(creados) == 1


@pytest.mark.django_db
class TestOnchangeDigitsWarning:
    """``_onchange_digits_warning`` — el aviso al reducir la precisión."""

    def test_reducing_the_precision_warns(self):
        (registro,) = DecimalPrecision.create([{'name': 'Account', 'digits': 6}])
        registro.digits = 2
        aviso = registro._onchange_digits_warning()
        assert aviso is not None
        assert 'Account' in aviso['warning']['title']
        assert 'WON' in aviso['warning']['message'] or 'no se actualiz' in aviso['warning']['message']

    def test_raising_the_precision_does_not_warn(self):
        (registro,) = DecimalPrecision.create([{'name': 'Account', 'digits': 2}])
        registro.digits = 6
        assert registro._onchange_digits_warning() is None

    def test_leaving_it_unchanged_does_not_warn(self):
        (registro,) = DecimalPrecision.create([{'name': 'Account', 'digits': 2}])
        assert registro._onchange_digits_warning() is None


@pytest.mark.django_db
class TestHeader:
    """La cabecera del modelo, contra la de la fuente."""

    def test_it_declares_the_two_class_attributes_of_the_source(self):
        assert DecimalPrecision._name == 'decimal.precision'
        assert DecimalPrecision._description == 'Decimal Precision'

    def test_the_named_constraint_of_the_source_survives(self):
        nombres = {c.name for c in DecimalPrecision._meta.constraints}
        assert 'decimal_precision_name_uniq' in nombres

    def test_two_rows_cannot_share_a_usage(self):
        DecimalPrecision.create([{'name': 'Account', 'digits': 2}])
        with pytest.raises(IntegrityError), transaction.atomic():
            DecimalPrecision.objects.create(name='Account', digits=3)
