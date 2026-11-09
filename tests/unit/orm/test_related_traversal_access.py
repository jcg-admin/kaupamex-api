"""Acceso denegado al recorrer un ``related`` no heredado.

≙ ``Field._compute_related`` (``odoo19c: odoo/orm/fields.py:696-712``): el
``AccessError`` de un eslabón **intermedio** se relanza con el párrafo
*«Implicitly accessed through '<descripción>' (<modelo>).»*; el de la lectura
final, no.

La expectativa vive en el Workbench de la iniciativa
(``reference/observations/related-traversal-access.json``), marcada como
inferencia estática del código de la referencia: esta prueba la lee y no la
redefine.

*Métrica:* último párrafo del mensaje de ``AccessError`` al leer cada campo.
*Ciega a:* el resto del mensaje.
"""
import json
import pathlib

import pytest
from django.contrib.auth import get_user_model

from exceptions import AccessError
from orm.environments import env as current_env
from orm.environments import sudo, user_scope
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db

ROOT = pathlib.Path(__file__).resolve().parents[3]
OBSERVATION = (
    ROOT / 'scripts/workbench/orm-continuation-plan-20261103T095630'
    / 'reference/observations/related-traversal-access.json')
MODELS = ('test_orm.related', 'test_orm.related_foo', 'test_orm.related_bar')


def _expected():
    return json.loads(OBSERVATION.read_text())['observed']


def _paragraph(error):
    message = str(error.args[0]) if error.args else ''
    last = message.split('\n\n')[-1]
    return last if last.startswith('Implicitly accessed through') else None


def _seed():
    Groups, Access, Rule, IrModel = (MODELS_BY_NAME[name] for name in (
        'res.groups', 'ir.model.access', 'ir.rule', 'ir.model'))
    group = Groups.objects.create(name='related-traversal')
    reader = get_user_model().objects.create_user(
        login='related-traversal', password=None, name='related-traversal')
    reader.group_ids.add(group)
    for name in MODELS:
        label = MODELS_BY_NAME[name]._meta.label
        model = (IrModel.objects.filter(model=label).first()
                 or IrModel.objects.create(model=label, name=name))
        Access.objects.create(name=name, model_id=model, group_id=group,
                              perm_read=True, perm_write=True,
                              perm_create=True, perm_unlink=True)
    rule = Rule.objects.create(
        name='hide secret foo',
        model_name=MODELS_BY_NAME['test_orm.related_foo']._meta.label,
        domain_force="[('name', '!=', 'secret-foo')]")
    rule.groups.add(group)
    bar = MODELS_BY_NAME['test_orm.related_bar'].objects.create(name='bar')
    foo = MODELS_BY_NAME['test_orm.related_foo'].objects.create(
        name='secret-foo', bar_id=bar)
    row = MODELS_BY_NAME['test_orm.related'].objects.create(
        name='visible', foo_id=foo)
    return reader, row


@pytest.fixture
def outcomes():
    actor = get_user_model().objects.create_user(
        login='related-traversal-root', password=None,
        name='related-traversal-root')
    with user_scope(actor.pk), sudo():
        reader, row = _seed()
    result = {}
    with user_scope(reader.pk):
        for field in _expected():
            current_env().invalidate_all()
            visible = MODELS_BY_NAME['test_orm.related'].objects.get(
                pk=row.pk)
            try:
                getattr(visible, field)
            except AccessError as error:
                result[field] = {'exception': 'AccessError',
                                 'implicit_paragraph': _paragraph(error)}
            else:
                result[field] = {'exception': None}
    return result


def test_the_traversal_matches_the_observation(outcomes):
    assert outcomes == _expected()


def test_the_observation_separates_the_two_reads():
    """Control: si la observación diera lo mismo en los dos campos, la
    prueba no distinguiría el eslabón intermedio de la lectura final."""
    expected = _expected()
    assert expected['foo_name']['implicit_paragraph'] is None
    assert expected['foo_bar_name']['implicit_paragraph']
