"""``LangData``, ``LangDataDict`` y la caché de idiomas activos de ``res.lang``.

≙ ``odoo19c: odoo/addons/base/models/res_lang.py:18-46, 270-330``.
"""

import pytest

from addons.base.models.res_lang import LangData, LangDataDict, ResLang
from exceptions import UserError
from orm import registry

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def fresh_cache():
    registry.clear_cache('stable')
    yield
    registry.clear_cache('stable')


def test_lang_data_reads_like_a_record_and_is_falsy_without_id():
    data = LangData({'id': 3, 'code': 'es_MX'})
    assert data.code == 'es_MX' and bool(data)
    assert not LangData({'id': False, 'code': False})
    with pytest.raises(AttributeError):
        data.missing


def test_lang_data_dict_answers_a_dummy_for_a_missing_key():
    langs = LangDataDict([('en_US', LangData({'id': 1, 'code': 'en_US'}))])
    dummy = langs['xx_XX']
    assert not dummy and dummy.code is False


def test_get_data_finds_an_active_language_by_code():
    data = ResLang._get_data(code='en_US')
    assert data.code == 'en_US' and data.id
    assert set(data) == set(ResLang.CACHED_FIELDS)


def test_get_data_of_an_inactive_language_is_the_dummy():
    inactive = ResLang.objects.filter(active=False).first()
    assert inactive is not None
    assert not ResLang._get_data(code=inactive.code)


def test_get_active_by_refuses_a_field_that_is_not_cached():
    with pytest.raises(UserError):
        ResLang._get_active_by('date_format_typo')


def test_lang_get_and_get_code_resolve_only_active_languages():
    assert ResLang._lang_get('en_US').code == 'en_US'
    assert ResLang._get_code('en_US') == 'en_US'
    inactive = ResLang.objects.filter(active=False).first()
    assert ResLang._get_code(inactive.code) is False


def test_get_installed_is_built_from_the_active_cache_sorted_by_name():
    installed = ResLang.get_installed()
    assert ('en_US', 'English (US)') in installed
    assert [name for _, name in installed] == sorted(name for _, name in installed)


def test_activating_a_language_reaches_the_cache():
    """El ``create``/``write`` de la fuente vacían la familia ``stable``; sin
    eso un idioma recién activado no aparecería hasta reiniciar."""
    inactive = ResLang.objects.filter(active=False).first()
    assert not ResLang._get_data(code=inactive.code)
    inactive.active = True
    inactive.save()
    assert ResLang._get_data(code=inactive.code).code == inactive.code
