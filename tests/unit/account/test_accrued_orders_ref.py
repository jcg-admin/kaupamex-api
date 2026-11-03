"""La referencia del asiento de devengo lleva la fecha con formato de idioma.

≙ ``_compute_move_vals`` (``odoo19c:
addons/account/wizard/accrued_orders.py:358``,
LGPL-3)::

    'ref': _('Accrued %(entry_type)s entry as of %(date)s',
             entry_type=move_type, date=format_date(self.env, self.date)),

``format_date`` aplica el ``date_format`` del idioma del entorno; con
``en_US`` es ``%m/%d/%Y``. Un ``isoformat`` daría ``2026-01-31``, así que la
fecha del caso tiene día mayor que doce para que los dos formatos no
coincidan por accidente.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from addons.account.models import AccountAccount
from addons.account.wizard.accrued_orders import AccountAccruedOrdersWizard
from addons.base.models import ResCompany
from addons.sale.models import SaleOrder, SaleOrderLine
from orm.environments import Environment, user_scope
from orm.utils import SUPERUSER_ID
from tests.factories.product_factory import make_product

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def environment(db):
    user = get_user_model().objects.create_user(
        login='devengo.referencia@kaupamex.mx', password='Devengo123!')
    with Environment(None, SUPERUSER_ID, {}), user_scope(user.pk):
        yield


def test_the_ref_formats_the_date_for_the_language(environment):
    company = ResCompany.objects.create(code='devengo', name='Devengo')
    income = AccountAccount.objects.create(
        code='401', name='Ventas', account_type='income', company=company)
    product = make_product(name='Eleke devengo')
    product.product_tmpl.property_account_income = income
    product.product_tmpl.save()
    order = SaleOrder.objects.create(company=company)
    SaleOrderLine.objects.create(order=order, product=product,
                                 product_uom_qty=Decimal('1'),
                                 price_unit=Decimal('100.00'))
    move_vals, _ = AccountAccruedOrdersWizard._compute_move_vals(
        [order], company, None, date(2026, 1, 31), income,
        amount=Decimal('10.00'))
    assert move_vals['ref'] == 'Accrued Revenue entry as of 01/31/2026'
