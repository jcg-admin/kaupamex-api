"""La guarda de tamaño de ``FieldDescriptor.__get__`` — TASK-API-0401.

``odoo19c: odoo/orm/fields.py:1641-1661`` mide ``len(record._ids)`` antes
de tocar la caché: con dos o más ids deja que ``ensure_one`` levante; con
cero devuelve el valor nulo del campo; con uno sigue hacia la caché. El
puerto la conserva en el bloque ``own_ids`` de ``FieldDescriptor.__get__``.

El valor se siembra en ``__dict__`` a propósito: es el almacén de Django, y
la primera rama del descriptor lo entrega sólo a un singleton. Sin la
guarda, la lectura llana de un recordset múltiple o vacío no la detiene
nadie con el mensaje de la fuente.
"""

import pytest

import fields
from orm.environments import Environment
from orm.models import BaseModel


class SizeGuardProbe(BaseModel):
    """Sonda sin tabla: los recordsets se construyen con ``_from_ids``."""

    _name = 'orm.size.guard.probe'
    _description = "Size guard probe"

    label = fields.Char('Label')

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_size_guard_probe'


def recordset(ids, seeded=None):
    """Recordset de la sonda con ``ids``; ``seeded`` va a ``__dict__``."""
    record = SizeGuardProbe._from_ids(Environment(), ids, ids)
    if seeded is not None:
        record.__dict__['label'] = seeded
    return record


class TestSizeGuard:

    def test_two_ids_with_a_seeded_value_raise_expected_singleton(self):
        # El ancla al repr (``orm.size.guard.probe``) separa a ``ensure_one``
        # del descriptor de ``id``, que dice ``Expected singleton: ids=``.
        with pytest.raises(
            ValueError, match=r'Expected singleton: orm\.size\.guard\.probe'
        ):
            recordset((7, 18), seeded='x').label

    def test_two_ids_without_a_seeded_value_raise_expected_singleton(self):
        with pytest.raises(
            ValueError, match=r'Expected singleton: orm\.size\.guard\.probe'
        ):
            recordset((7, 18)).label

    def test_empty_recordset_gives_the_null_value_not_the_seeded(self):
        # ``:1659-1661`` — ``convert_to_record(convert_to_cache(False))``:
        # para un ``Char`` es ``False``.
        assert recordset((), seeded='x').label is False

    def test_singleton_returns_the_seeded_value(self):
        assert recordset((7,), seeded='x').label == 'x'
