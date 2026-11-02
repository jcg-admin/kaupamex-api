"""``Command`` en sus dos formas — TASK-API-0190 (H-API-589).

≙ ``odoo19c: odoo/orm/commands.py``: cada método devuelve el triple diferido
``(código, id, valores)``. La forma ejecutiva —manager o fila como primer
argumento— la siguen usando ``stock`` y debe conservarse.
"""

from unittest import mock

from orm.commands import Command, is_command_list


def test_the_source_form_returns_the_deferred_triple():
    assert Command.create({'name': 'x'}) == (0, 0, {'name': 'x'})
    assert Command.update(7, {'name': 'y'}) == (1, 7, {'name': 'y'})
    assert Command.delete(7) == (2, 7, 0)
    assert Command.unlink(7) == (3, 7, 0)
    assert Command.link(7) == (4, 7, 0)
    assert Command.clear() == (5, 0, 0)
    assert Command.set([7, 8]) == (6, 0, [7, 8])


def test_the_codes_are_the_source_constants():
    assert (Command.CREATE, Command.UPDATE, Command.DELETE, Command.UNLINK,
            Command.LINK, Command.CLEAR, Command.SET) == (0, 1, 2, 3, 4, 5, 6)


def test_the_executive_form_still_acts_on_the_manager():
    manager = mock.Mock()
    Command.link(manager, 'row')
    Command.unlink(manager, 'row')
    Command.set(manager, ['row'])
    Command.clear(manager)
    manager.add.assert_called_once_with('row')
    manager.remove.assert_called_once_with('row')
    manager.set.assert_called_once_with(['row'])
    manager.clear.assert_called_once_with()


def test_the_executive_delete_and_update_act_on_the_row():
    row = mock.Mock(spec=['delete', 'save', 'name'])
    Command.delete(row)
    row.delete.assert_called_once_with()
    assert Command.update(row, name='z') is row
    assert row.name == 'z'


def test_a_bool_code_is_not_a_command():
    """``type(code) is int``: ``True`` no es el código 1 de ``UPDATE``."""
    assert not is_command_list([(True, 1, 0)])


def test_a_command_list_is_recognised():
    assert is_command_list([Command.link(1), Command.unlink(2)])
    assert not is_command_list([1, 2])
    assert not is_command_list([])
