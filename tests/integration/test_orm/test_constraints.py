"""Restricciones Python al crear y escribir — porte de ``test_15_constraint``.

Referencia: odoo-tools ``abe4040ec1``,
``odoo19c: odoo/addons/test_orm/tests/test_fields.py:798-820`` sobre
``test_orm.message._check_author`` (``…/models/test_orm.py:177-180``).

El flujo que se prueba: ``_create`` valida los campos almacenados del lote
(``odoo19c: odoo/orm/models.py:4948-4949``), ``write`` valida lo escrito
(``:4491``) y el recómputo valida lo calculado (``:4954-4959``). Análisis:
``scripts/workbench/constraint-validation-flow-20261110T051341/FLOW.md``.

``discussion_0`` es dato de demostración en la fuente; aquí la prueba crea
su propia discusión con el usuario como participante, que es lo que el dato
aporta a la prueba.
"""
import pytest
from django.core.exceptions import ValidationError

import models

pytestmark = pytest.mark.django_db


@pytest.fixture
def discussion(env, system_user):
    assert env.user == system_user
    return env['test_orm.discussion'].create([{
        'name': 'Discussion constraint',
        'participants': [(6, 0, [env.user.id])],
    }])


def test_15_constraint(env, discussion, assert_raises):
    """ test new-style Python constraints """
    env.flush_all()

    # remove oneself from discussion participants: we can no longer create
    # messages in discussion
    discussion.participants -= env.user
    with assert_raises(ValidationError, discussion):
        env['test_orm.message'].create(
            [{'discussion': discussion.id, 'body': 'Whatever'}])

    # make sure that assertRaises() does not leave fields to recompute
    assert not env.fields_to_compute()

    # put back oneself into discussion participants: now we can create
    # messages in discussion
    discussion.participants += env.user
    env['test_orm.message'].create(
        [{'discussion': discussion.id, 'body': 'Whatever'}])

    # check constraint on recomputed field
    assert discussion.messages
    with assert_raises(ValidationError, discussion):
        discussion.name = 'X'


def test_a_many2many_towards_django_rows_reads_as_their_recordset(
        env, discussion):
    """``_RelationalMulti.convert_to_record``
    (``odoo19c: odoo/orm/fields_relational.py:643``): el valor es el conjunto
    de filas del comodelo, en su ``_order``, no el gestor de Django."""
    participants = discussion.participants
    assert env.user in participants
    assert list(participants) == [env.user]
    assert isinstance(participants, models.AccessQuerySet)


def test_recordset_algebra_on_django_rows(env, discussion):
    """``__add__``/``__sub__``/``__and__``/``__or__`` (``models.py:6544-6610``)
    con una fila suelta como singleton, que es lo que vale un ``Many2one``
    hacia un modelo de Django."""
    user = env.user
    users = type(user).objects.filter(pk=user.pk)
    assert list(users - user) == []
    assert list((users - user) + user) == [user]
    assert list((users - user) | user) == [user]
    assert list(users & user) == [user]
    with pytest.raises(TypeError, match='inconsistent models'):
        users - discussion
    with pytest.raises(TypeError, match='unsupported operand'):
        users - 'x'
