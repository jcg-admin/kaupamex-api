"""Todo modelo que declara ``_name`` es un ``BaseModel``, como en la fuente.

≙ ``odoo19c: odoo/orm/models.py:334`` (``BaseModel``),
``odoo19c: odoo/orm/models.py:7046`` (``AbstractModel = BaseModel``) y
``odoo19c: odoo/orm/models.py:7049`` (``Model(AbstractModel)``): allá no hay
modelo fuera de ``BaseModel``, así que ``env[name]`` siempre es un recordset.
Programa y censo en ``scripts/workbench/orm-continuation-plan-20261103T095630/
designs/basemodel-adoption-program.md``.

*Métrica:* clases concretas de ``apps.get_models()`` declaradas fuera de
``tests/`` que declaran ``_name`` en su propio cuerpo.
*Ciega a:* una contraparte de la fuente que aún no declara ``_name``; la
unidad que la adopta le porta la cabecera y entonces entra aquí.
"""
import collections
import inspect
import pathlib

import pytest
from django.apps import apps

from orm.models import BaseModel

TESTS = pathlib.Path(__file__).resolve().parents[2]
FRAMEWORK = {'admin', 'auth', 'contenttypes', 'sessions', 'token_blacklist'}


def _named_models_by_app():
    found = collections.defaultdict(list)
    for model in apps.get_models():
        meta = model._meta
        if meta.abstract or meta.proxy or meta.app_label in FRAMEWORK:
            continue
        if TESTS in pathlib.Path(inspect.getfile(model)).resolve().parents:
            continue
        if model.__dict__.get('_name'):
            found[meta.app_label].append(model)
    return found


NAMED = _named_models_by_app()

#: Las apps cuya adopción sigue pendiente, medidas al abrir el programa.
#: Es un trinquete, no una exención: la prueba exige que este conjunto sea
#: EXACTAMENTE el medido, así que una adopción tiene que sacar su app de aquí
#: y ninguna app nueva puede quedar fuera de ``BaseModel``. Vacío, el
#: paraguas ``basemodel-adoption-0397`` está cumplido.
PENDING = {
    'account',
    'analytic',
    'base',
    'helpdesk',
    'mass_mailing',
    'product',
    'sale',
    'stock',
    'website',
}


def _outside(app_label):
    return sorted(model._name for model in NAMED[app_label]
                  if not issubclass(model, BaseModel))


@pytest.mark.parametrize('app_label', sorted(set(NAMED) - PENDING))
def test_every_named_model_is_a_basemodel(app_label):
    assert _outside(app_label) == []


def test_the_pending_apps_are_exactly_the_measured_ones():
    assert {app for app in NAMED if _outside(app)} == PENDING
