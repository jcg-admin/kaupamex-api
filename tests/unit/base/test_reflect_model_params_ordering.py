"""El ``order`` reflejado de un modelo es texto aunque ``Meta.ordering``
lleve expresiones.

``_reflect_model_params`` guarda ``model._order`` (``odoo19c:
odoo/addons/base/models/ir_model.py:430``), que en la referencia es siempre
una cadena. Un modelo sin ``_order`` cae aquí a ``Meta.ordering``, y Django
admite en ella expresiones (``models.TranslatedValue('name').asc()``): cada
término se traduce a su texto, ``nombre`` o ``nombre desc``. Diseño:
``designs/module-install-cycle.md``, L2.
"""
from django.apps import apps
from django.db.models.expressions import OrderBy

from addons.base.models.ir_model import IrModel


def test_an_expression_ordering_is_reflected_as_text():
    removal = apps.get_model('stock', 'ProductRemoval')
    assert not getattr(removal, '_order', None)
    assert IrModel._reflect_model_params(removal)['order'] == 'name'


def test_a_descending_expression_keeps_its_direction(monkeypatch):
    removal = apps.get_model('stock', 'ProductRemoval')
    term = removal._meta.ordering[0]
    monkeypatch.setattr(removal._meta, 'ordering',
                        [OrderBy(term.expression, descending=True)])
    assert IrModel._reflect_model_params(removal)['order'] == 'name desc'
