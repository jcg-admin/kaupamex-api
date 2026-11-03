"""Toda ruta de ``_rec_names_search`` compila sobre su modelo.

``_search_display_name`` (``api: src/orm/models.py``) emite una condición por
cada nombre de ``_rec_names_search``. Una ruta que no resuelve no falla al
importar ni al arrancar: falla en la primera búsqueda por nombre, con
``Invalid field``. Así quedaron ``res.partner`` (``ref`` sin declarar,
H-API-1126) y ``sale.order.line`` (``order__name``, la travesía de Django en
vez de la ruta con punto de la fuente, ``odoo19c: sale_order_line.py:16``).

Un ``_rec_names_search`` declarado como ``property`` (``sale.order``, como en
la fuente) depende del contexto: se mide con ``search_display_name``, que es
quien lo evalúa, con y sin la clave que cambia sus rutas.
"""

import pytest
from django.apps import apps

from orm.domains import Domain, to_q
from orm.environments import context_scope
from orm.models import search_display_name


def _declared_paths():
    for model in apps.get_models():
        names = getattr(model, '_rec_names_search', None)
        if isinstance(names, (list, tuple)):
            for path in names:
                yield pytest.param(model, path, id=f'{model._meta.label}:{path}')


def test_the_census_is_not_empty():
    """El control: sin modelos medidos, el caso parametrizado no pregunta nada."""
    assert len(list(_declared_paths())) >= 10


@pytest.mark.parametrize(('model', 'path'), list(_declared_paths()))
def test_each_path_compiles(model, path):
    to_q(Domain(path, 'ilike', 'x'), model)


def _property_models():
    return [model for model in apps.get_models()
            if isinstance(getattr(model, '_rec_names_search', None), property)]


def test_the_property_census_is_not_empty():
    assert _property_models()


@pytest.mark.parametrize('show_partner', [False, True])
def test_a_property_is_evaluated_and_compiles(show_partner):
    """``sale.order`` declara la propiedad; ``sale_show_partner_name`` añade
    ``partner.name`` (``odoo19c: sale_order.py:48-49``)."""
    for model in _property_models():
        with context_scope(sale_show_partner_name=show_partner):
            domain = search_display_name(model, 'ilike', 'x')
            to_q(domain, model)
