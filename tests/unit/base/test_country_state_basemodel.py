"""``res.country`` y ``res.country.state`` son ``BaseModel``.

``class ResCountry(models.Model)`` y ``class CountryState(models.Model)``
(``odoo19c: odoo/addons/base/models/res_country.py``). Con ``BaseModel`` un
``Many2one`` vacío hacia el país se lee como el recordset vacío, y quien lo
use como filtro tiene que llevarlo al ``False`` del ``country_id`` de la
fuente (``odoo19c: addons/account/models/account_account_tag.py:88-95``).
"""

import models
import pytest

from addons.account.models import AccountAccountTag
from addons.base.models import ResCompany
from addons.base.models.res_country import ResCountry, ResCountryState

pytestmark = [pytest.mark.unit]


@pytest.mark.parametrize('model', [ResCountry, ResCountryState])
def test_country_and_state_are_basemodel(model):
    """Cada uno hereda ``BaseModel``, que ya lleva el mixin de carga."""
    assert issubclass(model, models.BaseModel)


@pytest.mark.django_db
def test_an_empty_country_filters_tax_tags_by_null():
    """El país vacío de una compañía es un recordset vacío; el dominio de la
    etiqueta lo filtra como país nulo, no como ese recordset."""
    company = ResCompany.objects.create(code='tag-null', name='Tag null')
    domain = AccountAccountTag.get_tax_tags_domain('DIOT: X', company.country)
    assert domain['country'] is None
