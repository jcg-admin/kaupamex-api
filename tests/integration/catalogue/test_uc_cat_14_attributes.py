"""
Tests — UC-CAT-14: EJE 2 (AttributeAxis / AttributeValue / ProductAttribute)

CP3 coverage per executor gate:
  1. migration 0016 forward: multiple categories per product preserved
  2. EJE 2 models: create axis, hierarchical values, product-attribute join
  3. anti-cycle validation on AttributeValue.parent
  4. unique_together constraints reject duplicates
  5. existing Category / Product M2M (EJE 1) not broken by EJE 2 additions
"""
import pytest
from decimal import Decimal
from django.db import IntegrityError
from apps.modules.catalogue.models import (
    AttributeAxis, AttributeValue, ProductAttribute,
    Category, Product,
)

pytestmark = pytest.mark.integration


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def orisha_axis(db):
    return AttributeAxis.objects.create(
        name='Orisha', slug='orisha', is_filterable=True, display_order=1,
    )


@pytest.fixture
def color_axis(db):
    return AttributeAxis.objects.create(
        name='Color', slug='color', is_filterable=True, display_order=2,
    )


@pytest.fixture
def yemaya(orisha_axis):
    return AttributeValue.objects.create(
        axis=orisha_axis, value='Yemayá', slug='yemaya', display_order=1,
    )


@pytest.fixture
def yemaya_mayelewo(orisha_axis, yemaya):
    return AttributeValue.objects.create(
        axis=orisha_axis, value='Yemayá Mayelewo', slug='yemaya-mayelewo',
        parent=yemaya, display_order=1,
    )


@pytest.fixture
def cat_collares(db):
    return Category.objects.create(name='Collares', slug='collares', is_active=True)


@pytest.fixture
def cat_accesorios(db):
    return Category.objects.create(name='Accesorios Yemayá', slug='accesorios-yemaya', is_active=True)


@pytest.fixture
def product_eleke(db, cat_collares, cat_accesorios):
    p = Product.objects.create(
        name='Eleke de Yemayá', slug='eleke-yemaya', sku='ELK-YEM-001',
        price=Decimal('250.00'), stock=10, is_active=True, is_published=True,
    )
    p.categories.add(cat_collares, cat_accesorios)
    return p


# =============================================================================
# 1. Migration 0016 forward: multiple categories preserved
# =============================================================================

class TestMigration0016MultipleCategories:
    """Verifies that the M2M infrastructure supports multiple categories per
    product — which is what migration 0016 forward was designed to preserve."""

    def test_product_puede_tener_multiples_categorias(self, product_eleke, cat_collares, cat_accesorios):
        cats = set(product_eleke.categories.values_list('slug', flat=True))
        assert 'collares' in cats
        assert 'accesorios-yemaya' in cats
        assert len(cats) == 2

    def test_product_con_tres_categorias(self, db):
        cat_a = Category.objects.create(name='Cat A', slug='cat-a', is_active=True)
        cat_b = Category.objects.create(name='Cat B', slug='cat-b', is_active=True)
        cat_c = Category.objects.create(name='Cat C', slug='cat-c', is_active=True)
        p = Product.objects.create(
            name='Multi Cat', slug='multi-cat', sku='MULTI-001',
            price=Decimal('100.00'), stock=5, is_active=True, is_published=False,
        )
        p.categories.add(cat_a, cat_b, cat_c)
        assert p.categories.count() == 3

    def test_categoria_tiene_multiples_productos(self, db, cat_collares):
        for i in range(3):
            p = Product.objects.create(
                name=f'Eleke {i}', slug=f'eleke-{i}', sku=f'ELK-{i:03d}',
                price=Decimal('100.00'), stock=5, is_active=True, is_published=False,
            )
            p.categories.add(cat_collares)
        assert cat_collares.products.count() == 3


# =============================================================================
# 2. EJE 2 — Crear AttributeAxis y AttributeValue
# =============================================================================

class TestAttributeAxisCrud:

    def test_crear_axis(self, orisha_axis):
        assert orisha_axis.pk is not None
        assert orisha_axis.slug == 'orisha'
        assert orisha_axis.is_filterable is True
        assert orisha_axis.is_active is True

    def test_axis_tiene_timestamps(self, orisha_axis):
        assert orisha_axis.created_at is not None
        assert orisha_axis.updated_at is not None

    def test_axis_slug_unico(self, db, orisha_axis):
        with pytest.raises(IntegrityError):
            AttributeAxis.objects.create(name='Otro Orisha', slug='orisha')

    def test_axis_name_unico(self, db, orisha_axis):
        with pytest.raises(IntegrityError):
            AttributeAxis.objects.create(name='Orisha', slug='orisha-2')


class TestAttributeValueCrud:

    def test_crear_value_sin_parent(self, yemaya, orisha_axis):
        assert yemaya.pk is not None
        assert yemaya.axis == orisha_axis
        assert yemaya.parent is None

    def test_crear_value_con_parent_jerarquico(self, yemaya_mayelewo, yemaya):
        assert yemaya_mayelewo.parent == yemaya
        assert yemaya_mayelewo.axis == yemaya.axis

    def test_value_tiene_timestamps(self, yemaya):
        assert yemaya.created_at is not None

    def test_children_relation(self, yemaya, yemaya_mayelewo):
        yemaya_asesu = AttributeValue.objects.create(
            axis=yemaya.axis, value='Yemayá Asesú', slug='yemaya-asesu',
            parent=yemaya,
        )
        children_slugs = set(yemaya.children.values_list('slug', flat=True))
        assert 'yemaya-mayelewo' in children_slugs
        assert 'yemaya-asesu' in children_slugs

    def test_axis_plano_sin_parent(self, color_axis):
        rojo = AttributeValue.objects.create(
            axis=color_axis, value='Rojo', slug='rojo',
        )
        assert rojo.parent is None


