"""``_get_placeholder_filename`` existe en todo modelo y devuelve ``False``.

≙ ``odoo19c: odoo/orm/models.py:6999-7004``. Diseño en
``designs/placeholder-filename.md`` del Workbench (TASK-API-0513).

*Métrica:* el valor devuelto por la base y por una sobrescritura con
``super()``.
*Ciega a:* el flujo HTTP de ``ir.binary``, que tiene sus propias pruebas.
"""
import pytest

from addons.base.models.res_partner import ResPartner
from addons.onboarding.models.onboarding_onboarding_step import (
    OnboardingOnboardingStep)
from orm.environments import Environment
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.django_db


@pytest.fixture
def env(db):
    environment = Environment(None, SUPERUSER_ID, {})
    with environment:
        yield environment


def test_a_django_model_without_override_returns_false():
    assert ResPartner()._get_placeholder_filename('image_1920') is False


def test_a_base_model_recordset_returns_false(env):
    record = env['test_orm.category'].create({'name': 'a'})
    assert record._get_placeholder_filename('name') is False


def test_the_onboarding_step_falls_back_to_the_base():
    step = OnboardingOnboardingStep()
    assert step._get_placeholder_filename('step_image') == (
        'base/static/img/onboarding_default.png')
    assert step._get_placeholder_filename('title') is False
