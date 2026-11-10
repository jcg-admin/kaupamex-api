"""``_RelationalMulti`` existe como clase y es la única fuente de la familia
de escritura compartida.

≙ ``odoo19c: odoo/orm/fields_relational.py:556`` (``class
_RelationalMulti(_Relational)``) con ``write_sequence = 20`` (``:558``),
``convert_to_record_multi`` (``:653``), ``write`` (``:737``),
``write_batch`` (``:742``) y ``create`` (``:766``). Aquí los dos dueños,
``One2many`` y ``ManyToManyField`` —clase de Django, sin MRO que podamos
tocar—, reciben los mismos objetos función leídos de su
``__dict__``. Diseño:
``designs/many2many-write-family.md``, sección «Representación explícita».
"""
import pytest
from django.db import models

from orm.fields_relational import One2many, _RelationalMulti

SHARED = ('write', 'write_batch', 'create', 'convert_to_record_multi')


@pytest.mark.parametrize('name', SHARED)
def test_the_django_owner_carries_the_same_function(name):
    assert models.ManyToManyField.__dict__[name] is \
        _RelationalMulti.__dict__[name]
    assert getattr(One2many, name) is _RelationalMulti.__dict__[name]


def test_x2many_fields_are_written_last():
    assert _RelationalMulti.write_sequence == 20
    assert models.ManyToManyField.write_sequence == 20
    assert One2many.write_sequence == 20
