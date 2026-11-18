"""``_load_records`` en todo modelo concreto, como en la fuente.

≙ ``odoo19c: odoo/orm/models.py:5054-5213``: el cargador de datos cuelga de
``BaseModel``, así que todo modelo lo tiene y ``tools/convert.py`` lo llama
sobre el modelo de cualquier ``<record>``. Diseño en
``designs/record-loader-universality.md``.

*Métrica:* clases de ``apps.get_models()`` que responden a
``_load_records``, y un registro cargado en un modelo de Django directo.
*Ciega a:* si cada modelo carga bien sus propios datos.
"""
import pytest
from django.apps import apps

from addons.base.models import ResCountry
from orm.environments import env as current_env
from orm.environments import sudo

FRAMEWORK = {'admin', 'auth', 'contenttypes', 'sessions', 'token_blacklist'}


def _concrete_models():
    return [model for model in apps.get_models()
            if not model._meta.abstract and not model._meta.proxy
            and model._meta.app_label not in FRAMEWORK]


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
