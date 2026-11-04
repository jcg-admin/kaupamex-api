"""Tests — ``product.attribute.custom.value``, el texto libre de una opción.

Cubre el modelo que ``api@<este commit>`` porta desde
``odoo19c: product/models/product_attribute_custom_value.py``. Ningún caso
previo lo tocaba: el modelo no existía.

Lo que se fija aquí:

1. El modelo guarda lo que el comprador escribió, atado al valor de atributo
   que admite texto libre.
2. ``name`` es un campo **sin columna** — ``fields.NonStored``, el equivalente
   construido del ``store=False`` de la fuente. Su cuerpo antepone el nombre
   del valor de atributo, igual que ``_compute_name`` de la referencia.
3. El ``on_delete=PROTECT`` porta el ``ondelete='restrict'`` de la fuente: el
   motor rehúsa borrar un valor de atributo que alguien personalizó.

*Métrica:* los 3 campos y el método de cómputo que la fuente declara.
*Ciega a:* lo que ``sale`` le cuelga por ``_inherit``
(``sale_order_line_id`` y su restricción de unicidad), que vive en
``addons/sale/models/product_product.py`` y se porta con esa extensión.
"""

import pytest
from django.db.models import ProtectedError

from addons.product.models import (
    ProductAttribute,
    ProductAttributeCustomValue,
    ProductAttributeValue,
    ProductTemplate,
    ProductTemplateAttributeLine,
    ProductTemplateAttributeValue,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def attribute_value():
    """Un valor de atributo por-producto — el destino de la FK."""
    attribute = ProductAttribute.objects.create(name='Grabado')
    value = ProductAttributeValue.objects.create(
        attribute=attribute, name='Personalizado', sequence=0
    )
    template = ProductTemplate.objects.create(name='Placa conmemorativa')
    line = ProductTemplateAttributeLine.objects.create(
        product_tmpl=template, attribute=attribute, sequence=10
    )
    line.values.set([value])
    return ProductTemplateAttributeValue.objects.create(
        line=line, attribute_value=value
    )


class TestWhatTheBuyerWroteIsStored:

    def test_the_custom_value_survives_the_reload(self, attribute_value):
        custom = ProductAttributeCustomValue.objects.create(
            custom_product_template_attribute_value_id=attribute_value,
            custom_value='Para Yemayá, 2026',
        )

        again = ProductAttributeCustomValue.objects.get(pk=custom.pk)
        assert again.custom_value == 'Para Yemayá, 2026'

    def test_an_empty_custom_value_is_allowed(self, attribute_value):
        """La fuente declara ``custom_value`` sin ``required``."""
        custom = ProductAttributeCustomValue.objects.create(
            custom_product_template_attribute_value_id=attribute_value
        )
        assert custom.custom_value == ''


class TestTheNameHasNoColumn:

    def test_the_name_prefixes_the_attribute_value(self, attribute_value):
        """≙ ``_compute_name`` (``odoo19c: :20-25``)."""
        custom = ProductAttributeCustomValue.objects.create(
            custom_product_template_attribute_value_id=attribute_value,
            custom_value='  Para Yemayá  ',
        )
        assert custom.name == f'{attribute_value}: Para Yemayá'

    def test_the_name_takes_no_column(self):
        """Es un campo del modelo, como en ``_fields`` de la fuente, pero sin
        columna."""
        concrete = {
            f.name for f in ProductAttributeCustomValue._meta.concrete_fields
        }
        assert 'name' not in concrete
        assert (
            'custom_value' in concrete
        ), 'control positivo: el vecino SÍ tiene columna'

    def test_the_name_cannot_be_filtered(self, attribute_value):
        """≙ ``Field.to_sql`` (``odoo19c: odoo/orm/fields.py:1215-1216``):
        un campo sin columna no se convierte a SQL."""
        with pytest.raises(ValueError, match='because it is not stored'):
            ProductAttributeCustomValue.objects.filter(name='x').exists()

    def test_what_gets_written_never_reaches_the_database(
        self, attribute_value
    ):
        """Lo asignado vive en la caché del entorno, no en la tabla.

        ≙ ``Field.write`` (``odoo19c: odoo/orm/fields.py:1501-1518``): escribir
        actualiza la caché del registro, que es por id, así que otra lectura
        del mismo registro en la misma transacción ve el valor. Lo que no
        existe es la columna donde guardarlo.
        """
        custom = ProductAttributeCustomValue.objects.create(
            custom_product_template_attribute_value_id=attribute_value,
            custom_value='original',
        )
        custom.name = 'inventado'
        custom.save()

        assert custom.name == 'inventado', 'vive en la caché'
        again = ProductAttributeCustomValue.objects.get(pk=custom.pk)
        assert again.name == 'inventado', 'la caché es por id'
        columns = {
            f.column for f in ProductAttributeCustomValue._meta.concrete_fields
        }
        assert 'name' not in columns, 'no vive en la tabla'


class TestTheAttributeValueIsProtected:

    def test_deleting_a_personalised_attribute_value_is_refused(
        self, attribute_value
    ):
        """≙ ``ondelete='restrict'`` (``odoo19c: :17``)."""
        ProductAttributeCustomValue.objects.create(
            custom_product_template_attribute_value_id=attribute_value,
            custom_value='Para Yemayá',
        )

        with pytest.raises(ProtectedError):
            attribute_value.delete()
