"""Contrato de ``Command`` — ``odoo19c: odoo/orm/commands.py``.

El oráculo es el archivo de la referencia en ``odoo-tools@abe4040e``:
``class Command(enum.IntEnum)`` (``:11``), los siete códigos
``CREATE = 0`` … ``SET = 6`` (``:35-41``) y siete ``classmethod`` que
devuelven el triple con el **miembro** del enum como primer elemento
(``:44-126``): ``(cls.CREATE, 0, values)``, ``(cls.SET, 0, ids)``…

Mutaciones que lo hacen caer: volver a una clase plana de enteros (caen las
pruebas del enum y la de identidad del código); convertir ``ids`` a lista en
``set`` (cae la de identidad de ``ids``); y en ``is_command_list``, volver a
``type(...) is int`` (cae la del triple con miembro) o aceptar ``bool`` (cae
la de ``True``).
"""
import enum

import pytest

from orm.commands import Command, is_command_list

pytestmark = pytest.mark.integration


class TestCommandIsTheReferenceEnum:

    def test_it_is_an_int_enum_with_the_seven_codes_in_order(self):
        assert issubclass(Command, enum.IntEnum)
        assert [(member.name, int(member)) for member in Command] == [
            ('CREATE', 0), ('UPDATE', 1), ('DELETE', 2), ('UNLINK', 3),
            ('LINK', 4), ('CLEAR', 5), ('SET', 6)]

    def test_a_literal_rpc_code_resolves_to_its_member(self):
        assert Command(4) is Command.LINK
        assert Command.LINK == 4


class TestEachFactoryReturnsTheReferenceTriple:

    @pytest.mark.parametrize('triple, code, expected', [
        (Command.create({'name': 'x'}), Command.CREATE, (0, 0, {'name': 'x'})),
        (Command.update(7, {'name': 'y'}), Command.UPDATE,
         (1, 7, {'name': 'y'})),
        (Command.delete(7), Command.DELETE, (2, 7, 0)),
        (Command.unlink(7), Command.UNLINK, (3, 7, 0)),
        (Command.link(7), Command.LINK, (4, 7, 0)),
        (Command.clear(), Command.CLEAR, (5, 0, 0)),
        (Command.set([1, 2]), Command.SET, (6, 0, [1, 2])),
    ])
    def test_the_triple_and_its_code(self, triple, code, expected):
        assert triple == expected
        # ``is`` solo no discrimina: CPython cachea los enteros pequeños y
        # ``0 is 0`` es verdadero también con la clase plana.
        assert type(triple[0]) is Command
        assert triple[0] is code

    def test_set_returns_the_ids_it_received(self):
        ids = (1, 2)
        assert Command.set(ids)[2] is ids


class TestCommandListsAreRecognised:

    def test_a_triple_built_by_the_factory(self):
        assert is_command_list([Command.link(3), Command.unlink(4)])

    def test_a_literal_rpc_triple(self):
        assert is_command_list([(4, 3, 0)])

    def test_a_boolean_is_not_a_command_code(self):
        assert not is_command_list([(True, 3, 0)])
