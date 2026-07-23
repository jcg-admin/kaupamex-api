"""
Tests del builder puro del payload Orders (T-201a).

Verifican la estructura PROVEN de la colección Postman: type=online, importes
STRING, discriminante payment_method.type, processing/capture automatic
(DEC-ORD-02), payer/items inline. No hace red — solo construye el dict desde
un Order real.
"""
import pytest
from decimal import Decimal

from addons.orders.models import Order, OrderItem, OrderValue, OrderAddress
from addons.payment_mercado_pago.gateway import (
    _build_order_payload,
    _build_order_payment_method,
    _amount_str,
    _money_number,
)

pytestmark = pytest.mark.integration


def _make_order(user, total='200.00'):
    order = Order.objects.create(user=user, status='PENDING')
    OrderItem.objects.create(
        order=order, product_name='Smartphone', sku='SKU-201A',
        unit_price=Decimal(total), quantity=1, subtotal=Decimal(total),
    )
    OrderValue.objects.create(
        order=order, subtotal=Decimal(total), tax=Decimal('0'),
        shipping_cost=Decimal('0'), discount=Decimal('0'), total=Decimal(total),
    )
    OrderAddress.objects.create(
        order=order, recipient_name='Juan Perez', street='Calle 10',
        city='CDMX', state='CMX', zip_code='06600', phone='5512345678',
    )
    return order


class TestAmountStr:
    def test_two_decimals_string(self):
        assert _amount_str(Decimal('12.9')) == '12.90'
        assert _amount_str('200') == '200.00'
        assert _amount_str(Decimal('12.905')) == '12.90'  # quantize floor


class TestMoneyNumber:
    """_money_number: importe->float con 2 decimales, sin artefacto IEEE-754.

    Mitiga el error de coma flotante descrito por el estándar IEEE 754:
    valores como 0.1 no son representables en binario, así que operar en
    float acumula error. Cuantizando a 2 decimales ANTES de cruzar a float
    el valor que llega a la pasarela es siempre un importe monetario limpio.
    """
    def test_two_decimals_number(self):
        assert _money_number(Decimal('12.9')) == 12.90
        assert _money_number('200') == 200.0
        assert _money_number(Decimal('12.905')) == 12.90  # HALF_EVEN

    def test_neutraliza_artefacto_de_coma_flotante(self):
        # 0.1 sumado 3 veces en float da 0.30000000000000004 (IEEE-754).
        contaminado = 0.1 + 0.1 + 0.1        # 0.30000000000000004
        assert contaminado != 0.30           # el defecto existe
        assert _money_number(Decimal('0.1') * 3) == 0.30   # Decimal exacto
        assert _money_number(contaminado) == 0.30          # cuantizado limpio

    def test_coincide_con_amount_str(self):
        # Ambos helpers redondean idéntico; sólo difiere el tipo de salida.
        for v in ['19.99', '0.1', '12.905', '200', '1234.5']:
            assert str(_money_number(v)) == _amount_str(v) or \
                   f'{_money_number(v):.2f}' == _amount_str(v)


class TestPaymentMethodBlock:
    def test_credit_card_has_token_and_installments(self):
        pm = _build_order_payment_method('visa', 'credit_card', token='TKN', installments=3)
        assert pm == {'id': 'visa', 'type': 'credit_card', 'token': 'TKN', 'installments': 3}

    def test_card_with_statement_descriptor(self):
        pm = _build_order_payment_method('master', 'credit_card', token='T', statement_descriptor='YORUBA')
        assert pm['statement_descriptor'] == 'YORUBA'

    def test_non_card_omits_token_and_installments(self):
        pm = _build_order_payment_method('oxxo', 'ticket')
        assert pm == {'id': 'oxxo', 'type': 'ticket'}
        assert 'token' not in pm and 'installments' not in pm


class TestBuildOrderPayload:
    def test_core_structure_card(self, user, db):
        order = _make_order(user, '200.00')
        p = _build_order_payload(
            order, payment_method_id='visa', payment_type='credit_card',
            token='CARD-TKN', installments=1,
        )
        assert p['type'] == 'online'
        assert p['external_reference'] == order.order_number
        assert p['processing_mode'] == 'automatic'
        assert p['capture_mode'] == 'automatic'
        # importes STRING, cuadran orden vs pago
        assert p['total_amount'] == '200.00'
        pay = p['transactions']['payments'][0]
        assert pay['amount'] == '200.00'
        assert pay['payment_method']['id'] == 'visa'
        assert pay['payment_method']['type'] == 'credit_card'
        assert pay['payment_method']['token'] == 'CARD-TKN'

    def test_amounts_are_strings_not_floats(self, user, db):
        order = _make_order(user, '12.90')
        p = _build_order_payload(order, payment_method_id='visa', payment_type='credit_card', token='T')
        assert isinstance(p['total_amount'], str)
        assert isinstance(p['transactions']['payments'][0]['amount'], str)
        assert isinstance(p['items'][0]['unit_price'], str)

    def test_no_explicit_3ds_config_key_for_card(self, user, db):
        """H-ORD-07 (T-202): el Orders API rechaza toda clave de config 3DS en
        el create (400 unsupported_properties). El 3DS on_fraud_risk (DEC-ORD-02)
        lo aplica MP automáticamente por riesgo — el payload NO debe emitir
        ``config`` ni ``three_d_secure_mode`` en ningún nivel."""
        order = _make_order(user)
        p = _build_order_payload(order, payment_method_id='visa', payment_type='credit_card', token='T')
        pm = p['transactions']['payments'][0]['payment_method']
        assert 'config' not in pm
        assert 'three_d_secure_mode' not in pm
        assert 'config' not in p                     # sin config a nivel order
        assert 'three_d_secure_mode' not in p['transactions']['payments'][0]

    def test_non_card_has_no_3ds_no_token(self, user, db):
        order = _make_order(user)
        p = _build_order_payload(order, payment_method_id='oxxo', payment_type='ticket')
        pm = p['transactions']['payments'][0]['payment_method']
        assert 'config' not in pm
        assert 'token' not in pm

    def test_payer_and_items_inline(self, user, db):
        order = _make_order(user)
        p = _build_order_payload(
            order, payment_method_id='visa', payment_type='credit_card', token='T',
            payer_identification_type='RFC', payer_identification_number='XAXX010101000',
        )
        assert p['payer']['email']
        assert p['payer']['identification'] == {'type': 'RFC', 'number': 'XAXX010101000'}
        assert p['items'][0]['title'] == 'Smartphone'
