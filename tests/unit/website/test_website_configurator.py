"""B4 (#537) — el configurador y los tres RPC, sin tocar la red.

Universo controlado: un sitio con empresa y usuario público, dos menús con
``route`` conocida, y un transporte inyectado con ``monkeypatch`` cuando el
caso necesita observar el payload. El camino sin endpoint (default vacío,
#416) corta con ``AccessError`` **antes** de la red — ese es el contrato que
``configurator_init`` de la fuente atrapa para degradar.
"""
import pytest

from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.res_company import ResCompany
from addons.base.models.res_users import ResUsers
from addons.website.models import website as website_module
from addons.website.models.website import Website
from addons.website.models.website_menu import WebsiteMenu
from exceptions import AccessError
from orm.environments import company_scope

pytestmark = pytest.mark.django_db


@pytest.fixture
def website(db):
    company = ResCompany.objects.create(name='Kaupamex Config QA')
    user = (ResUsers.objects.filter(login='public@kaupamex.test').first()
            or ResUsers.objects.create_user(login='public@kaupamex.test'))
    with company_scope(company.pk):
        yield Website.objects.create(name='Tienda', sequence=1, user=user)


# ── indexación ──────────────────────────────────────────────────────────────

def test_idna_url_lowercases_before_encoding(website):
    """El codec idna NO normaliza mayúsculas (medido en B2) — lo hace el
    ``.lower()`` del método."""
    assert website._idna_url('HTTPS://Tienda.Example.com') == 'tienda.example.com'


def test_is_indexable_url_ignores_www_and_scheme(website):
    website.domain = 'https://tienda.example.com'
    assert website._is_indexable_url('http://www.tienda.example.com/') is True
    assert website._is_indexable_url('https://otra.example.com') is False


# ── los tres RPC ────────────────────────────────────────────────────────────

def test_api_rpc_without_endpoint_raises_access_error(website):
    """Default vacío (#416): sin ``ir.config_parameter`` no hay red."""
    with pytest.raises(AccessError):
        website._website_api_rpc('/api/website/1/x', {})


def test_missing_industry_inherits_the_rpc_state(website):
    with pytest.raises(AccessError):
        Website.configurator_missing_industry('cestería ritual')


def test_api_rpc_uses_the_configured_endpoint_and_stamps_version(
        website, monkeypatch):
    """Con endpoint declarado, el transporte recibe ``endpoint + route`` y un
    payload JSON-RPC 2.0 con la versión del producto inyectada."""
    SystemParameter.set_param('website.website_api_endpoint',
                              'https://svc.kaupamex.test')
    seen = {}

    def fake_transport(url, method='call', params=None, timeout=15):
        seen.update(url=url, method=method, params=params, timeout=timeout)
        return {'industries': []}

    monkeypatch.setattr(website_module, '_configurator_rpc_call',
                        fake_transport)
    result = website._website_api_rpc('/api/website/1/configurator/industries',
                                      {'lang': 'es_MX'})
    assert result == {'industries': []}
    assert seen['url'] == ('https://svc.kaupamex.test'
                           '/api/website/1/configurator/industries')
    assert seen['params']['lang'] == 'es_MX'
    assert seen['params']['version']          # release.version, no vacío


def test_olg_rpc_extends_the_timeout(website, monkeypatch):
    """≙ ``timeout=45`` de ``_OLG_api_rpc`` (``odoo19c: :498``)."""
    SystemParameter.set_param('website.olg_api_endpoint',
                              'https://olg.kaupamex.test')
    seen = {}

    def fake_transport(url, method='call', params=None, timeout=15):
        seen['timeout'] = timeout
        return 'texto'

    monkeypatch.setattr(website_module, '_configurator_rpc_call',
                        fake_transport)
    website._OLG_api_rpc('/api/olg/1/generate', {'prompt': 'hola'})
    assert seen['timeout'] == 45


# ── el configurador portable ────────────────────────────────────────────────

def test_get_cta_data_is_verbatim(website):
    assert website.get_cta_data('sell', 'ecommerce') == {
        'cta_btn_text': False, 'cta_btn_href': '/contactus'}


def test_snippet_view_key_prefixes_the_default_module(website):
    assert (website._get_snippet_view_key('s_cover', 'homepage')
            == 'website.configurator_homepage_s_cover')
    assert (website._get_snippet_view_key('mi_modulo.s_hero', 'about')
            == 'mi_modulo.configurator_about_s_hero')
    assert website._get_snippet_defaults('s_cover') == {}


def test_footer_links_point_at_the_static_page_prefix(website):
    links = website.configurator_get_footer_links()
    assert links[0]['href'] == '/pages/privacy'


def test_set_menu_links_updates_sequences_by_route(website):
    """La fuente empareja por ``url``; aquí el campo es ``route`` y el
    recorte usa la FK ``website`` (#543)."""
    WebsiteMenu.objects.create(key='cfg-shop', name='Shop', route='/shop',
                               website=website)
    WebsiteMenu.objects.create(key='cfg-about', name='About', route='/about',
                               website=website)
    otro = WebsiteMenu.objects.create(key='cfg-ajeno', name='Shop', route='/shop')
    website.configurator_set_menu_links(
        None, {'/shop': {'sequence': 40}, '/about': {'sequence': 50}})
    assert WebsiteMenu.objects.get(key='cfg-shop').sequence == 40
    assert WebsiteMenu.objects.get(key='cfg-about').sequence == 50
    # El menú sin sitio (u de otro sitio) no se toca.
    assert WebsiteMenu.objects.get(pk=otro.pk).sequence == otro.sequence


def test_configurator_skip_marks_the_current_website(website):
    """Divergencia declarada: sin módulos de tema (#488) devuelve ``None``;
    lo portado es el flag."""
    assert website.configurator_done is False
    assert Website.configurator_skip() is None
    website.refresh_from_db()
    assert website.configurator_done is True
