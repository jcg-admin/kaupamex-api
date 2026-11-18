"""``uom.uom`` sobre ``BaseModel``, con los cómputos de la fuente.

≙ ``odoo19c: addons/uom/models/uom_uom.py:35-75``: ``factor`` es un cómputo
recursivo almacenado que el ORM recalcula como superusuario
(``compute_sudo``, ``odoo19c: odoo/orm/fields.py:448``), ``sequence`` un
cómputo almacenado editable, ``rounding`` un cómputo y ``related_uom_ids`` un
``One2many``. Diseño en ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/basemodel-adoption-uom.md``.
"""
import pytest

from addons.uom.models import Uom
from orm.environments import Environment, sudo
from orm.models import BaseModel

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def chain():
    gram = Uom.objects.create(name='g', relative_factor=1.0)
    kilo = Uom.objects.create(name='kg', relative_factor=1000,
                              relative_uom_id=gram)
    ton = Uom.objects.create(name='t', relative_factor=1000,
                             relative_uom_id=kilo)
    return gram, kilo, ton


def test_uom_is_a_basemodel():
    assert issubclass(Uom, BaseModel)


def test_the_children_are_a_declared_one2many(chain):
    gram, kilo, ton = chain
    with sudo():
        assert list(gram.related_uom_ids) == [kilo]


def test_a_parent_factor_reaches_the_grandchildren(chain):
    """El recálculo baja dos niveles sin que el usuario lea ``uom.uom``."""
    gram, kilo, ton = chain
    with Environment('default', None, {}) as env:
        record = env['uom.uom'].sudo().browse(gram.pk)
        record.relative_factor = 1.0
        kilo_record = env['uom.uom'].sudo().browse(kilo.pk)
        kilo_record.relative_factor = 10
        env.flush_all()
    ton.refresh_from_db()
    assert ton.factor == pytest.approx(10 * 1000)


def test_the_sequence_is_derived_once(chain):
    gram, kilo, ton = chain
    assert kilo.sequence == 1000
    kilo.sequence = 7
    kilo.save()
    kilo.relative_factor = 2
    kilo.save()
    kilo.refresh_from_db()
    assert kilo.sequence == 7
