"""Rejilla de los campos relacionales sobre ``test_orm.category``.

Como ``model_record_grid``, no importa ni ``odoo`` ni ``orm``: el proceso de
referencia le pasa ``env['test_orm.category']`` y el puerto la clase con el
mismo ``_name``. El modelo existe en los dos árboles
(``odoo19c: odoo/addons/test_orm/models/test_orm.py`` y
``api: addons/test_orm``) y su ``parent`` es un ``Many2one`` hacia sí mismo,
así que los registros nuevos bastan: ninguna lectura toca la base.

``Many2one.convert_to_read``
(``odoo19c: odoo/orm/fields_relational.py:366-378``) se pide con valor y sin
él, con ``display_name`` y sin él; y ``BaseModel._read_format`` sobre el
hijo, con los dos modos de carga, que es el consumidor que decide
``use_display_name``. Un id de registro nuevo se compara por su clase, no
por su ``repr``, que lleva una dirección de memoria.
"""

FIELDS = ['name', 'parent']


def _step(function):
    try:
        return repr(function())
    except Exception as error:
        # La clase de la excepción es el resultado del paso; su mensaje no.
        return f'raises {type(error).__name__}'


def _shape(value):
    """Un id nuevo por su clase; el par conserva la etiqueta."""
    if isinstance(value, tuple):
        return (type(value[0]).__name__, value[1])
    if value is False or value is None:
        return value
    return type(value).__name__


def _rows(rows):
    return [sorted((key, _shape(value)) for key, value in row.items())
            for row in rows]


def trace(Domain, model, model_name):
    """Los pasos de la rejilla, cada uno como ``nombre resultado``."""
    del Domain, model_name
    field = model._fields['parent']
    parent = model.new({'name': 'P'})
    child = model.new({'name': 'C', 'parent': parent})
    orphan = model.new({'name': 'O'})
    steps = []
    for label, record in (('value', child), ('empty', orphan)):
        for display in (True, False):
            steps.append((
                f'convert_to_read {label} display={display}',
                lambda record=record, display=display: _shape(
                    field.convert_to_read(record['parent'], record,
                                          display))))
    for load in ('_classic_read', None):
        steps.append((f'read_format load={load}', lambda load=load: _rows(
            child._read_format(FIELDS, load))))
    return [f'{name} {_step(function)}' for name, function in steps]
