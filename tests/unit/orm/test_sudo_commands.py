"""Comandos x2many bajo ``sudo()`` o ``with_user`` — ``_check_sudo_commands``.

≙ ``_RelationalMulti._check_sudo_commands`` (``odoo19c:
odoo/orm/fields_relational.py:772-777``) y la sección 2 de
``test_sudo_commands`` (``odoo/addons/test_orm/tests/test_fields.py:3677``):
sobre un comodelo con ``_allow_sudo_commands = False`` los comandos corren
con el usuario por defecto de la transacción y sin ``sudo``; sobre uno que
los admite, con el entorno del registro.

El usuario por defecto aquí es el del canal ambiental: este árbol no fija
``Transaction.default_env`` desde el entorno ambiental (divergencia declarada
en ``designs/check-sudo-commands.md`` del Workbench).

*Métrica:* clase de la excepción y operación nombrada en su mensaje.
*Ciega a:* el resto del texto, que es la traducción de este árbol.
"""
import pytest
from django.contrib.auth import get_user_model

from exceptions import AccessError
from orm.commands import Command, related_manager
from orm.environments import env as current_env
from orm.environments import (Environment, _discard_connection_transaction,
                              get_transaction, sudo, user_scope)
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db

ACCESS = {
    # modelo -> (lectura, escritura, creación, borrado) del usuario por defecto
    'test_orm.user': (True, True, True, True),
    'test_orm.group': (True, False, False, False),
    'test_orm.related_foo': (True, True, True, True),
}


def _request_env(uid):
    """El entorno de la petición — el ``default_env`` de la referencia, que
    es el primero de la transacción con un uid válido."""
    _discard_connection_transaction()
    Environment(uid=uid)
    assert get_transaction().default_env.uid == uid


def _grant(group, name, perms):
    IrModel = MODELS_BY_NAME['ir.model']
    Access = MODELS_BY_NAME['ir.model.access']
    label = MODELS_BY_NAME[name]._meta.label
    model = (IrModel.objects.filter(model=label).first()
             or IrModel.objects.create(model=label, name=name))
    read, write, create, unlink = perms
    Access.objects.create(name=name, model_id=model, group_id=group,
                          perm_read=read, perm_write=write,
                          perm_create=create, perm_unlink=unlink)


@pytest.fixture
def actors():
    User = get_user_model()
    Groups = MODELS_BY_NAME['res.groups']
    with sudo():
        restricted = Groups.objects.create(name='sudo-commands-restricted')
        full = Groups.objects.create(name='sudo-commands-full')
        for name, perms in ACCESS.items():
            _grant(restricted, name, perms)
        for name in ('test_orm.user', 'test_orm.group'):
            _grant(full, name, (True, True, True, True))
        me = User.objects.create_user(login='sudo-commands-me', password=None,
                                      name='me')
        admin = User.objects.create_user(login='sudo-commands-admin',
                                         password=None, name='admin')
        me.group_ids.add(restricted)
        admin.group_ids.add(full)
        group = MODELS_BY_NAME['test_orm.group'].objects.create(name='public')
        user = MODELS_BY_NAME['test_orm.user'].objects.create(name='foo')
        related_manager(user, 'group_ids').add(group)
    return me, admin, user.pk


@pytest.mark.parametrize('variant', ['with_user', 'sudo'])
def test_create_on_a_comodel_without_sudo_commands_is_refused(actors, variant):
    me, admin, user_pk = actors
    with user_scope(me.pk):
        _request_env(me.pk)
        users = current_env()['test_orm.user'].browse()
        Users = (users.with_user(admin) if variant == 'with_user'
                 else users.sudo())
        with pytest.raises(AccessError, match='crear registros'):
            Users.create([{'name': 'foo', 'group_ids': [Command.create({})]}])


@pytest.mark.parametrize('variant', ['with_user', 'sudo'])
def test_update_on_a_comodel_without_sudo_commands_is_refused(actors, variant):
    me, admin, user_pk = actors
    with user_scope(me.pk):
        _request_env(me.pk)
        record = current_env()['test_orm.user'].browse([user_pk])
        record = (record.with_user(admin) if variant == 'with_user'
                  else record.sudo())
        group_pk = record.group_ids.ids[0]
        with pytest.raises(AccessError, match='modificar registros'):
            record.write({'group_ids': [
                Command.update(group_pk, {'name': 'x'})]})


@pytest.mark.parametrize('variant', ['with_user', 'sudo'])
def test_delete_on_a_comodel_without_sudo_commands_is_refused(actors, variant):
    me, admin, user_pk = actors
    with user_scope(me.pk):
        _request_env(me.pk)
        record = current_env()['test_orm.user'].browse([user_pk])
        record = (record.with_user(admin) if variant == 'with_user'
                  else record.sudo())
        group_pk = record.group_ids.ids[0]
        with pytest.raises(AccessError, match='borrar registros'):
            record.write({'group_ids': [Command.delete(group_pk)]})


def test_allowed_sudo_commands_run_with_the_record_env(actors):
    """CONTROL: ``related_bar`` admite comandos bajo ``sudo`` y el usuario
    por defecto no tiene ninguna ACL sobre él."""
    me, _admin, _user_pk = actors
    with sudo():
        foo = MODELS_BY_NAME['test_orm.related_foo'].objects.create(name='foo')
    with user_scope(me.pk):
        _request_env(me.pk)
        record = current_env()['test_orm.related_foo'].browse(
            [foo.pk]).sudo()
        record.write({'bar_ids': [Command.create({'name': 'bar'})]})
        assert record.bar_ids.mapped('name') == ['bar']


def test_the_default_user_with_access_runs_the_commands(actors):
    """CONTROL: la guarda baja privilegios, no prohíbe; el administrador como
    usuario por defecto crea el grupo."""
    _me, admin, user_pk = actors
    with user_scope(admin.pk):
        _request_env(admin.pk)
        record = current_env()['test_orm.user'].browse([user_pk]).sudo()
        record.write({'group_ids': [Command.create({'name': 'made'})]})
        assert 'made' in record.group_ids.mapped('name')
