"""``BaseModel._fields`` contiene el ``One2many`` declarado.

En la fuente ``_fields`` es el mapa de TODO campo declarado, tenga columna o
no (``odoo19c: odoo/orm/models.py:368``). Aquí un
``fields.One2many(comodel, inverse)`` declarado no pasa por ``_meta``
(``orm/fields_relational.py``, ``contribute_to_class``), así que el registro
tiene que recogerlo aparte, como ya recoge los campos sin columna.
"""
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def test_fields_holds_a_declared_one2many(env):
    Discussion = env['test_orm.discussion']
    field = Discussion._fields['messages']
    assert field.type == 'one2many'
    assert field is vars(type(Discussion))['messages']
