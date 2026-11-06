"""Las tres propiedades de método marcado sobre ``BaseModel``.

La fuente declara ``_constraint_methods``, ``_ondelete_methods`` y
``_onchange_methods`` como propiedades de ``BaseModel``
(``odoo19c: odoo/orm/models.py:519-593``): las dos primeras devuelven una
lista y la tercera un mapa de nombre de campo a métodos. El puerto ya tiene
los tres colectores —con su consumidor— en ``orm.registry``. Aquí se mide
que cada propiedad responda con lo que da su colector para la clase del
recordset.

La propiedad se invoca por su ``fget`` sobre dos dobles —uno con los tres
marcadores y uno sin ninguno—, como hace ``test_marked_method_collectors.py``,
porque ningún modelo concreto de este árbol declara hoy ``@api.constrains``
ni ``@api.ondelete``: con modelos reales la igualdad se cumpliría en vacío.
El único con ``@api.onchange``, ``test_orm.discussion``, entra también.

*Métrica:* igualdad entre la propiedad y el colector, y la forma del valor.
*Ciega a:* qué métodos marca cada addon, que mide
``test_marked_method_collectors.py``; y la memoización en la clase de la
fuente, que aquí hace el colector.
"""
import pytest
from django.apps import apps

from orm import registry
from orm.decorators import constrains, ondelete, onchange
from orm.models import BaseModel

PROPERTIES = (
    ('_constraint_methods', registry.constraint_methods, list),
    ('_ondelete_methods', registry.ondelete_methods, list),
    ('_onchange_methods', registry.onchange_methods, dict),
)
IDS = [entry[0] for entry in PROPERTIES]


class _Marked:
    """Un doble con los tres marcadores."""

    _name = 'probe.marked'

    @constrains('alpha')
    def _check_alpha(self):
        return 'alpha'

    @ondelete(at_uninstall=False)
    def _unlink_if_alpha(self):
        return 'unlink'

    @onchange('alpha')
    def _onchange_alpha(self):
        return 'onchange'


class _Bare:
    """El control negativo: ningún método marcado."""

    _name = 'probe.bare'


def _expected(collector, shape, cls):
    collected = collector(cls)
    return dict(collected) if shape is dict else list(collected)


@pytest.mark.parametrize('name,collector,shape', PROPERTIES, ids=IDS)
def test_the_property_answers_with_its_collector(name, collector, shape):
    for double in (_Marked(), _Bare()):
        value = getattr(BaseModel, name).fget(double)
        assert isinstance(value, shape), (double, name)
        assert value == _expected(collector, shape, type(double))


@pytest.mark.parametrize('name,collector,shape', PROPERTIES, ids=IDS)
def test_the_marked_double_is_not_empty(name, collector, shape):
    assert getattr(BaseModel, name).fget(_Marked())
    assert not getattr(BaseModel, name).fget(_Bare())


@pytest.mark.django_db
def test_a_real_model_with_onchange_methods():
    model = next(model for model in apps.get_models()
                 if getattr(model, '_name', None) == 'test_orm.discussion')
    value = model.browse()._onchange_methods
    assert value
    assert value == dict(registry.onchange_methods(model))
