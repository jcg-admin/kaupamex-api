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
from django.db.models import F
from django.db.models.expressions import OrderBy

from addons.base.models.ir_model import IrModel


# Un modelo de Django sin ``_order``: ``ReturnItem``, hijo de
# ``return.request`` y propio del L0, no tiene ``_name`` ni contraparte en la
# fuente. Los sujetos anteriores, ``product.removal`` y ``stock.route``,
# declaran el ``_order`` de la fuente desde las unidades U1 y U6a de ``stock``.
SUBJECT = ('stock', 'ReturnItem')


def test_an_expression_ordering_is_reflected_as_text(monkeypatch):
    route = apps.get_model(*SUBJECT)
    assert not getattr(route, '_order', None)
    monkeypatch.setattr(route._meta, 'ordering', [F('name').asc()])
    assert IrModel._reflect_model_params(route)['order'] == 'name'


def test_a_descending_expression_keeps_its_direction(monkeypatch):
    route = apps.get_model(*SUBJECT)
    monkeypatch.setattr(route._meta, 'ordering',
                        [OrderBy(F('name'), descending=True)])
    assert IrModel._reflect_model_params(route)['order'] == 'name desc'
