"""
Tests — Product.weight_kg (peso para cotización de envío por peso, G-ENV-04).

El peso físico habilita el costo de envío por peso (addons.logistics.offers).
Nullable: los productos sin peso caen al costo plano por zona en el checkout.
Sólo el serializer admin lo escribe/expone.
"""
import pytest
from decimal import Decimal
from addons.catalogue.models import Category, Product
from addons.catalogue.serializers import ProductAdminSerializer

pytestmark = pytest.mark.integration


@pytest.fixture
def cat(db):
    return Category.objects.create(name='Velas', slug='velas', is_active=True)


class TestProductWeight:
    def test_weight_kg_opcional_por_defecto_none(self, db, cat):
        p = Product.objects.create(
            name='Vela sin peso', slug='vela-sin-peso', sku='VEL-001',
            price=Decimal('50.00'), stock=5, is_active=True)
        assert p.weight_kg is None

    def test_admin_serializer_escribe_y_expone_weight_kg(self, db, cat):
        ser = ProductAdminSerializer(data={
            'name': 'Vela pesada', 'sku': 'VEL-002', 'base_price': '80.00',
            'category_ids': [cat.id], 'stock': 3, 'weight_kg': '1.250',
            'status': 'BORRADOR',
        })
        assert ser.is_valid(), ser.errors
        prod = ser.save()
        assert prod.weight_kg == Decimal('1.250')
        # se expone de vuelta en la representación admin
        assert Decimal(ProductAdminSerializer(prod).data['weight_kg']) == Decimal('1.250')

    def test_weight_kg_no_negativo(self, db, cat):
        ser = ProductAdminSerializer(data={
            'name': 'Vela neg', 'sku': 'VEL-003', 'base_price': '10.00',
            'category_ids': [cat.id], 'stock': 1, 'weight_kg': '-1.0',
            'status': 'BORRADOR',
        })
        assert not ser.is_valid()
        assert 'weight_kg' in ser.errors
