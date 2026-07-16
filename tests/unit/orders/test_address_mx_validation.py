"""Validación MX de dirección de checkout (Teléfono 10 / C.P. 5).

Regla del proyecto (México): el teléfono, si se envía, debe tener
EXACTAMENTE 10 dígitos, y el código postal EXACTAMENTE 5 — sin espacios,
guiones ni prefijo +52. Defensa en profundidad junto a la validación del
front (ver iniciativa hardening-checkout-envio-mexico).
"""
import pytest

from apps.addons.orders.serializers import (
    OrderAddressInputSerializer,
    UpdateAddressSerializer,
)

BASE = dict(
    recipient_name='Ala Yoruba',
    street='Av. Reforma 1',
    city='Cuauhtémoc',
    state='CDMX',
    zip_code='06600',
    country='MX',
    phone='5512345678',
)

SERIALIZERS = [OrderAddressInputSerializer, UpdateAddressSerializer]


@pytest.mark.parametrize('serializer_cls', SERIALIZERS)
def test_valid_address_passes(serializer_cls):
    assert serializer_cls(data=dict(BASE)).is_valid(), serializer_cls.__name__


@pytest.mark.parametrize('serializer_cls', SERIALIZERS)
@pytest.mark.parametrize('phone', [
    '551234567',       # 9 dígitos
    '55123456789',     # 11 dígitos
    '55-1234-5678',    # con guiones
    '55 1234 5678',    # con espacios
    '+525512345678',   # con +52
    'abcdefghij',      # no numérico
])
def test_phone_must_be_exactly_10_digits(serializer_cls, phone):
    s = serializer_cls(data={**BASE, 'phone': phone})
    assert not s.is_valid()
    assert 'phone' in s.errors


@pytest.mark.parametrize('serializer_cls', SERIALIZERS)
@pytest.mark.parametrize('zip_code', [
    '1234',    # 4 dígitos
    '123456',  # 6 dígitos
    'abcde',   # no numérico
    '06 60',   # con espacio
    '0660-',   # con guion
])
def test_zip_must_be_exactly_5_digits(serializer_cls, zip_code):
    s = serializer_cls(data={**BASE, 'zip_code': zip_code})
    assert not s.is_valid()
    assert 'zip_code' in s.errors


@pytest.mark.parametrize('serializer_cls', SERIALIZERS)
def test_empty_phone_is_allowed(serializer_cls):
    # phone es opcional (default=''); el front lo exige, el back solo valida
    # el formato cuando viene un valor. No debe romper flujos que lo omiten.
    data = {k: v for k, v in BASE.items() if k != 'phone'}
    assert serializer_cls(data=data).is_valid(), serializer_cls.__name__
