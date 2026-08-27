"""Contrato del bloque B6 del modelo ``website`` (tarea **#539**).

Adaptación de ``odoo19c: addons/website/models/website.py``
(``odoo-tools@622ddc2a``, LGPL-3). B6 es el bloque de cierre de la partición
B1-B6: re-medido por AST al abrirlo, el resto no declarado eran **42** métodos
(no los 32 de la partición). De ellos, **19 se portaron** en el pase B6 — CDN,
Plausible, URL canónica, snippets, ``_get_html_fields``, cachés sin caché
(#542) — y **4 más** en el pase de enumeración de rutas (#545:
``rule_is_enumerable``, ``_enumerate_pages``, ``search_pages``,
``check_existing_page``) y **3 más** en el pase de ``website.page`` (#104:
``new_page``, ``get_website_page_ids``, ``_get_website_pages`` — su
bloqueador era el propio modelo de página, que ese pase portó). Los demás
quedan declarados en los banners del módulo (4 bloqueados en B6, 9 en B4,
3 cubiertos con nombre divergente desde B1).

Los casos cubren:

1. **Presencia por nombre de los portados** — el conteo contra la fuente
   es lo único que distingue un porte parcial de uno completo.
2. **Los métodos de modelo** — CDN, claves únicas, valores cacheables,
   canónica, campos HTML y bloqueo de menú — contra PostgreSQL real
   (``django_db``).
"""

import pytest
from django.test import RequestFactory

from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.res_company import ResCompany
from addons.base.models.res_users import ResUsers
from addons.base.models.ir_http import set_current_request
from addons.base.models.ir_ui_view import IrUiView
from addons.website.models.website import Website
from addons.website.models.website_menu import WebsiteMenu

pytestmark = [pytest.mark.django_db]


#: Los 19 métodos que B6 porta, por nombre de la fuente. Derivados por AST
#: sobre ``odoo19c: addons/website/models/website.py`` menos los declarados
#: antes de este pase (111 - 75 = 42; ver la partición del módulo).
B6_PORTED = [
    'is_menu_cache_disabled',
    'get_unique_path',
    '_get_plausible_script_url',
    '_get_plausible_server',
    '_get_plausible_share_url',
    'get_unique_key',
    'search_url_dependencies',
    'get_template',
    'get_suggested_controllers',
    'image_url',
    'get_cdn_url',
    '_get_canonical_url',
    '_is_canonical_url',
    '_get_cached_values',
    '_get_cached',
    '_get_html_fields_blacklist',
    '_get_html_fields',
    '_is_snippet_used',
    '_disable_unused_snippets_assets',
]

#: El eje de enumeración de rutas, portado por #545 sobre el URLconf de
#: Django (``_iter_url_patterns`` ≙ ``router.iter_rules()``).
B6_PORTED_ROUTING = [
    'rule_is_enumerable',
    '_enumerate_pages',
    'search_pages',
    'check_existing_page',
]

#: El eje de páginas, desbloqueado por #104 al portar ``website.page``:
#: la fábrica de páginas y las dos consultas que la fuente cuelga del
#: sitio.
B6_PORTED_PAGES = [
    'new_page',
    'get_website_page_ids',
    '_get_website_pages',
]

#: Los 4 que siguen sin portarse — cada uno lleva su arista de bloqueo con
#: la forma fija en el banner del módulo (website.py). Se listan para que
#: un porte futuro los encuentre por grep; NO deben existir como métodos
#: hasta que su bloqueador se cierre.
B6_BLOCKED = [
    'action_dashboard_redirect',   # #467
    'get_client_action_url',       # #488
    'get_client_action',           # #488
    'button_go_website',           # #488
]


class TestB6Coverage:
    """La cobertura declarada del bloque es la real."""

    def test_the_ported_methods_exist(self):
        missing = [name for name in B6_PORTED + B6_PORTED_ROUTING + B6_PORTED_PAGES
                   if not callable(getattr(Website, name, None))]
        assert missing == []

    def test_the_blocked_methods_are_not_silently_stubbed(self):
        # Un stub sin cuerpo real sería un porte parcial presentado como
        # completo; el bloqueado correcto NO declara el símbolo.
        present = [name for name in B6_BLOCKED if hasattr(Website, name)]
        assert present == []


def _make_website(**overrides):
    # ``company`` y ``user`` son NOT NULL en el modelo (cabecera de B1); el
    # fixture los aporta igual que ``test_website_resolution``: la empresa se
    # crea por prueba y el usuario público se materializa una vez (allá lo
    # suministra la data del addon, que es de #104).
    values = {'name': 'B6', 'domain': 'https://b6.example.test'}
    if 'company' not in overrides:
        values['company'] = ResCompany.objects.create(name='Kaupamex B6 QA')
    if 'user' not in overrides:
        existing = ResUsers.objects.filter(login='b6@kaupamex.test').first()
        values['user'] = existing or ResUsers.objects.create_user(
            login='b6@kaupamex.test')
    values.update(overrides)
    website = Website(**values)
    website.save()
    return website


