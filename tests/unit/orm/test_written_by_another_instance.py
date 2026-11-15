"""Dos instancias de la misma fila leen lo último escrito.

≙ ``Field.__get__`` (``odoo19c: odoo/orm/fields.py:1668-1673``): un registro
no guarda valores y la lectura va a ``env.cache``. Aquí la instancia de Django
guarda su copia en ``__dict__``; ``transaction.field_written`` dice cuándo esa
copia quedó atrás.
"""
import pytest

from orm.registry import MODELS_BY_NAME
from orm.environments import sudo

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


def _category(**values):
    [category] = MODELS_BY_NAME['res.partner.category'].create(
        [{'name': 'Fila compartida', **values}])
    return category


def test_a_write_through_another_instance_reaches_the_first():
    partner = _category()
    assert partner.name == 'Fila compartida'
    other = partner.browse(partner.id)
    assert other is not partner
    other.write({'name': 'Escrito por otra'})
    assert partner.name == 'Escrito por otra'


def test_writing_back_the_stale_value_is_not_a_no_op():
    partner = _category()
    assert partner.name == 'Fila compartida'
    partner.browse(partner.id).write({'name': 'Intermedio'})
    partner.write({'name': 'Fila compartida'})
    model = MODELS_BY_NAME['res.partner.category']
    assert model.objects.filter(pk=partner.id).values_list(
        'name', flat=True)[0] == 'Fila compartida'


def test_a_many2one_written_elsewhere_was_already_coherent():
    """Control: el descriptor de ``Many2one`` lee de la caché; este caso
    pasa con o sin el refresco, y así queda medido."""
    first = _category(name='Padre A wbai')
    second = _category(name='Padre B wbai')
    child = _category(name='Hija wbai', parent=first.id)
    assert child.parent.id == first.id
    child.browse(child.id).write({'parent': second.id})
    assert child.parent.id == second.id
