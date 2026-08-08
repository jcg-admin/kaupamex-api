"""El impuesto por defecto de la empresa y su herencia al producto (#140→#141).

Es el eslabón que faltaba entre el motor (``compute_all``, :ref:`h-api-342`) y
su consumidor (``SaleOrderLine.price_tax``, :ref:`h-api-340`). Sin él,
reapuntar la línea de venta a los impuestos del producto daría **0** en todo
producto que no declare el suyo — y hoy no hay ninguno que lo declare, porque
nada siembra un ``account.tax``.

La referencia resuelve eso con un ``default`` en el M2M del producto que lee el
campo de la empresa (``odoo19c: account/models/product.py:44`` sobre
``company.py:126-127``; idéntico en ``odoo18c:41``). Aquí el default no puede
ser declarativo —Django no admite ``default=`` en un ``ManyToManyField``, no hay
fila que asociar hasta después del INSERT— así que es un receptor ``post_save``.
Estos tests fijan que el **efecto** sea el mismo, que es lo que importa del
porte.
"""
from decimal import Decimal

import pytest
from django.db.models import ProtectedError

from addons.account.models import AccountTax
from addons.base.models import ResCompany
from addons.product.models import ProductTemplate

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def company():
    return ResCompany.objects.create(code='acme', name='ACME')


@pytest.fixture
def sale_tax(company):
    return AccountTax.objects.create(
        name='IVA 16', amount=Decimal('16'), amount_type='percent',
        type_tax_use='sale', company=company)


class TestCompanyDefaultTaxField:
    def test_company_declares_its_sale_tax(self, company, sale_tax):
        company.account_sale_tax = sale_tax
        company.save(update_fields=['account_sale_tax'])
        company.refresh_from_db()
        assert company.account_sale_tax == sale_tax

    def test_cannot_delete_a_tax_used_as_default(self, company, sale_tax):
        """``PROTECT`` y no ``SET_NULL``.

        Con ``SET_NULL`` el borrado deja a la empresa sin default en silencio,
        y los productos creados a partir de ahí nacen sin impuesto. El error
        ruidoso es la conducta correcta.
        """
        company.account_sale_tax = sale_tax
        company.save(update_fields=['account_sale_tax'])
        with pytest.raises(ProtectedError):
            sale_tax.delete()


class TestProductInheritsCompanyTax:
    def test_new_product_inherits_company_tax(self, company, sale_tax):
        company.account_sale_tax = sale_tax
        company.save(update_fields=['account_sale_tax'])

        product = ProductTemplate.objects.create(name='Eleke', company=company)

        assert list(product.taxes.all()) == [sale_tax]

    def test_without_company_default_product_has_no_taxes(self, company):
        """La contraprueba: el receptor no inventa un impuesto.

        Éste es el estado de HOY en todo despliegue —``account_sale_tax`` es
        ``NULL`` porque nada lo puebla— y es exactamente la razón por la que
        #141 no se puede cerrar antes que #145: reapuntar ``price_tax`` aquí
        daría cero.
        """
        product = ProductTemplate.objects.create(name='Eleke', company=company)
        assert list(product.taxes.all()) == []

    def test_does_not_override_declared_taxes(self, company, sale_tax):
        """Es un ``default``, no un compute: sólo actúa si el M2M quedó vacío."""
        other_tax = AccountTax.objects.create(
            name='IVA 8 frontera', amount=Decimal('8'), amount_type='percent',
            type_tax_use='sale', company=company)
        company.account_sale_tax = sale_tax
        company.save(update_fields=['account_sale_tax'])

        product = ProductTemplate.objects.create(name='Eleke', company=company)
        product.taxes.set([other_tax])
        product.save()
        product.refresh_from_db()

        assert list(product.taxes.all()) == [other_tax]

    def test_later_edit_does_not_restore_default(self, company, sale_tax):
        """Quitar los impuestos a mano es una decisión; el receptor no la deshace.

        Si actuara en cada ``save()`` en vez de sólo al crear, un producto sin
        impuestos sería imposible de expresar.
        """
        company.account_sale_tax = sale_tax
        company.save(update_fields=['account_sale_tax'])
        product = ProductTemplate.objects.create(name='Eleke', company=company)
        assert list(product.taxes.all()) == [sale_tax]

        product.taxes.clear()
        product.name = 'Eleke de Yemayá'
        product.save()
        product.refresh_from_db()

        assert list(product.taxes.all()) == []

    def test_product_without_company_does_not_crash(self, company, sale_tax):
        """``company`` es opcional en nuestro ``ProductTemplate``.

        El receptor sale temprano en vez de lanzar ``AttributeError`` — un
        default que rompe la creación sería peor que no tener default.
        """
        company.account_sale_tax = sale_tax
        company.save(update_fields=['account_sale_tax'])
        product = ProductTemplate.objects.create(name='Sin empresa')
        assert list(product.taxes.all()) == []
