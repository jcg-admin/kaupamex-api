"""Porte de ``odoo19c: odoo/addons/test_orm/tests/test_company_checks.py``.

Revisión de referencia: ``odoo-tools@abe4040ec1``. Se portan los casos de
coherencia de compañía en ``create``/``write`` (``_check_company_auto`` y
``check_company=True``). Los casos de entorno de la fuente
(``test_company_environment``, ``test_with_company``,
``test_company_sticky_with_context``) operan sobre ``res.users`` como recordset
y quedan fuera de este porte: ``res.users`` todavía no deriva de ``BaseModel``
(TASK-API-0397). ``test_check_company_write_performance`` cuenta consultas de
la fuente y tampoco se porta aquí.

**Adaptación declarada:** ``res.company`` se crea con su manager de Django,
porque su ``create`` sigue devolviendo ``QuerySet`` (H-API-1123); los modelos
de ``test_orm`` se crean con ``env[...].create``, como en la fuente.
"""

import pytest

from addons.base.models import ResCompany
from exceptions import UserError
from orm.commands import Command

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

#: Mitad roja persistida: ``Command`` es imperativo en este árbol
#: (``orm/commands.py``) y la fuente lo usa como valor diferido,
#: ``Command.link(id)`` → ``(4, id, 0)``. Sucesor: TASK-API-0190 (H-API-589).
#: ``strict=True`` hace fallar el caso el día que el contrato se cumpla.
needs_declarative_command = pytest.mark.xfail(
    strict=True, raises=TypeError,
    reason='Command declarativo: TASK-API-0190')


@pytest.fixture
def companies():
    return tuple(
        ResCompany.objects.create(code=f'orm-check-{key}', name=f'Company {key}')
        for key in 'abc')


@pytest.fixture
def parents(env, companies):
    company_a, company_b, _ = companies
    Parent = env['test_orm.model_parent']
    return (
        Parent.create({'name': 'M0', 'company_id': False}),
        Parent.create({'name': 'M1', 'company_id': company_a.id}),
        Parent.create({'name': 'M2', 'company_id': company_b.id}),
    )


def test_check_company_auto(env, companies):
    child = env['test_orm.model_child'].create({'company_id': companies[0].id})
    assert child._check_company_auto


@needs_declarative_command
def test_company_and_same_company(env, companies, parents):
    env['test_orm.model_child'].create({
        'name': 'M1',
        'company_id': companies[0].id,
        'parent_id': parents[1].id,
        'parent_ids': [Command.link(parents[1].id)],
    })


@needs_declarative_command
def test_company_and_different_company(env, companies, parents):
    with pytest.raises(UserError):
        env['test_orm.model_child'].create({
            'name': 'M1',
            'company_id': companies[1].id,
            'parent_id': parents[1].id,
        })
    with pytest.raises(UserError):
        env['test_orm.model_child'].create({
            'name': 'M1',
            'company_id': companies[1].id,
            'parent_ids': [Command.link(parents[1].id),
                           Command.link(parents[2].id)],
        })


@needs_declarative_command
def test_company_and_no_company(env, companies, parents):
    env['test_orm.model_child'].create({
        'name': 'M1',
        'company_id': companies[0].id,
        'parent_id': parents[0].id,
        'parent_ids': [Command.link(parents[0].id)],
    })


@needs_declarative_command
def test_no_company_and_no_company(env, parents):
    env['test_orm.model_child'].create({
        'name': 'M1',
        'company_id': False,
        'parent_id': parents[0].id,
        'parent_ids': [Command.link(parents[0].id)],
    })


@needs_declarative_command
def test_no_company_and_some_company(env, parents):
    with pytest.raises(UserError):
        env['test_orm.model_child'].create({
            'name': 'M1',
            'company_id': False,
            'parent_id': parents[1].id,
        })
    with pytest.raises(UserError):
        env['test_orm.model_child'].create({
            'name': 'M1',
            'company_id': False,
            'parent_ids': [Command.link(parents[0].id),
                           Command.link(parents[1].id)],
        })


def test_no_company_check(env, companies, parents):
    env['test_orm.model_child_nocheck'].create({
        'name': 'M1',
        'company_id': companies[1].id,
        'parent_id': parents[1].id,
    })


@needs_declarative_command
def test_company_write(env, companies, parents):
    company_a, company_b, _ = companies
    child = env['test_orm.model_child'].create({
        'name': 'M1',
        'company_id': company_a.id,
        'parent_id': parents[1].id,
        'parent_ids': [Command.link(parents[1].id)],
    })

    with pytest.raises(UserError):
        child.company_id = company_b.id
    with pytest.raises(UserError):
        child.parent_id = parents[2].id
    with pytest.raises(UserError):
        child.parent_ids = [Command.link(parents[2].id)]

    child.write({
        'parent_id': parents[2].id,
        'parent_ids': [Command.unlink(parents[1].id),
                       Command.link(parents[2].id)],
        'company_id': company_b.id,
    })


def test_false_reaches_the_column_as_null_without_the_descriptor(env, parents):
    """Adaptación propia del Consumer: la ruta que no pasa por el descriptor.

    ``QuerySet.update`` llama a ``ForeignKey.get_db_prep_save`` directamente;
    ahí ``False`` también tiene que llegar como ``NULL``
    (``odoo19c: odoo/orm/fields_relational.py:326-327``) y no como ``0``.
    """
    Parent = type(parents[1])
    Parent.objects.filter(pk=parents[1].id).update(company_id=False)
    assert Parent.objects.get(pk=parents[1].id).company_id is None