class TestCdn:
    def test_matching_filter_rewrites_against_cdn_base(self):
        website = _make_website(
            cdn_activated=True, cdn_url='https://cdn.example.test')
        assert (website.get_cdn_url('/web/assets/app.js')
                == 'https://cdn.example.test/web/assets/app.js')

    def test_non_matching_uri_comes_back_untouched(self):
        website = _make_website(cdn_url='https://cdn.example.test')
        assert website.get_cdn_url('/api/v1/cart/') == '/api/v1/cart/'

    def test_empty_uri_yields_empty_string(self):
        website = _make_website()
        assert website.get_cdn_url('') == ''


class TestPlausible:
    def test_defaults_are_empty_not_a_third_party_service(self):
        # #416: la fuente apunta a https://plausible.io; aquí, sin parámetro
        # configurado, no se emite endpoint alguno.
        website = _make_website()
        assert website._get_plausible_script_url() == ''
        assert website._get_plausible_server() == ''
        assert website._get_plausible_share_url() == ''

    def test_share_url_composes_when_operator_configured_a_server(self):
        website = _make_website(
            plausible_site='b6.example.test', plausible_shared_key='k3y')
        SystemParameter.set_param(
            'website.plausible_server', 'https://plausible.example.test')
        share_url = website._get_plausible_share_url()
        assert share_url.startswith(
            'https://plausible.example.test/share/b6.example.test')
        assert 'auth=k3y' in share_url


class TestUniqueKeyAndPath:
    def test_get_unique_key_prefixes_website_module(self):
        website = _make_website()
        assert website.get_unique_key('home') == 'website.home'
        assert (website.get_unique_key('home', template_module='blog')
                == 'blog.home')

    def test_get_unique_key_suffixes_on_collision(self):
        website = _make_website()
        IrUiView.objects.create(
            name='Home', type='qweb', key='website.home', arch_db='<t/>')
        assert website.get_unique_key('home') == 'website.home-1'

    def test_get_unique_path_returns_free_path_untouched(self):
        website = _make_website()
        assert website.get_unique_path('/una-ruta-libre') == '/una-ruta-libre'


class TestCachedValues:
    def test_the_four_reference_keys_are_served(self):
        # Las claves conservan los nombres de la fuente (user_id, company_id,
        # default_lang_id, homepage_url) — aquí coinciden con los attname.
        website = _make_website(homepage_url='/shop')
        values = website._get_cached_values()
        assert set(values) == {
            'user_id', 'company_id', 'default_lang_id', 'homepage_url'}
        assert values['homepage_url'] == '/shop'
        assert values['company_id'] == website.company_id

    def test_get_cached_reads_one_key(self):
        website = _make_website(homepage_url='/shop')
        assert website._get_cached('homepage_url') == '/shop'


class TestCanonicalUrl:
    def test_canonical_is_domain_plus_requested_path(self):
        website = _make_website(domain='https://b6.example.test')
        request = RequestFactory().get('/pages/privacy?x=1')
        set_current_request(request)
        try:
            assert (website._get_canonical_url()
                    == 'https://b6.example.test/pages/privacy?x=1')
        finally:
            set_current_request(None)

    def test_without_request_there_is_nothing_to_correct(self):
        website = _make_website()
        set_current_request(None)
        assert website._is_canonical_url() is True


class TestHtmlFields:
    def test_seed_and_own_html_fields_are_listed(self):
        pairs = Website._get_html_fields()
        assert (IrUiView, 'arch_db') in pairs
        # Los tres Html declarados por este mismo modelo.
        website_fields = {name for model, name in pairs if model is Website}
        assert {'custom_code_head', 'custom_code_footer',
                'robots_txt'} <= website_fields

    def test_blacklisted_models_are_excluded(self):
        blacklist_tables = {
            name.replace('.', '_')
            for name in Website._get_html_fields_blacklist()}
        tables = {model._meta.db_table
                  for model, _name in Website._get_html_fields()}
        assert not tables & blacklist_tables


class TestMenuCache:
    def test_record_like_route_disables_the_cache(self):
        website = _make_website()
        WebsiteMenu.objects.create(
            name='Producto', route='/shop/producto-42', key=f'm-{website.pk}',
            website=website)
        assert website.is_menu_cache_disabled() is True

    def test_plain_routes_keep_the_cache(self):
        website = _make_website()
        WebsiteMenu.objects.create(
            name='Contacto', route='/contactus', key=f'c-{website.pk}',
            website=website)
        assert website.is_menu_cache_disabled() is False


class TestImageUrl:
    def test_url_carries_dotted_name_pk_field_and_hash(self):
        website = _make_website()
        url = Website.image_url(website, 'logo')
        assert url.startswith(f'/web/image/website/{website.pk}/logo?unique=')

    def test_size_segment_is_appended_when_given(self):
        website = _make_website()
        url = Website.image_url(website, 'logo', size='128x128')
        assert '/logo/128x128?unique=' in url


class TestSuggestedControllers:
    def test_routes_come_verbatim_without_lang_localization(self):
        website = _make_website()
        suggested = website.get_suggested_controllers()
        assert [entry[1] for entry in suggested] == ['/', '/contactus']
