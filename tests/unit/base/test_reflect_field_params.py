"""``_reflect_field_params`` — el enganche que arma la fila de un campo.

La referencia lo declara aparte de ``_reflect_fields``
(``odoo19c: ir_model.py:1164``) precisamente para que una extensión pueda
añadir columnas sin reescribir el recorrido: Enterprise 19 lo hereda en dos
clases con ``_inherit = 'ir.model.fields'``.

Aquí el recorrido inverso ya existía (``_reflect_fields``) con el diccionario
en línea, así que el enganche no tenía dónde engancharse.
"""

import pytest

from addons.base.models.ir_model import IrModel, IrModelFields

pytestmark = pytest.mark.django_db


def test_the_hook_exists_and_is_a_classmethod():
    assert callable(getattr(IrModelFields, '_reflect_field_params', None))


def test_it_returns_the_columns_of_the_row():
    # La fila de ``ir.model`` de un modelo existe siempre en la fuente, y la
    # siembra de la ACL de ``base`` (``0096``) ya la crea: se toma, no se crea.
    row, _ = IrModel.objects.get_or_create(model='base.IrModel',
                                           defaults={'name': 'Modelo'})
    field = IrModel._meta.get_field('model')
    values = IrModelFields._reflect_field_params(field, row)
    assert values['model'] == 'base.IrModel'
    assert values['model_id'] == row
    assert values['ttype'] == 'char'
    assert set(values) == {
        'model',
        'model_id',
        'ttype',
        'field_description',
        'help',
        'required',
        'index',
        'store',
        'state',
        'relation',
        'size',
    }


def test_reflect_fields_consumes_the_hook():
    """El control: anular el enganche cambia lo que se escribe.

    Sin esta aserción el test anterior sólo probaría que existe un método —
    no que ``_reflect_fields`` pase por él, que es lo único que lo hace un
    punto de extensión.
    """
    row, _ = IrModel.objects.get_or_create(model='base.IrModelInherit',
                                           defaults={'name': 'Herencia'})
    original = IrModelFields._reflect_field_params.__func__

    def marked(cls, field, model_row):
        values = original(cls, field, model_row)
        values['field_description'] = 'MARCA'
        return values

    IrModelFields._reflect_field_params = classmethod(marked)
    try:
        IrModelFields._reflect_fields(row)
    finally:
        IrModelFields._reflect_field_params = classmethod(original)

    written = IrModelFields.objects.filter(model='base.IrModelInherit')
    assert written.exists()
    assert all(f.field_description == 'MARCA' for f in written)
