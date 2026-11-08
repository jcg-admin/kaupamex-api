"""``_add_inherited_fields`` con varios padres delegados.

La rejilla diferencial (``model_persisted_grid``) lo mide contra la
referencia en los cuatro modelos con ``_inherits`` que las dos bases
instalan; ninguno delega en dos padres. Este archivo mide el orden de la
fuente para ese caso (``odoo19c: odoo/orm/model_classes.py:486-494``): el
diccionario ``to_inherit`` se arma padre por padre, así que un padre
posterior pisa a uno anterior en el mismo nombre, y un campo propio del
hijo nunca se sustituye.
"""

from types import SimpleNamespace

from orm.model_classes import _add_inherited_fields


class _Field:
    """Un campo mínimo: ``copy.copy`` lo duplica con su ``__dict__``."""

    def __init__(self, label):
        self.label = label
        self.inherited = False
        self.inherited_field = None
        self.related = None
        self.compute_sudo = True
        self.store = True
        self.concrete = True
        self.model_name = ''


def _parent(*names, label):
    return SimpleNamespace(_fields={name: _Field(f'{label}.{name}')
                                    for name in names})


def _child(inherits, fields, abstract=False):
    model = type('Child', (), {
        '_inherits': inherits,
        '_meta': SimpleNamespace(abstract=abstract),
        '_name': 'test.child',
    })
    return model, fields


def _fk(name, parent):
    return SimpleNamespace(name=name, attname=f'{name}_id',
                           related_model=parent)


def test_a_later_parent_wins_on_the_same_name():
    first = _parent('name', 'only_first', label='first')
    second = _parent('name', 'only_second', label='second')
    model, fields = _child({'first': 'first', 'second': 'second'}, {
        'first': _fk('first', first), 'second': _fk('second', second)})
    _add_inherited_fields(model, fields)
    assert fields['name'].inherited_field is second._fields['name']
    assert fields['name'].related == 'second_id.name'
    assert fields['only_first'].related == 'first_id.only_first'
    assert fields['only_second'].related == 'second_id.only_second'


def test_an_own_field_is_never_replaced():
    parent = _parent('name', 'email', label='parent')
    own = _Field('child.name')
    model, fields = _child({'parent': 'parent'}, {
        'parent': _fk('parent', parent), 'name': own})
    _add_inherited_fields(model, fields)
    assert fields['name'] is own
    assert fields['email'].inherited
    assert fields['email'].compute_sudo is False
    assert fields['email'].store is False


def test_an_abstract_model_inherits_nothing():
    parent = _parent('name', label='parent')
    model, fields = _child({'parent': 'parent'},
                           {'parent': _fk('parent', parent)}, abstract=True)
    _add_inherited_fields(model, fields)
    assert set(fields) == {'parent'}
