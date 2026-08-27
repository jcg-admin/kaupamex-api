"""B5 (#538) — bloqueo de rastreadores de terceros, sin red y sin navegador.

Universo controlado: un sitio con empresa y usuario público, una lista propia
de dominios conocida, y la petición en curso inyectada con
``set_current_request`` (``RequestFactory``) cuando el caso necesita leer el
consentimiento — el fixture la limpia SIEMPRE al salir. El consentimiento
viaja en la cookie ``cookie_consent`` (JSON URL-encoded por categoría,
``core.middleware.cookie_governance``), que es la divergencia de formato
declarada en ``addons/website/models/ir_http.py``.
"""
import json
from urllib.parse import quote

import pytest
from django.test import RequestFactory
from django.utils.safestring import SafeString

from addons.base.models.ir_http import set_current_request
from addons.base.models.res_company import ResCompany
from addons.base.models.res_users import ResUsers
from addons.website.models.website import Website
from orm.environments import company_scope

pytestmark = pytest.mark.django_db


@pytest.fixture
def website(db):
    company = ResCompany.objects.create(name='Kaupamex Trackers QA')
    user = (ResUsers.objects.filter(login='public@kaupamex.test').first()
            or ResUsers.objects.create_user(login='public@kaupamex.test'))
    with company_scope(company.pk):
        yield Website.objects.create(name='Tienda', sequence=1, user=user)


@pytest.fixture
def watching(website):
    """El sitio con una lista propia conocida — se suma a la de fábrica."""
    website.custom_blocked_third_party_domains = (
        'tracker.example\nwww.videos.example')
    return website


@pytest.fixture
def http_request():
    """La petición en curso del caso; el ``finally`` implícito del yield la
    limpia para no filtrar contexto entre tests (mismo criterio que el
    middleware)."""
    request = RequestFactory().get('/')
    set_current_request(request)
    yield request
    set_current_request(None)


def _grant_consent(request, choices):
    request.COOKIES['cookie_consent'] = quote(json.dumps({'choices': choices}))


# ── las dos listas ──────────────────────────────────────────────────────────

def test_blocked_domains_list_splits_by_line(watching):
    domains = watching._get_blocked_third_party_domains_list()
    assert 'tracker.example' in domains          # la propia
    assert 'youtube.com' in domains              # la de fábrica sigue ahí
    assert all('\n' not in domain for domain in domains)


def test_blocked_iframe_containers_is_the_set_of_five(website):
    assert website._get_blocked_iframe_containers_classes() == {
        's_map',
        's_instagram_page',
        'o_facebook_page',
        'o_background_video',
        'media_iframe_video',
    }


# ── la vigilancia por dominio y por clase ───────────────────────────────────

def test_domains_watchlist_matches_exact_host(watching):
    assert watching._is_tag_domains_watchlisted(
        'iframe', {'src': 'https://tracker.example/widget'})


def test_domains_watchlist_matches_subdomain(watching):
    assert watching._is_tag_domains_watchlisted(
        'iframe', {'src': 'https://a.tracker.example/widget'})


def test_domains_watchlist_rejects_misleading_suffix(watching):
    """``mytracker.example`` NO es ``tracker.example`` ni subdominio suyo."""
    assert not watching._is_tag_domains_watchlisted(
        'iframe', {'src': 'https://mytracker.example/widget'})


def test_domains_watchlist_www_entry_blocks_bare_domain(watching):
    """``www.videos.example`` en la lista bloquea también sin ``www.``."""
    assert watching._is_tag_domains_watchlisted(
        'script', {'src': 'https://videos.example/v.js'})


def test_domains_watchlist_ignores_other_tags_and_missing_src(watching):
    assert not watching._is_tag_domains_watchlisted(
        'div', {'src': 'https://tracker.example/widget'})
    assert not watching._is_tag_domains_watchlisted('iframe', {})


def test_classes_watchlist_is_the_intersection(website):
    assert website._is_tag_classes_watchlisted('div', {'class': 's_map foo'})
    assert not website._is_tag_classes_watchlisted('div', {'class': 'foo bar'})


# ── el marcado del elemento ─────────────────────────────────────────────────

def test_remove_trackers_neutralizes_the_src(website):
    atts = {'src': 'https://youtube.com/embed/x'}
    website._remove_third_party_trackers('iframe', atts, ['domains'])
    assert atts['data-need-cookies-approval'] == 'true'
    assert atts['data-nocookie-src'] == 'https://youtube.com/embed/x'
    assert atts['src'] == 'about:blank'


def test_remove_trackers_marks_container_without_touching_src(website):
    """Clase en la lista y sin ``src``: sólo el marcador — el iframe que el
    cliente cree al vuelo nacerá ya controlado."""
    atts = {'class': 's_map'}
    website._remove_third_party_trackers('div', atts, ['classes'])
    assert atts['data-need-cookies-approval'] == 'true'
    assert 'src' not in atts
    assert 'data-nocookie-src' not in atts


# ── el control del fragmento HTML ───────────────────────────────────────────

def test_control_html_neutralizes_blocked_iframes(website, monkeypatch):
    monkeypatch.setattr(Website, '_should_remove_third_party_trackers',
                        lambda self: True)
    content = '<div><iframe src="https://youtube.com/embed/a"></iframe></div>'
    result = website._control_third_party_trackers_in_html(content)
    assert isinstance(result, SafeString)
    assert 'about:blank' in result
    assert 'data-nocookie-src="https://youtube.com/embed/a"' in result


def test_control_html_passes_through_unparseable_input(website, monkeypatch):
    """Un comentario suelto revienta el parser (``ParserError: Document is
    empty``, medido) → passthrough del input, no una excepción."""
    monkeypatch.setattr(Website, '_should_remove_third_party_trackers',
                        lambda self: True)
    content = '<!-- solo comentario -->'
    assert website._control_third_party_trackers_in_html(content) is content


def test_control_html_passes_through_when_removal_is_off(website, monkeypatch):
    monkeypatch.setattr(Website, '_should_remove_third_party_trackers',
                        lambda self: False)
    content = '<iframe src="https://youtube.com/embed/a"></iframe>'
    assert website._control_third_party_trackers_in_html(content) is content


# ── consentimiento ──────────────────────────────────────────────────────────

def test_all_consents_granted_without_cookies_bar(website):
    """Sin barra de cookies el consentimiento pleno se da por concedido."""
    assert website._allConsentsGranted() is True


def test_all_consents_follow_the_consent_cookie(website, http_request):
    website.cookies_bar = True
    website.save()
    # Sin cookie de consentimiento → nada concedido.
    assert website._allConsentsGranted() is False
    # Todas las categorías concedidas → pleno.
    _grant_consent(http_request, {'marketing': True})
    assert website._allConsentsGranted() is True
    # Una categoría denegada → no es pleno.
    _grant_consent(http_request, {'marketing': False})
    assert website._allConsentsGranted() is False


def test_should_remove_is_the_conjunction(website, http_request):
    website.cookies_bar = True
    website.save()
    assert website.block_third_party_domains is True   # default de fábrica
    # Barra + bloqueo + sin consentimiento → se controla.
    assert website._should_remove_third_party_trackers() is True
    # Con consentimiento total → no se controla.
    _grant_consent(http_request, {'marketing': True})
    assert website._should_remove_third_party_trackers() is False


def test_should_remove_is_off_without_cookies_bar(website):
    assert website.cookies_bar is False
    assert not website._should_remove_third_party_trackers()
