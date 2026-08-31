"""Tests unitarios — modelos del addon ``product`` (ex ``catalogue``/``chartsize``).

Los addons ``catalogue`` y ``chartsize`` fueron eliminados; sus responsabilidades
viven ahora en ``addons.product`` como una adaptación fiel de Odoo:

- ``product.ProductTemplate`` — la ficha (antes ``catalogue.Product``).
- ``product.ProductProduct`` — la variante (antes ``chartsize.ProductVariant``;
  el eje "variante" se colapsó: ``product.product`` YA es la variante).
- ``product.ProductCategory`` — el árbol de categorías (antes ``catalogue.Category``).
- ``product.ProductAttribute``/``ProductAttributeValue`` — atributos reutilizables
  (antes ``chartsize.VariantType``/``VariantOption``, que eran por-producto).

Cubre lo que no depende de la base de datos real de forma esencial (aunque usa
``@pytest.mark.django_db`` porque el ORM lo exige): construcción de nombres,
invariantes de ``clean()``, combinación de variantes y delegación a la ficha.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from addons.base.models import ResPartner
from addons.crm.models.crm_lead import CrmLead
from addons.product.models.product_supplierinfo import ProductSupplierinfo
from addons.stock.models.stock_quant import StockQuant
from addons.product.models import (
    ProductAttribute,
    ProductAttributeValue,
    ProductCategory,
    ProductCombo,
    ProductComboItem,
    ProductProduct,
    ProductTemplate,
    ProductTemplateAttributeLine,
    ProductTemplateAttributeValue,
)
from addons.product.models.product_template import (
    TYPE_COMBO,
    TYPE_SERVICE,
)

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


# =============================================================================
# ProductCategory — árbol (complete_name, parent_path, product_count)
# =============================================================================

class TestProductCategory:

    def test_complete_name_raiz_es_su_propio_nombre(self):
        cat = ProductCategory.objects.create(name='Collares')
        assert cat.complete_name == 'Collares'

    def test_complete_name_hijo_concatena_con_separador(self):
        padre = ProductCategory.objects.create(name='Collares')
        hijo = ProductCategory.objects.create(name='Elekes', parent=padre)
        assert hijo.complete_name == 'Collares / Elekes'

    def test_parent_path_materializa_la_ruta(self):
        padre = ProductCategory.objects.create(name='Collares')
        hijo = ProductCategory.objects.create(name='Elekes', parent=padre)
        assert hijo.parent_path == f'{padre.pk}/{hijo.pk}/'

    def test_renombrar_padre_repropaga_a_los_hijos(self):
        padre = ProductCategory.objects.create(name='Collares')
        hijo = ProductCategory.objects.create(name='Elekes', parent=padre)
        padre.name = 'Collares Sagrados'
        padre.save()
        hijo.refresh_from_db()
        assert hijo.complete_name == 'Collares Sagrados / Elekes'

    def test_clean_rechaza_categoria_como_su_propio_padre(self):
        cat = ProductCategory.objects.create(name='Collares')
        cat.parent = cat
        with pytest.raises(ValidationError):
            cat.clean()

    def test_clean_rechaza_ciclo_indirecto(self):
        a = ProductCategory.objects.create(name='A')
        b = ProductCategory.objects.create(name='B', parent=a)
        a.parent = b
        with pytest.raises(ValidationError):
            a.clean()

    def test_product_count_cuenta_los_de_la_categoria(self):
        cat = ProductCategory.objects.create(name='Collares')
        ProductTemplate.objects.create(name='Eleke', categ=cat)
        assert cat.product_count == 1

    def test_product_count_cuenta_toda_la_rama(self):
        """``child_of`` en la referencia: cuenta las hijas, pese a que su
        propia ayuda diga lo contrario (odoo19c: product_category.py).
        """
        padre = ProductCategory.objects.create(name='Joyería')
        hija  = ProductCategory.objects.create(name='Collares', parent=padre)
        ProductTemplate.objects.create(name='Eleke', categ=hija)
        ProductTemplate.objects.create(name='Ide',   categ=padre)
        assert padre.product_count == 2
        assert hija.product_count == 1

    def test_product_count_vacia_es_cero(self):
        cat = ProductCategory.objects.create(name='Sin productos')
        assert cat.product_count == 0


# =============================================================================
# ProductAttribute / ProductAttributeValue — reutilizables entre productos
# =============================================================================

class TestProductAttribute:

    def test_value_str_incluye_el_atributo(self):
        color = ProductAttribute.objects.create(name='Color')
        rojo = ProductAttributeValue.objects.create(attribute=color, name='Rojo')
        assert str(rojo) == 'Color: Rojo'

    def test_unique_attribute_value_name(self):
        color = ProductAttribute.objects.create(name='Color')
        ProductAttributeValue.objects.create(attribute=color, name='Rojo')
        with pytest.raises(Exception):
            ProductAttributeValue.objects.create(attribute=color, name='Rojo')

    def test_mismo_nombre_en_otro_atributo_no_choca(self):
        color = ProductAttribute.objects.create(name='Color')
        talla = ProductAttribute.objects.create(name='Talla')
        ProductAttributeValue.objects.create(attribute=color, name='Rojo')
        # 'Rojo' es una talla rara pero la unicidad es por (attribute, name).
        v2 = ProductAttributeValue.objects.create(attribute=talla, name='Rojo')
        assert v2.pk is not None


# =============================================================================
# ProductTemplate — invariantes de tipo (consu/service/combo)
# =============================================================================

class TestProductTemplateClean:

    def test_service_con_peso_es_invalido(self):
        tmpl = ProductTemplate(
            name='Consultoría', type=TYPE_SERVICE, weight=1.0)
        with pytest.raises(ValidationError):
            tmpl.clean()

    def test_service_con_volumen_es_invalido(self):
        tmpl = ProductTemplate(
            name='Consultoría', type=TYPE_SERVICE, volume=1.0)
        with pytest.raises(ValidationError):
            tmpl.clean()

    def test_service_sin_peso_ni_volumen_es_valido(self):
        tmpl = ProductTemplate(name='Consultoría', type=TYPE_SERVICE)
        tmpl.clean()  # no debe levantar

    def test_combo_con_costo_propio_es_invalido(self):
        tmpl = ProductTemplate(
            name='Menú', type=TYPE_COMBO,
            standard_price=Decimal('10.00'))
        with pytest.raises(ValidationError):
            tmpl.clean()

    def test_combo_sin_costo_es_valido(self):
        tmpl = ProductTemplate(name='Menú', type=TYPE_COMBO)
        tmpl.clean()  # no debe levantar

    def test_is_product_variant_falso_en_la_ficha(self):
        tmpl = ProductTemplate.objects.create(name='Eleke')
        assert tmpl.is_product_variant is False


class TestProductTemplateComboInvariants:

    def test_combo_con_lineas_de_atributo_es_invalido(self):
        tmpl = ProductTemplate.objects.create(
            name='Menú', type=TYPE_COMBO)
        color = ProductAttribute.objects.create(name='Color')
        ProductTemplateAttributeLine.objects.create(
            product_tmpl=tmpl, attribute=color)
        with pytest.raises(ValidationError):
            tmpl.check_combo_has_no_attributes()

    def test_consu_con_lineas_de_atributo_es_valido(self):
        tmpl = ProductTemplate.objects.create(name='Eleke')
        color = ProductAttribute.objects.create(name='Color')
        ProductTemplateAttributeLine.objects.create(
            product_tmpl=tmpl, attribute=color)
        tmpl.check_combo_has_no_attributes()  # no debe levantar

    def test_combo_sin_elecciones_es_invalido(self):
        tmpl = ProductTemplate.objects.create(
            name='Menú', type=TYPE_COMBO)
        with pytest.raises(ValidationError):
            tmpl.check_combo_choices()

    def test_combo_con_eleccion_vendible_es_valido(self):
        tmpl = ProductTemplate.objects.create(
            name='Menú', type=TYPE_COMBO, sale_ok=True)
        bebida_tmpl = ProductTemplate.objects.create(name='Refresco')
        bebida_variant = ProductProduct.objects.create(product_tmpl=bebida_tmpl)
        combo = ProductCombo.objects.create(name='Bebida')
        ProductComboItem.objects.create(combo=combo, product=bebida_variant)
        tmpl.combo_ids.add(combo)
        tmpl.check_combo_choices()  # no debe levantar

    def test_combo_a_la_venta_con_opcion_no_vendible_es_invalido(self):
        tmpl = ProductTemplate.objects.create(
            name='Menú', type=TYPE_COMBO, sale_ok=True)
        bebida_tmpl = ProductTemplate.objects.create(
            name='Refresco agotado', sale_ok=False)
        bebida_variant = ProductProduct.objects.create(product_tmpl=bebida_tmpl)
        combo = ProductCombo.objects.create(name='Bebida')
        ProductComboItem.objects.create(combo=combo, product=bebida_variant)
        tmpl.combo_ids.add(combo)
        with pytest.raises(ValidationError):
            tmpl.check_combo_choices()


# =============================================================================
# ProductProduct — la variante: combinación, delegación, precio
# =============================================================================

class TestProductProduct:

    def test_delega_nombre_categoria_y_uom_de_la_ficha(self):
        cat = ProductCategory.objects.create(name='Collares')
        tmpl = ProductTemplate.objects.create(name='Eleke', categ=cat)
        variante = ProductProduct.objects.create(product_tmpl=tmpl)
        assert variante.name == 'Eleke'
        assert variante.categ == cat

    def test_is_product_variant_verdadero_en_la_variante(self):
        tmpl = ProductTemplate.objects.create(name='Eleke')
        variante = ProductProduct.objects.create(product_tmpl=tmpl)
        assert variante.is_product_variant is True

    def test_str_usa_default_code_cuando_existe(self):
        tmpl = ProductTemplate.objects.create(name='Eleke')
        variante = ProductProduct.objects.create(
            product_tmpl=tmpl, default_code='ELK-001')
        assert str(variante) == '[ELK-001] Eleke'

    def test_str_sin_default_code_usa_display_name(self):
        tmpl = ProductTemplate.objects.create(name='Eleke')
        variante = ProductProduct.objects.create(product_tmpl=tmpl)
        assert str(variante) == 'Eleke'

    def test_build_combination_indices_ordena_los_ids(self):
        # sorted([30, 10, 20]) -> '10,20,30' — sin el sort la clave dependería
        # del orden de selección y "¿existe ya esta combinación?" fallaría.
        indices = ProductProduct.build_combination_indices([30, 10, 20])
        assert indices == '10,20,30'

    def test_refresh_combination_indices_usa_los_valores_reales(self):
        color = ProductAttribute.objects.create(name='Color')
        rojo = ProductAttributeValue.objects.create(attribute=color, name='Rojo')
        tmpl = ProductTemplate.objects.create(name='Eleke')
        line = ProductTemplateAttributeLine.objects.create(
            product_tmpl=tmpl, attribute=color)
        line.values.set([rojo])
        ptav = ProductTemplateAttributeValue.objects.create(
            line=line, attribute_value=rojo)
        variante = ProductProduct.objects.create(product_tmpl=tmpl)
        variante.product_template_attribute_values.set([ptav])
        variante.refresh_combination_indices()
        assert variante.combination_indices == str(ptav.pk)

    def test_lst_price_suma_el_extra_de_los_atributos(self):
        color = ProductAttribute.objects.create(name='Color')
        dorado = ProductAttributeValue.objects.create(attribute=color, name='Dorado')
        tmpl = ProductTemplate.objects.create(
            name='Eleke', list_price=Decimal('100.00'))
        line = ProductTemplateAttributeLine.objects.create(
            product_tmpl=tmpl, attribute=color)
        line.values.set([dorado])
        ptav = ProductTemplateAttributeValue.objects.create(
            line=line, attribute_value=dorado, price_extra=Decimal('30.00'))
        variante = ProductProduct.objects.create(product_tmpl=tmpl)
        variante.product_template_attribute_values.set([ptav])
        assert variante.list_price == Decimal('100.00')
        assert variante.price_extra == Decimal('30.00')
        assert variante.lst_price == Decimal('130.00')

    def test_display_name_excluye_valores_no_distintivos(self):
        """La referencia excluye valores de líneas con un único valor: si
        todas las variantes son de un solo color, no aporta nombrarlo. Los
        valores de ``ProductAttributeValue`` no llevan ``is_distinguishing``
        (getattr con default True), así que con un valor SÍ se distingue —
        se verifica el caso donde SÍ aparece en el nombre."""
        color = ProductAttribute.objects.create(name='Color')
        rojo = ProductAttributeValue.objects.create(attribute=color, name='Rojo')
        tmpl = ProductTemplate.objects.create(name='Eleke')
        line = ProductTemplateAttributeLine.objects.create(
            product_tmpl=tmpl, attribute=color)
        line.values.set([rojo])
        ptav = ProductTemplateAttributeValue.objects.create(
            line=line, attribute_value=rojo)
        variante = ProductProduct.objects.create(product_tmpl=tmpl)
        variante.product_template_attribute_values.set([ptav])
        assert variante.display_name == 'Eleke (Rojo)'

    def test_clean_permite_combo_con_variante(self):
        """H-API-190: un combo SÍ puede tener variante (la línea de venta
        apunta a product.product); lo que se prohíbe es tener atributos,
        y esa regla vive en ProductTemplate, no aquí."""
        tmpl = ProductTemplate.objects.create(
            name='Menú', type=TYPE_COMBO)
        variante = ProductProduct.objects.create(product_tmpl=tmpl)
        variante.clean()  # no debe levantar


class TestGetImportTemplates:
    """El lado proveedor del contrato de ``base_import`` en ``product``.

    Hasta ``api@<este pase>`` el metodo se declinaba con una razon medida
    sobre ``src/`` — una raiz que no puede contener el simbolo, porque los
    addons viven en ``addons/``. Estos casos fijan la forma que la
    referencia declara (``odoo19c: addons/product/models/product_supplierinfo.py:95-99``)
    para que un cambio de etiqueta o de ruta salga en rojo y no en prosa.
    """

    def test_returns_one_template_entry(self):
        assert len(ProductSupplierinfo.get_import_templates()) == 1

    def test_the_entry_carries_the_reference_label_and_path(self):
        entrada = ProductSupplierinfo.get_import_templates()[0]
        assert entrada['label'] == 'Import Template for Vendor Pricelists'
        assert entrada['template'] == '/product/static/xls/product_supplierinfo.xls'

    def test_the_shape_matches_the_two_sibling_providers(self):
        """Las tres implementaciones del arbol declaran las MISMAS claves.

        Es lo que hace del simbolo un contrato y no tres metodos con el
        mismo nombre: ``base_import`` lee ``label`` y ``template`` sin
        saber de que modelo vienen.
        """
        claves = {
            frozenset(proveedor.get_import_templates()[0])
            for proveedor in (ProductSupplierinfo, CrmLead, StockQuant)
        }
        assert claves == {frozenset({'label', 'template'})}


@pytest.mark.django_db
class TestSelectSeller:
    """La cadena ``_prepare_sellers`` → ``_get_filtered_sellers`` →
    ``_select_seller`` (``odoo19c: addons/product/models/product_product.py:1016-1071``).

    Cada caso exige que el resultado **discrimine** entre dos filas: un
    ``return sellers[:1]`` desnudo pasaría cualquier caso que sólo afirmara
    "devuelve algo".
    """

    def _tariff(self, tmpl, partner, **kwargs):
        return ProductSupplierinfo.objects.create(
            partner=partner, product_tmpl=tmpl, **kwargs)

    def _variant(self, name='Eleke'):
        tmpl = ProductTemplate.objects.create(name=name)
        return tmpl, ProductProduct.objects.create(product_tmpl=tmpl)

    def test_prepare_sellers_orders_by_the_reference_key(self):
        """``(sequence, -min_qty, price, id)`` — la secuencia manda, y a
        igual secuencia gana la cantidad mínima MAYOR (el ``-min_qty``)."""
        tmpl, variant = self._variant()
        supplier = ResPartner.objects.create(name='Proveedor')
        late = self._tariff(tmpl, supplier, sequence=9, price=Decimal('1.00'))
        early_small = self._tariff(
            tmpl, supplier, sequence=1, min_qty=1, price=Decimal('5.00'))
        early_large = self._tariff(
            tmpl, supplier, sequence=1, min_qty=50, price=Decimal('5.00'))
        assert variant._prepare_sellers() == [
            early_large, early_small, late]

    def test_prepare_sellers_drops_a_tariff_of_another_variant(self):
        """Delega en ``_get_filtered_supplier``: la fila específica de otra
        variante no entra, la de plantilla sí."""
        tmpl, variant = self._variant()
        other = ProductProduct.objects.create(product_tmpl=tmpl)
        supplier = ResPartner.objects.create(name='Proveedor')
        from_template = self._tariff(tmpl, supplier)
        self._tariff(tmpl, supplier, product=other)
        assert variant._prepare_sellers() == [from_template]

    def test_filtered_sellers_drops_an_expired_tariff(self):
        tmpl, variant = self._variant()
        supplier = ResPartner.objects.create(name='Proveedor')
        in_force = self._tariff(tmpl, supplier, price=Decimal('9.00'))
        self._tariff(tmpl, supplier, price=Decimal('1.00'),
                     date_end=date(2020, 1, 1))
        assert variant._get_filtered_sellers() == [in_force]

    def test_filtered_sellers_drops_a_tariff_not_yet_in_force(self):
        tmpl, variant = self._variant()
        supplier = ResPartner.objects.create(name='Proveedor')
        in_force = self._tariff(tmpl, supplier, price=Decimal('9.00'))
        self._tariff(tmpl, supplier, price=Decimal('1.00'),
                     date_start=date(2999, 1, 1))
        assert variant._get_filtered_sellers() == [in_force]

    def test_filtered_sellers_requires_the_minimum_quantity(self):
        """El mismo conjunto da resultados distintos según la cantidad — es
        lo que distingue el filtro de un paso a través."""
        tmpl, variant = self._variant()
        supplier = ResPartner.objects.create(name='Proveedor')
        single_unit = self._tariff(tmpl, supplier, min_qty=1, price=Decimal('9.00'))
        bulk = self._tariff(tmpl, supplier, min_qty=100, price=Decimal('4.00'))
        assert variant._get_filtered_sellers(quantity=5) == [single_unit]
        assert set(variant._get_filtered_sellers(quantity=100)) == {
            single_unit, bulk}

    def test_filtered_sellers_accepts_the_parent_partner_tariff(self):
        """Una tarifa firmada con la matriz sirve a la sucursal
        (``seller.partner_id not in [partner_id, partner_id.parent_id]``)."""
        tmpl, variant = self._variant()
        parent_company = ResPartner.objects.create(name='Matriz')
        branch = ResPartner.objects.create(name='Sucursal', parent=parent_company)
        unrelated = ResPartner.objects.create(name='Ajena')
        from_parent = self._tariff(tmpl, parent_company, price=Decimal('7.00'))
        self._tariff(tmpl, unrelated, price=Decimal('1.00'))
        assert variant._get_filtered_sellers(partner_id=branch) == [from_parent]

    def test_select_seller_cuts_by_supplier_before_comparing_price(self):
        """**El caso que discrimina.** El segundo proveedor es más barato y
        NO gana: la fuente conserva sólo las filas del primero
        (``if not res or res.partner_id == seller.partner_id``). Una
        implementación que ordenara todo por precio devolvería la barata."""
        tmpl, variant = self._variant()
        preferred = ResPartner.objects.create(name='Preferido')
        cheap_partner = ResPartner.objects.create(name='Barato')
        expensive_from_preferred = self._tariff(
            tmpl, preferred, sequence=1, price=Decimal('50.00'))
        self._tariff(tmpl, cheap_partner, sequence=2, price=Decimal('1.00'))
        assert variant._select_seller() == [expensive_from_preferred]

    def test_select_seller_takes_the_cheapest_within_that_supplier(self):
        tmpl, variant = self._variant()
        supplier = ResPartner.objects.create(name='Proveedor')
        self._tariff(tmpl, supplier, sequence=1, price=Decimal('50.00'))
        cheaper = self._tariff(tmpl, supplier, sequence=1, price=Decimal('8.00'))
        assert variant._select_seller() == [cheaper]

    def test_select_seller_honours_the_discount(self):
        """Ordena por ``price_discounted``, no por ``price``: la de precio
        nominal mayor gana si su descuento la deja por debajo."""
        tmpl, variant = self._variant()
        supplier = ResPartner.objects.create(name='Proveedor')
        self._tariff(tmpl, supplier, sequence=1, price=Decimal('10.00'))
        discounted = self._tariff(
            tmpl, supplier, sequence=1, price=Decimal('12.00'),
            discount=Decimal('50.00'))
        assert variant._select_seller() == [discounted]

    def test_ordered_by_takes_primacy_over_the_price(self):
        """``ordered_by`` antepone otro campo; el precio pasa a desempatar."""
        tmpl, variant = self._variant()
        supplier = ResPartner.objects.create(name='Proveedor')
        low_min_qty = self._tariff(
            tmpl, supplier, sequence=1, min_qty=0, price=Decimal('50.00'))
        self._tariff(
            tmpl, supplier, sequence=1, min_qty=1, price=Decimal('8.00'))
        # Con ``quantity=10`` las dos superan su mínimo: el filtro deja de
        # decidir y lo que se mide es el orden, que es el objeto del caso.
        assert variant._select_seller(quantity=10) != [low_min_qty]
        assert variant._select_seller(quantity=10, ordered_by='min_qty') == [low_min_qty]

    def test_select_seller_returns_empty_when_nothing_matches(self):
        tmpl, variant = self._variant()
        assert variant._select_seller() == []
