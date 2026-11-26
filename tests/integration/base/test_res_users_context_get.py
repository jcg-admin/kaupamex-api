"""``res.users.context_get`` — el contexto de idioma y zona del usuario.

≙ ``context_get`` (``odoo19c: odoo/addons/base/models/res_users.py:694-723``):
``lang`` y ``tz`` del usuario, sin ``id``; el ``lang`` cae a uno instalado
(petición → empresa → ``DEFAULT_LANG`` → el primero); ``uid``; memorizado por
``uid`` y purgado cuando el usuario escribe un campo de
``_get_invalidation_fields`` (``:641-643``). Diseño:
``designs/res-users-context-get.md``.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from addons.base.models import ResCompany, ResLang
from addons.base.models.ir_http import set_current_request
from addons.base.models.res_users import ResUsers
from orm.environments import sudo, user_scope

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def _user(login, **values):
    with sudo():
        user = get_user_model().objects.create_user(
            login=login, password=None, name=login)
        for field, value in values.items():
            setattr(user, field, value)
        user.save()
    return user


def _with_company(user, code, lang):
    """Da al usuario una empresa cuyo partner habla ``lang``."""
    with sudo():
        company = ResCompany.objects.create(code=code, name=code)
        partner = company.partner
        partner.lang = lang
        partner.save()
        user.company = company
        user.save()


def _activate(code):
    with sudo():
        lang = ResLang.objects.get(code=code)
        lang.active = True
        lang.save()


@pytest.fixture
def no_request():
    set_current_request(None)
    yield
    set_current_request(None)


def test_it_returns_lang_tz_and_uid_without_id(no_request):
    user = _user('ctx-get-plain', lang='en_US', tz='America/Mexico_City')
    with user_scope(user.pk):
        context = ResUsers.context_get()
    assert dict(context) == {
        'lang': 'en_US', 'tz': 'America/Mexico_City', 'uid': user.pk}


def test_an_uninstalled_lang_falls_back_to_the_company_partner(no_request):
    _activate('es_MX')
    user = _user('ctx-get-company', lang='fr_FR')
    _with_company(user, 'ctx-get-company', 'es_MX')
    with user_scope(user.pk):
        assert ResUsers.context_get()['lang'] == 'es_MX'


def test_without_any_installed_choice_it_is_the_default_lang(no_request):
    user = _user('ctx-get-default', lang='fr_FR')
    _with_company(user, 'ctx-get-default', 'fr_FR')
    with user_scope(user.pk):
        assert ResUsers.context_get()['lang'] == 'en_US'


def test_the_request_language_comes_before_the_company(no_request):
    _activate('es_MX')
    user = _user('ctx-get-request', lang='fr_FR')
    set_current_request(
        RequestFactory().get('/', HTTP_ACCEPT_LANGUAGE='es-MX,es;q=0.9'))
    with user_scope(user.pk):
        assert ResUsers.context_get()['lang'] == 'es_MX'


def test_an_unknown_uid_has_an_empty_context(no_request):
    with user_scope(2147483646):
        assert dict(ResUsers.context_get()) == {}


def test_it_is_memoized_per_uid(no_request):
    user = _user('ctx-get-memo', lang='en_US')
    with user_scope(user.pk):
        assert ResUsers.context_get() is ResUsers.context_get()


def test_writing_the_lang_purges_the_memo(no_request):
    _activate('es_MX')
    user = _user('ctx-get-purge', lang='en_US')
    with user_scope(user.pk):
        assert ResUsers.context_get()['lang'] == 'en_US'
    with sudo():
        user.lang = 'es_MX'
        user.save()
    with user_scope(user.pk):
        assert ResUsers.context_get()['lang'] == 'es_MX'
