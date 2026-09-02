"""``tools.misc.ReadonlyDict`` — el mapa que ni ``dict.update`` puede modificar.

Fiel a ``odoo19c: odoo/tools/misc.py:1671-1706`` (LGPL-3).

La propiedad por la que se porta está en su propio docstring: un ``frozendict``
hereda de ``dict``, así que ``dict.update(data, ...)`` lo modifica por la
espalda; ``ReadonlyDict`` hereda de ``collections.abc.Mapping`` y por eso no
tiene por dónde. El precio de esa garantía es que ``json.dumps`` deja de
conocerlo — que es exactamente la rama que ``json_default`` cubre.
"""
import json

import pytest

from tools.misc import ReadonlyDict

pytestmark = pytest.mark.unit


# -- Lectura: es un ``Mapping`` completo (``misc.py:1696-1706``) -------------

def test_reads_a_key():
    """``__getitem__`` (``:1698-1699``)."""
    assert ReadonlyDict({'foo': 'bar'})['foo'] == 'bar'


def test_reports_its_length_and_iterates_its_keys():
    """``__len__`` e ``__iter__`` (``:1701-1705``)."""
    data = ReadonlyDict({'a': 1, 'b': 2})
    assert len(data) == 2
    assert sorted(data) == ['a', 'b']


def test_answers_membership():
    """``__contains__`` (``:1696-1697``)."""
    data = ReadonlyDict({'foo': 'bar'})
    assert 'foo' in data
    assert 'baz' not in data


def test_derives_the_mapping_helpers_from_the_abc():
    """``keys``/``values``/``items``/``get`` los deriva ``Mapping``, no el porte."""
    data = ReadonlyDict({'foo': 'bar'})
    assert list(data.keys()) == ['foo']
    assert list(data.values()) == ['bar']
    assert list(data.items()) == [('foo', 'bar')]
    assert data.get('missing', 'default') == 'default'


def test_copies_the_source_mapping_instead_of_aliasing_it():
    """``__init__`` hace ``dict(data)`` (``:1693-1694``).

    Sin la copia, mutar el diccionario original cambiaría el «inmodificable»,
    que es la garantía entera.
    """
    source = {'foo': 'bar'}
    data = ReadonlyDict(source)
    source['foo'] = 'changed'
    assert data['foo'] == 'bar'


# -- Escritura: las tres formas que el docstring de la fuente enumera --------

def test_rejects_item_assignment():
    """``data['baz'] = 'xyz'`` — «raises exception» (``:1687``)."""
    data = ReadonlyDict({'foo': 'bar'})
    with pytest.raises(TypeError):
        data['baz'] = 'xyz'


def test_rejects_item_deletion():
    """Borrar tampoco: ``Mapping`` no declara ``__delitem__``."""
    data = ReadonlyDict({'foo': 'bar'})
    with pytest.raises(TypeError):
        del data['foo']


def test_rejects_the_update_method():
    """``data.update(...)`` — «raises exception» (``:1688``)."""
    data = ReadonlyDict({'foo': 'bar'})
    with pytest.raises(AttributeError):
        data.update({'baz': 'xyz'})


def test_rejects_update_called_through_the_dict_class():
    """``dict.update(data, ...)`` — la puerta trasera del ``frozendict`` (``:1689``).

    Es la diferencia que justifica el porte: sobre un ``frozendict`` esta
    llamada **funciona**, porque hereda de ``dict``.
    """
    data = ReadonlyDict({'foo': 'bar'})
    with pytest.raises(TypeError):
        dict.update(data, {'baz': 'xyz'})
    assert 'baz' not in data


def test_has_no_instance_dictionary():
    """``__slots__ = ('_data__',)`` (``:1691``) — sin atributos improvisados."""
    data = ReadonlyDict({'foo': 'bar'})
    assert not hasattr(data, '__dict__')


# -- El precio de la garantía, que es la razón de la rama de ``json_default`` -

def test_json_dumps_does_not_know_it():
    """«`json.dumps` works for a `frozendict` … but not for a `ReadonlyDict`»."""
    with pytest.raises(TypeError):
        json.dumps(ReadonlyDict({'foo': 'bar'}))
