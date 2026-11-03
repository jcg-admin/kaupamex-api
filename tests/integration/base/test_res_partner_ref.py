"""``res.partner.ref`` — ≙ ``odoo19c: odoo/addons/base/models/res_partner.py:218``.

La fuente declara ``ref = fields.Char(string='Reference', index=True)`` y lo
lista en ``_rec_names_search`` (``:205``). Aquí ``_rec_names_search`` ya lo
nombraba sin que el campo existiera, así que toda búsqueda por
``display_name`` de un partner compilaba una condición sobre un campo
ausente.
"""

import pytest

from orm.environments import Environment
from orm.utils import SUPERUSER_ID
from tests.conftest import matching_by_display_name

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


@pytest.fixture
def env(db):
    environment = Environment(None, SUPERUSER_ID, {})
    with environment:
        yield environment


def test_the_reference_is_a_stored_indexed_char(env):
    field = env['res.partner']._fields['ref']
    assert field.get_internal_type() == 'CharField'
    assert field.index is True


def test_searching_by_display_name_matches_the_reference(env):
    model = env['res.partner']
    partner = model.objects.create(name='Acme', ref='CUST-042')
    model.objects.create(name='Otro')
    found = matching_by_display_name(model, 'ilike', 'CUST-042')
    assert list(found) == [partner]
