"""Escribir un ``Many2many`` calculado descarta su recálculo pendiente.

≙ ``_RelationalMulti.write`` (``odoo19c: odoo/orm/fields_relational.py:
737-740``): *"discard recomputation of self on records"*, que
``BaseModel.write`` alcanza con ``field.write(self, value)``
(``odoo/orm/models.py:4469``). Diseño: ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/
write-many2many-discards-recompute.md``.

*Métrica:* el valor del campo tras escribirlo y volcar.
*Ciega a:* los ``One2many``, que escriben por otra rama.
"""
import pytest

from orm.environments import env, sudo

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _superuser():
    with sudo():
        yield


def test_a_written_computed_many2many_survives_the_flush():
    tags = env()['test_orm.multi.tag']
    [computed_tag, written_tag] = tags.create(
        [{'name': 'auto'}, {'name': 'manual'}])
    [record] = env()['test_orm.compute.onchange'].create([{'foo': 'auto'}])
    record.write({'tag_ids': [(6, 0, [written_tag.id])]})
    env().flush_all()
    record.invalidate_recordset()
    assert record.tag_ids == written_tag
    assert computed_tag not in record.tag_ids


def test_a_dirty_computed_value_does_not_overwrite_the_written_one():
    """Leer el campo ejecuta su cómputo perezoso, que deja en caché un valor
    sucio; el comando escrito luego va directo a la tabla intermedia, y el
    volcado siguiente no puede devolver el valor calculado."""
    tags = env()['test_orm.multi.tag']
    [computed_tag, written_tag] = tags.create(
        [{'name': 'auto2'}, {'name': 'manual2'}])
    [record] = env()['test_orm.compute.onchange'].create([{'foo': 'auto2'}])
    assert record.tag_ids == computed_tag
    record.write({'tag_ids': [(6, 0, [written_tag.id])]})
    env().flush_all()
    env().invalidate_all(flush=False)
    assert record.tag_ids == written_tag
