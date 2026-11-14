"""``Registry.load`` nombra también los modelos que el módulo extiende.

≙ ``odoo19c: odoo/orm/registry.py:350-380`` (*"return the names of the
directly modified models"*) y ``odoo/modules/loading.py:187-194``: el
módulo que extiende un modelo con ``_inherit`` lo carga y lo refleja con su
propio identificador ``<módulo>.model_<x>``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
registry-load-extended-models.md``.
"""
import pytest
from django.db import DEFAULT_DB_ALIAS

from addons.base.models import IrModelData
from modules.loading import load_modules
from orm.registry import Registry

pytestmark = pytest.mark.django_db


def test_load_names_the_models_the_module_extends():
    names = Registry(DEFAULT_DB_ALIAS).load('hr_recruitment')
    assert 'hr.job' in names
    assert 'hr.applicant' in names


def test_the_extending_module_reflects_the_model_with_its_xml_id():
    load_modules(DEFAULT_DB_ALIAS)
    assert IrModelData.objects.filter(
        module='hr_recruitment', name='model_hr_job',
        model='base.IrModel').exists()
