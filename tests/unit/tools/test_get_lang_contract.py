"""``get_lang(env, lang_code)`` y ``format_amount(env, …)`` con la firma de la
fuente (``odoo19c: odoo/tools/misc.py:1308-1326, 1635-1651``).

``get_lang`` devuelve un ``LangData`` de un idioma instalado, eligiendo en el
orden de la fuente: el código pedido, el del contexto, el del partner de la
empresa, y si no ``en_US``.
"""

import inspect

import pytest

from addons.base.models.res_company import ResCompany
from addons.base.models.res_lang import LangData, ResLang
from orm import registry
from orm.environments import context_scope, env, set_current_company
from tools import misc

pytestmark = pytest.mark.django_db


@pytest.fixture
def spanish():
    registry.clear_cache('stable')
    lang = ResLang.objects.get(code='es_MX')
    lang.active = True
    lang.save()
    yield lang
    registry.clear_cache('stable')


def test_the_signatures_are_the_source_ones():
    get_lang_params = list(inspect.signature(misc.get_lang).parameters)
    format_params = list(inspect.signature(misc.format_amount).parameters)
    assert get_lang_params == ['env', 'lang_code']
    assert format_params[:3] == ['env', 'amount', 'currency']


def test_without_anything_it_is_english(spanish):
    lang = misc.get_lang(env())
    assert isinstance(lang, LangData) and lang.code == 'en_US'


def test_an_installed_code_wins(spanish):
    assert misc.get_lang(env(), 'es_MX').code == 'es_MX'


def test_a_code_that_is_not_installed_is_ignored(spanish):
    assert misc.get_lang(env(), 'xx_XX').code == 'en_US'


def test_the_context_lang_is_the_second_choice(spanish):
    with context_scope(lang='es_MX'):
        assert misc.get_lang(env()).code == 'es_MX'
        assert misc.get_lang(env(), 'en_US').code == 'en_US'


def test_the_company_partner_lang_is_the_third_choice(spanish):
    from_company = ResCompany.objects.create(name='Kaupamex QA lang')
    partner = from_company.partner
    partner.lang = 'es_MX'
    partner.save(update_fields=['lang'])
    set_current_company(from_company.pk)
    try:
        assert misc.get_lang(env()).code == 'es_MX'
        with context_scope(lang='en_US'):
            assert misc.get_lang(env()).code == 'en_US'
    finally:
        set_current_company(None)
