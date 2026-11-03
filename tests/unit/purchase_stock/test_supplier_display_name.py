"""El nombre para mostrar de una tarifa formatea su precio con ``formatLang``.

≙ ``ProductSupplierinfo._compute_display_name`` (``odoo19c:
purchase_stock/models/product.py:290-298``, LGPL-3)::

    price_str = formatLang(self.env, supplier.price,
                           currency_obj=supplier.currency_id)

El precio sale agrupado por miles, con los decimales de la moneda y su
símbolo separado por un espacio duro: lo que una f-string sobre el valor no
produce. Los casos usan un precio con miles y sin decimales propios para que
la diferencia sea visible.
"""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from addons.base.models import ResPartner
from addons.base.models.res_currency import ResCurrency
from addons.product.models import ProductSupplierinfo, ProductTemplate
from orm.environments import Environment, user_scope
from orm.utils import SUPERUSER_ID

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def environment(db):
    user = get_user_model().objects.create_user(
        login='tarifa.nombre@kaupamex.mx', password='Tarifa123!')
    with Environment(None, SUPERUSER_ID, {}), user_scope(user.pk):
        yield


def _tariff(**kwargs):
    template = ProductTemplate.objects.create(name='Eleke')
    partner = ResPartner.objects.create(name='Proveedor')
    return ProductSupplierinfo.objects.create(
        partner=partner, product_tmpl=template, min_qty=3,
        price=Decimal('1234.5'), **kwargs)


def test_the_price_is_formatted_with_the_currency(environment):
    currency, _ = ResCurrency.objects.get_or_create(
        name='MXN', defaults={'symbol': '$'})
    tariff = _tariff(currency=currency)
    price = f'{currency.symbol}\N{NO-BREAK SPACE}1,234.50'
    if currency.position == 'after':
        price = f'1,234.50\N{NO-BREAK SPACE}{currency.symbol}'
    assert tariff.display_name.endswith(f'- {price})')


def test_without_currency_the_price_is_still_grouped(environment):
    tariff = _tariff()
    assert tariff.display_name.endswith('- 1,234.50)')
