"""La superficie ``_inherit`` de ``account`` sobre el producto (T-B2a).

Sin estos campos, una línea de venta recibe su impuesto cableado desde fuera
en vez de resolverlo desde el producto, y una factura no sabe a qué cuenta
imputar. Esto verifica las dos mitades del bloque:

1. **Que la extensión se aplicó** — los 7 campos existen en modelos que
   ``account`` no declara. Es la prueba del mecanismo (``add_to_class`` desde
   ``AccountConfig.ready()``), no de un modelo propio.
2. **Que la resolución en cascada funciona** — producto → categoría →
   ascendiente, con el remapeo de la posición fiscal encima.

El tercer escalón de la referencia (la cuenta por defecto de la empresa) NO
se prueba porque **no está portado**: ``ResCompany`` no declara
``income_account_id``. El test de abajo fija ese hueco explícitamente en vez
de omitirlo, para que no se lea como cobertura.
"""
import pathlib
import sys

import pytest
from django.db.models import ProtectedError

from addons.account.models import (
    AccountAccount,
    AccountAccountTag,
    AccountFiscalPosition,
    AccountFiscalPositionAccount,
    AccountTax,
)
from addons.base.models import ResCompany
from addons.product.models import ProductCategory, ProductProduct, ProductTemplate

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def company():
    return ResCompany.objects.create(code='acme', name='ACME')


@pytest.fixture
def cuentas(company):
    ingreso = AccountAccount.objects.create(
        code='401', name='Ventas', account_type='income', company=company)
    gasto = AccountAccount.objects.create(
        code='601', name='Compras', account_type='expense', company=company)
    return ingreso, gasto


class TestLaExtensionSeAplico:
    """El mecanismo — ``account`` cuelga campos de modelos que no declara."""

    @pytest.mark.parametrize('campo', [
        'taxes', 'supplier_taxes', 'property_account_income',
        'property_account_expense', 'account_tags',
    ])
    def test_product_template_recibe_sus_cinco_campos(self, campo):
        nombres = {f.name for f in ProductTemplate._meta.get_fields()}
        assert campo in nombres

    @pytest.mark.parametrize('campo', [
        'property_account_income_categ', 'property_account_expense_categ',
    ])
    def test_product_category_recibe_sus_dos_campos(self, campo):
        nombres = {f.name for f in ProductCategory._meta.get_fields()}
        assert campo in nombres

    def test_product_no_menciona_la_contabilidad(self):
        """El sentido del mecanismo: el addon extendido no importa al extensor.

        Si esto se rompe, la extensión dejó de ser Open/Closed y ``product``
        adquirió una razón de cambio que es de contabilidad.
        """
        origen = pathlib.Path(
            sys.modules[ProductTemplate.__module__].__file__).parent
        medidos = sorted(origen.glob('*.py'))
        # El denominador va en el assert: un glob vacío daría verde sin medir
        # nada — el "cero falso" que H-DOCS-21 registró.
        assert len(medidos) > 10, f'alcance sospechoso: {len(medidos)} archivos'
        con_account = [
            py.name for py in medidos if 'addons.account' in py.read_text()
        ]
        assert con_account == []


class TestResolucionDeCuenta:
    """Los dos escalones portados de ``_get_product_accounts``."""

    def test_la_cuenta_del_producto_gana(self, cuentas):
        ingreso, gasto = cuentas
        otra = AccountAccount.objects.create(
            code='402', name='Otros ingresos', account_type='income',
            company=ingreso.company)
        categoria = ProductCategory.objects.create(
            name='Collares', property_account_income_categ=otra)
        producto = ProductTemplate.objects.create(
            name='Eleke', categ=categoria, property_account_income=ingreso)

        assert producto._get_product_accounts()['income'] == ingreso

    def test_sin_cuenta_propia_baja_a_la_categoria(self, cuentas):
        ingreso, gasto = cuentas
        categoria = ProductCategory.objects.create(
            name='Collares',
            property_account_income_categ=ingreso,
            property_account_expense_categ=gasto)
        producto = ProductTemplate.objects.create(name='Eleke', categ=categoria)

        cuentas_resueltas = producto._get_product_accounts()
        assert cuentas_resueltas['income'] == ingreso
        assert cuentas_resueltas['expense'] == gasto

    def test_sube_el_arbol_hasta_el_ascendiente_que_la_tiene(self, cuentas):
        """No es "la cuenta de mi categoría": es la del primer ascendiente.

        Configurar una vez arriba y heredar hacia abajo es el punto entero de
        que la referencia recorra ``categ.parent`` en bucle.
        """
        ingreso, _ = cuentas
        abuela = ProductCategory.objects.create(
            name='Religiosos', property_account_income_categ=ingreso)
        madre = ProductCategory.objects.create(name='Collares', parent=abuela)
        hija = ProductCategory.objects.create(name='Elekes', parent=madre)
        producto = ProductTemplate.objects.create(name='Eleke', categ=hija)

        assert producto._get_product_accounts()['income'] == ingreso

    def test_sin_nada_devuelve_none_y_ese_es_el_hueco_declarado(self):
        """El tercer escalón de la referencia NO está portado.

        Allá caería en ``company.income_account_id``; aquí ``ResCompany`` no
        declara ese campo (Bloque 1, tarea #137), así que devuelve ``None``.
        Se fija aquí para que el hueco sea visible, no para celebrarlo.
        """
        categoria = ProductCategory.objects.create(name='Collares')
        producto = ProductTemplate.objects.create(name='Eleke', categ=categoria)

        assert producto._get_product_accounts() == {'income': None,
                                                    'expense': None}

    def test_la_variante_delega_en_su_plantilla(self, cuentas):
        ingreso, _ = cuentas
        categoria = ProductCategory.objects.create(name='Collares')
        plantilla = ProductTemplate.objects.create(
            name='Eleke', categ=categoria, property_account_income=ingreso)
        variante = ProductProduct.objects.create(product_tmpl=plantilla)

        assert variante._get_product_accounts()['income'] == ingreso


