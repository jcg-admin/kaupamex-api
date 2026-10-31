"""Many2one opcional sin columna: ausencia Django, valores y errores reales."""
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from addons.base.models import ResCompany, ResCountry, ResPartner
from addons.product.models.product_product import ProductProduct


pytestmark = [pytest.mark.integration, pytest.mark.django_db]


@pytest.fixture
def company():
    return ResCompany.objects.create(
        code='computed-country-empty', name='Computed country contract',
    )


def test_empty_computed_relation_does_not_look_up_a_false_primary_key(company):
    with CaptureQueriesContext(connection) as queries:
        assert company.country is None
        assert company.country is None
    assert len(queries) == 0


def test_computed_foreign_key_id_preserves_django_absence(company):
    with CaptureQueriesContext(connection) as queries:
        assert company.country_id is None
    assert len(queries) == 0


def test_related_code_of_an_empty_country_returns_the_field_empty_value(company):
    with CaptureQueriesContext(connection) as queries:
        assert company.country_code == ''
        assert company.country_code == ''
    assert len(queries) == 0


def test_explicit_constructor_none_is_readable_without_another_field_access():
    record = ResCompany(
        code='computed-country-constructor', country=None,
    )
    with CaptureQueriesContext(connection) as queries:
        assert record.country is None
    assert len(queries) == 0


def test_valid_computed_reference_and_related_value_are_preserved(company):
    country = ResCountry.objects.create(code='XQ', name='Country contract')
    company.country = country

    with CaptureQueriesContext(connection) as queries:
        assert company.country is country
        assert company.country_id == country.pk
        assert company.country_code == 'XQ'
    assert len(queries) == 0


def test_real_missing_reference_still_raises_the_target_error(company):
    company.country_id = 2147483647

    with pytest.raises(ResCountry.DoesNotExist):
        _ = company.country


def test_raw_computed_id_change_invalidates_the_cached_relation(company):
    first = ResCountry.objects.create(code='XQ', name='First country')
    second = ResCountry.objects.create(code='XR', name='Second country')
    company.country = first
    assert company.country is first

    company.country_id = second.pk

    assert company.country.pk == second.pk
    assert company.country_code == 'XR'


def test_stored_required_relation_keeps_its_django_constraint():
    record = ProductProduct(product_tmpl=None)

    with pytest.raises(ProductProduct.product_tmpl.RelatedObjectDoesNotExist):
        _ = record.product_tmpl


def test_wrong_comodel_assignment_is_not_suppressed(company):
    with pytest.raises(ValueError, match='ResCountry'):
        company.country = ResPartner(name='Wrong relation target')
