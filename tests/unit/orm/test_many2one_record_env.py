"""El corecord de un ``Many2one`` se construye en el entorno del registro.

≙ ``Many2one.convert_to_record`` (``odoo19c: odoo/orm/
fields_relational.py:354-358``): ``record.pool[comodel](record.env, ...)``.
El valor leído hereda el contexto, el usuario y el ``su`` de quien lo lee.
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-pricelist-cluster.md``.

*Métrica:* el contexto y el ``su`` del corecord leído desde un registro con
otro entorno, y el recordset vacío de un ``Many2one`` sin valor.
*Ciega a:* el ``Many2one`` hacia un comodelo de Django, que no tiene entorno.
"""
import pytest

from orm.environments import env, sudo

pytestmark = pytest.mark.django_db


@pytest.fixture
def variant():
    # Se crea con privilegios y se devuelve fuera de ``sudo()``: el entorno
    # ambiental de la prueba no es superusuario, así que el ``su`` del
    # corecord sólo puede venir del registro que lo lee.
    with sudo():
        [template] = env()['product.template'].create(
            [{'name': 'M2O entorno'}])
        ids = template.product_variant_ids[:1].ids
    return env()['product.product'].browse(ids)


def test_the_corecord_inherits_the_context(variant):
    template = variant.sudo().with_context(m2o_probe=7).product_tmpl_id
    assert template.env.context.get('m2o_probe') == 7


def test_the_corecord_inherits_superuser_mode(variant):
    assert variant.sudo().product_tmpl_id.env.su


def test_an_empty_many2one_lives_in_the_record_env(variant):
    with sudo():
        [rule] = env()['product.pricelist.item'].create(
            [{'pricelist_id': False}])
    empty = rule.sudo().with_context(m2o_probe=8).pricelist_id
    assert not empty
    assert empty.env.context.get('m2o_probe') == 8