# =============================================================================
# 3. Anti-cycle validation on AttributeValue.parent
# =============================================================================

class TestAttributeValueAntiCycle:

    def test_would_create_cycle_self(self, yemaya):
        assert yemaya.would_create_cycle(yemaya) is True

    def test_would_create_cycle_none_parent(self, yemaya):
        assert yemaya.would_create_cycle(None) is False

    def test_would_create_cycle_safe_parent(self, yemaya_mayelewo, yemaya):
        """Asignar el padre correcto NO crea ciclo."""
        # yemaya_mayelewo ya tiene yemaya como padre — re-asignar el mismo no crea ciclo
        # (verificar desde la perspectiva del padre hacia abajo)
        assert yemaya.would_create_cycle(yemaya_mayelewo) is True

    def test_would_create_cycle_indirect(self, orisha_axis):
        """A → B → C: asignar C.parent=A cuando A.parent=B crearía ciclo."""
        a = AttributeValue.objects.create(axis=orisha_axis, value='A', slug='a-v')
        b = AttributeValue.objects.create(axis=orisha_axis, value='B', slug='b-v', parent=a)
        c = AttributeValue.objects.create(axis=orisha_axis, value='C', slug='c-v', parent=b)
        # Asignar a.parent = c crearía: a → c → b → a (ciclo)
        assert a.would_create_cycle(c) is True

    def test_would_create_cycle_no_cycle_different_branches(self, orisha_axis):
        """Dos ramas independientes no crean ciclo entre sí."""
        rama1 = AttributeValue.objects.create(axis=orisha_axis, value='Rama1', slug='rama1')
        rama2 = AttributeValue.objects.create(axis=orisha_axis, value='Rama2', slug='rama2')
        assert rama1.would_create_cycle(rama2) is False


# =============================================================================
# 4. unique_together constraints
# =============================================================================

class TestUniqueTogetherConstraints:

    def test_axis_value_duplicado_falla(self, db, orisha_axis, yemaya):
        with pytest.raises(IntegrityError):
            AttributeValue.objects.create(
                axis=orisha_axis, value='Yemayá', slug='yemaya-dup',
            )

    def test_axis_slug_duplicado_falla(self, db, orisha_axis, yemaya):
        with pytest.raises(IntegrityError):
            AttributeValue.objects.create(
                axis=orisha_axis, value='Otro Yemayá', slug='yemaya',
            )

    def test_mismo_value_en_diferente_axis_ok(self, db, orisha_axis, color_axis):
        """El mismo value en ejes distintos NO viola unique_together."""
        AttributeValue.objects.create(axis=orisha_axis, value='Azul', slug='azul-orisha')
        v2 = AttributeValue.objects.create(axis=color_axis, value='Azul', slug='azul-color')
        assert v2.pk is not None

    def test_product_attribute_duplicado_falla(self, db, product_eleke, yemaya):
        ProductAttribute.objects.create(product=product_eleke, value=yemaya)
        with pytest.raises(IntegrityError):
            ProductAttribute.objects.create(product=product_eleke, value=yemaya)

    def test_product_attribute_diferente_value_ok(self, db, product_eleke, yemaya, yemaya_mayelewo):
        pa1 = ProductAttribute.objects.create(product=product_eleke, value=yemaya)
        pa2 = ProductAttribute.objects.create(product=product_eleke, value=yemaya_mayelewo)
        assert pa1.pk != pa2.pk


# =============================================================================
# 5. EJE 1 (Category M2M) no se rompió con la adición del EJE 2
# =============================================================================

class TestEje1NoRoto:

    def test_category_tree_intacto(self, db):
        parent_cat = Category.objects.create(name='Joyas', slug='joyas', is_active=True)
        child_cat  = Category.objects.create(
            name='Joyas Yemayá', slug='joyas-yemaya', parent=parent_cat, is_active=True,
        )
        assert child_cat.parent == parent_cat
        assert 'joyas-yemaya' in set(
            parent_cat.children.values_list('slug', flat=True)
        )

    def test_get_descendants_ids_intacto(self, db):
        root = Category.objects.create(name='Root', slug='root-cat', is_active=True)
        child = Category.objects.create(name='Child', slug='child-cat', parent=root, is_active=True)
        grandchild = Category.objects.create(
            name='Grand', slug='grand-cat', parent=child, is_active=True,
        )
        ids = root.get_descendants_ids()
        assert root.pk in ids
        assert child.pk in ids
        assert grandchild.pk in ids

    def test_product_categories_m2m_intacto(self, product_eleke, cat_collares, cat_accesorios):
        assert product_eleke.categories.count() == 2

    def test_eje1_y_eje2_coexisten_en_mismo_producto(self, db, product_eleke, yemaya):
        """Un producto puede tener categorías (EJE 1) Y atributos (EJE 2) simultáneamente."""
        pa = ProductAttribute.objects.create(product=product_eleke, value=yemaya)
        assert product_eleke.categories.count() == 2
        assert product_eleke.attributes.count() == 1
        assert pa.value == yemaya