class TestPosicionFiscal:
    def test_remapea_la_cuenta_resuelta(self, cuentas, company):
        """El punto donde un cliente de otro régimen imputa a otra cuenta.

        Sin tocar el producto: es lo que hace ``get_product_accounts`` y no
        ``_get_product_accounts``.
        """
        ingreso, _ = cuentas
        destino = AccountAccount.objects.create(
            code='403', name='Ventas exentas', account_type='income',
            company=company)
        posicion = AccountFiscalPosition.objects.create(
            name='Exento', company=company)
        AccountFiscalPositionAccount.objects.create(
            position=posicion, account_src=ingreso, account_dest=destino)

        categoria = ProductCategory.objects.create(name='Collares')
        producto = ProductTemplate.objects.create(
            name='Eleke', categ=categoria, property_account_income=ingreso)

        assert producto.get_product_accounts()['income'] == ingreso
        assert producto.get_product_accounts(posicion)['income'] == destino


class TestImpuestosYEtiquetas:
    def test_los_dos_m2m_son_independientes(self, company):
        """Vender y comprar el mismo producto no lleva el mismo impuesto.

        Por eso la referencia declara dos relaciones y no una con un filtro:
        ``product_taxes_rel`` y ``product_supplier_taxes_rel``.
        """
        iva_venta = AccountTax.objects.create(
            name='IVA 16 venta', amount=16, type_tax_use='sale',
            company=company)
        iva_compra = AccountTax.objects.create(
            name='IVA 16 compra', amount=16, type_tax_use='purchase',
            company=company)
        categoria = ProductCategory.objects.create(name='Collares')
        producto = ProductTemplate.objects.create(name='Eleke', categ=categoria)

        producto.taxes.add(iva_venta)
        producto.supplier_taxes.add(iva_compra)

        assert list(producto.taxes.all()) == [iva_venta]
        assert list(producto.supplier_taxes.all()) == [iva_compra]

    def test_un_producto_nace_sin_impuestos(self):
        """Divergencia declarada, no descuido.

        La referencia da a ``taxes_id`` el default
        ``env.companies.account_sale_tax_id``; ese campo es del Bloque 1 y no
        existe (tarea #137). Se fija el comportamiento real para que el día
        que #137 entre, este test falle y obligue a revisarlo.
        """
        categoria = ProductCategory.objects.create(name='Collares')
        producto = ProductTemplate.objects.create(name='Eleke', categ=categoria)

        assert producto.taxes.count() == 0
        assert producto.supplier_taxes.count() == 0

    def test_las_etiquetas_de_cuenta_cuelgan_del_producto(self, company):
        etiqueta = AccountAccountTag.objects.create(
            name='Exportación', applicability='products')
        categoria = ProductCategory.objects.create(name='Collares')
        producto = ProductTemplate.objects.create(name='Eleke', categ=categoria)

        producto.account_tags.add(etiqueta)

        assert list(producto.account_tags.all()) == [etiqueta]


class TestProtect:
    def test_no_se_borra_una_cuenta_usada_por_un_producto(self, cuentas):
        """``ondelete='restrict'`` de la referencia → ``PROTECT``.

        Dejar el producto sin cuenta al borrarla es peor que no poder
        borrarla: la factura siguiente no sabría dónde imputar.
        """
        ingreso, _ = cuentas
        categoria = ProductCategory.objects.create(name='Collares')
        ProductTemplate.objects.create(
            name='Eleke', categ=categoria, property_account_income=ingreso)

        with pytest.raises(ProtectedError):
            ingreso.delete()
