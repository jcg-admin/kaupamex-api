"""Campos dispersos — ≙ ``base_sparse_field/tests/test_sparse_fields.py``.

La referencia declara un modelo transitorio de prueba con un campo
serializado y seis dispersos encima (``odoo19c:
base_sparse_field/models/models.py:79-87``) y comprueba que escribir un
disperso deja el valor **dentro** del mapa, no en una columna propia.

Aquí el modelo de prueba se declara en el propio test —sin migración— porque
``Sparse`` no registra nada en ``_meta``: es un descriptor, y para
ejercitarlo basta un contenedor que tenga el ``Serialized``.
"""
import pytest

from orm import fields


class Carrier:
    """Contenedor mínimo con el campo serializado y sus dispersos encima.

    Reemplaza al ``sparse_fields.test`` de la referencia. No es un modelo de
    Django a propósito: el descriptor no toca ``_meta``, así que un objeto
    plano ejerce exactamente el mismo camino que un registro real.
    """

    boolean = fields.Sparse('data')
    integer = fields.Sparse('data', coerce=int)
    char = fields.Sparse('data')
    absent = fields.Sparse('data', default='fallback')

    def __init__(self, data=None):
        self.data = {} if data is None else data


def test_serialized_defaults_to_an_empty_map():
    """``Serialized`` entrega un mapa vacío, no ``None``.

    ≙ ``convert_to_record: json.loads(value or "{}")`` de la referencia.
    """
    field = fields.Serialized()
    assert field.get_default() == {}


def test_serialized_omits_its_own_defaults_from_the_migration():
    """El ``deconstruct`` no repite lo que el propio campo ya fija."""
    _name, path, _args, kwargs = fields.Serialized().deconstruct()
    assert path.endswith('fields_sparse.Serialized')
    assert 'default' not in kwargs
    assert 'blank' not in kwargs


def test_reading_an_unset_field_returns_its_default():
    carrier = Carrier()
    assert carrier.boolean is None
    assert carrier.absent == 'fallback'


def test_writing_stores_the_value_inside_the_map():
    """El valor vive en el mapa, que es el punto del mecanismo."""
    carrier = Carrier()
    carrier.char = 'yes'
    assert carrier.data == {'char': 'yes'}
    assert carrier.char == 'yes'


def test_writing_a_falsy_value_removes_the_key():
    """≙ ``_inverse_sparse``: el falso se **retira**, no se guarda.

    Es la asimetría que mantiene disperso al mapa; guardarlo lo llenaría de
    ceros y cadenas vacías.
    """
    carrier = Carrier(data={'char': 'yes'})
    carrier.char = ''
    assert carrier.data == {}


def test_writing_a_falsy_value_on_an_unset_field_is_a_no_op():
    carrier = Carrier()
    carrier.char = ''
    assert carrier.data == {}


def test_rewriting_the_same_value_leaves_the_map_untouched():
    """≙ la guarda ``if values.get(name) != value`` de la referencia."""
    carrier = Carrier()
    carrier.char = 'yes'
    first = carrier.data
    carrier.char = 'yes'
    assert carrier.data == first


def test_coerce_applies_on_read():
    """JSON no distingue ``int`` de ``float``; ``coerce`` lo recupera."""
    carrier = Carrier(data={'integer': 3.0})
    assert carrier.integer == 3
    assert isinstance(carrier.integer, int)


def test_deleting_removes_the_key():
    carrier = Carrier(data={'char': 'yes'})
    del carrier.char
    assert carrier.data == {}


def test_delete_on_an_unset_field_is_a_no_op():
    carrier = Carrier()
    del carrier.char
    assert carrier.data == {}


def test_the_map_is_replaced_not_mutated_in_place():
    """El contenedor se reasigna para que Django vea el campo sucio.

    Mutar el ``dict`` que la instancia ya tiene dejaría la escritura fuera de
    ``save(update_fields=…)``. La referencia no tiene el problema porque su
    asignación pasa por el ORM; aquí se resuelve copiando y reasignando.
    """
    original = {}
    carrier = Carrier(data=original)
    carrier.char = 'yes'
    assert original == {}, 'el mapa original no debe mutarse'
    assert carrier.data == {'char': 'yes'}


def test_a_non_dict_container_reads_as_empty():
    """Una fila vieja con ``NULL`` en la columna no debe reventar la lectura."""
    carrier = Carrier(data=None)
    assert carrier.char is None


def test_the_field_requires_the_name_of_its_container():
    with pytest.raises(ValueError):
        fields.Sparse('')


def test_accessing_on_the_class_returns_the_descriptor():
    """Sin instancia se devuelve el descriptor, no un valor."""
    assert isinstance(Carrier.__dict__['char'], fields.Sparse)
    assert Carrier.char is Carrier.__dict__['char']
