"""``Many2many(ondelete='restrict')``: la FK de ``column2`` de la intermedia.

≙ ``test_10_ondelete_many2many`` y ``test_11_ondelete_many2many``
(``odoo19c: odoo/addons/test_orm/tests/test_fields.py:3350-3376``) sobre
``test_orm.model_a``/``model_b``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
many2many-column2-ondelete.md``.

**Divergencia de mecanismo declarada:** la fuente espera
``psycopg2.IntegrityError`` (``ON DELETE RESTRICT`` en la base); aquí el
``restrict`` queda en Python y levanta ``ProtectedError`` antes del SQL,
como el resto de ``restrict`` del puerto.
"""
import pytest
from django.db.models.deletion import ProtectedError

from addons.product.models import (
    ProductAttribute, ProductAttributeValue, ProductProduct, ProductTemplate,
    ProductTemplateAttributeLine, ProductTemplateAttributeValue)
from orm.commands import Command
from orm.environments import Environment
from orm.utils import SUPERUSER_ID

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def test_10_ondelete_many2many(env):
    """A no se borra mientras la relación lo use (el ``restrict`` del
    segundo extremo, ``model_b.a_restricted_a_ids``)."""
    record_a = env['test_orm.model_a'].create({'name': 'a'})
    record_b = env['test_orm.model_b'].create({'name': 'b'})
    record_a.write({'a_restricted_b_ids': [Command.set(record_b.ids)]})
    with pytest.raises(ProtectedError):
        record_a.unlink()
    # B sigue en cascade.
    record_b.unlink()
    assert not record_b.exists()


def test_11_ondelete_many2many(env):
    """B no se borra mientras la relación lo use (el ``restrict`` del
    primer extremo, ``model_a.b_restricted_b_ids``)."""
    record_a = env['test_orm.model_a'].create({'name': 'a'})
    record_b = env['test_orm.model_b'].create({'name': 'b'})
    record_a.write({'b_restricted_b_ids': [Command.set(record_b.ids)]})
    with pytest.raises(ProtectedError):
        record_b.unlink()
    # A sigue en cascade.
    record_a.unlink()
    assert not record_a.exists()


def test_a_value_used_by_a_variant_is_not_deleted():
    """``product_template_attribute_value_ids`` es ``restrict``
    (``odoo19c: addons/product/models/product_product.py:49``)."""
    # Los modelos del producto aplican la ACL: corre como superusuario,
    # el ``TransactionCase`` de la fuente.
    with Environment(None, SUPERUSER_ID, {}):
        attribute = ProductAttribute.objects.create(name='Color m2mo')
        red = ProductAttributeValue.objects.create(attribute_id=attribute,
                                                   name='Rojo m2mo')
        template = ProductTemplate.objects.create(name='Taza m2mo')
        line = ProductTemplateAttributeLine.objects.create(
            product_tmpl_id=template, attribute_id=attribute)
        ptav = ProductTemplateAttributeValue.objects.create(
            attribute_line_id=line, product_attribute_value_id=red)
        variant = ProductProduct.objects.create(product_tmpl_id=template)
        variant.write({
            'product_template_attribute_value_ids': [Command.link(ptav.id)],
        })
        with pytest.raises(ProtectedError):
            ptav.delete()
