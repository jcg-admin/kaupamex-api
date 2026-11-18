"""``_load_records`` en todo modelo concreto, como en la fuente.

≙ ``odoo19c: odoo/orm/models.py:5054-5213``: el cargador de datos cuelga de
``BaseModel``, así que todo modelo lo tiene y ``tools/convert.py`` lo llama
sobre el modelo de cualquier ``<record>``. Diseño en
``designs/record-loader-universality.md``.

*Métrica:* clases de ``apps.get_models()`` que responden a
``_load_records``, y un registro cargado en un modelo de Django directo.
*Ciega a:* si cada modelo carga bien sus propios datos, y a un modelo de
un módulo que nada importa: por eso el censo importa antes los ``report``
de cada addon, que se cargan bajo demanda (``account.invoice.report``
quedó fuera del primer censo por eso). Los modelos que declaran las pruebas
(``tests/``) no son producto y no cuentan.
"""
import importlib
import pathlib

import pytest
from django.apps import apps

from addons.base.models import ResCountry
from orm.environments import env as current_env
from orm.environments import sudo

FRAMEWORK = {'admin', 'auth', 'contenttypes', 'sessions', 'token_blacklist'}
ADDONS = pathlib.Path(__file__).resolve().parents[3] / 'addons'


def _import_report_modules():
    """Los modelos de ``addons/<x>/report`` se registran al importarse."""
    for path in sorted(ADDONS.glob('*/report/*.py')):
        if path.stem != '__init__':
            importlib.import_module(
                f'addons.{path.parent.parent.name}.report.{path.stem}')


def _concrete_models():
    _import_report_modules()
    return [model for model in apps.get_models()
            if not model._meta.abstract and not model._meta.proxy
            and model._meta.app_label not in FRAMEWORK
            and not model.__module__.startswith('tests.')]


def test_every_concrete_model_answers_load_records():
    missing = sorted(model._meta.label for model in _concrete_models()
                     if not callable(getattr(model, '_load_records', None)))
    assert missing == []


@pytest.mark.django_db
def test_a_plain_django_model_loads_a_record_with_its_xml_id():
    with sudo():
        [country] = ResCountry._load_records([{
            'xml_id': 'test_record_loader.country_zz',
            'values': {'name': 'Zetalandia', 'code': 'ZZ'},
        }])
        found = current_env().ref('test_record_loader.country_zz')
    assert country.code == 'ZZ'
    assert found.pk == country.pk
