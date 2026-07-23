"""Tests — addons ``sms`` + ``sale_sms`` (confirmación SMS de la orden)."""
import pytest

from addons.sale.models import SaleOrder
from addons.sale_sms.models import SaleOrderSmsConfirmation
from addons.sms.models import SmsSms, SmsTemplate

pytestmark = pytest.mark.integration


def test_sms_defaults_and_transitions(db):
    sms = SmsSms.objects.create(number='+525599887766', body='Hola')
    assert sms.state == SmsSms.STATE_PENDING
    assert sms.error_code == ''
    sms.mark_sent()
    assert sms.state == SmsSms.STATE_SENT
    sms.mark_error('sms_number_format')
    assert sms.state == SmsSms.STATE_ERROR
    assert sms.error_code == 'sms_number_format'


def test_sms_template_render_tolerant(db):
    tpl = SmsTemplate.objects.create(
        name='Confirmación', body='Orden {order} por ${total}. Gracias {missing}',
    )
    out = tpl.render({'order': 'S-ABCD1234', 'total': '199.00'})
    assert 'Orden S-ABCD1234 por $199.00' in out
    # Placeholder ausente queda literal, no rompe.
    assert '{missing}' in out


def test_sale_order_sms_confirmation_send(db):
    tpl = SmsTemplate.objects.create(name='Conf', body='Orden {order} total ${total}')
    order = SaleOrder.objects.create()
    link = SaleOrderSmsConfirmation.send_for(order, '+525511223344', tpl)
    assert order.sms_confirmation.message == link.message
    assert link.message.number == '+525511223344'
    # Orden en draft aún no tiene name → placeholder queda vacío; el total sí.
    assert 'total $0.00' in link.message.body
    assert link.message.state == SmsSms.STATE_PENDING


def test_sale_order_sms_confirmation_idempotent(db):
    tpl = SmsTemplate.objects.create(name='Conf', body='Orden {order}')
    order = SaleOrder.objects.create()
    SaleOrderSmsConfirmation.send_for(order, '+525511223344', tpl)
    SaleOrderSmsConfirmation.send_for(order, '+525599990000', tpl)
    # Un único registro de confirmación por orden (update_or_create).
    assert SaleOrderSmsConfirmation.objects.filter(order=order).count() == 1
    order.refresh_from_db()
    assert order.sms_confirmation.message.number == '+525599990000'
