"""Contrato de ``website.page`` / ``website.rewrite`` / ``website.route`` (#104).

Adaptación de ``odoo19c: addons/website/models/website_page.py`` y
``website_rewrite.py`` (``odoo-tools@622ddc2a``, LGPL-3). Los casos cubren:

1. **Cobertura por nombre** — portados presentes, bloqueados ausentes (el
   conteo contra la fuente es lo que distingue un porte parcial de uno
   completo).
2. **La delegación ``_inherits``** — la página expone los campos de su vista.
3. **Los métodos de modelo** contra PostgreSQL real (``django_db``): páginas
   más específicas, unicidad de rutas, ``check_existing_page``, ``new_page``
   y el invariante de las redirecciones.
"""

import pytest

from addons.base.models.ir_ui_view import IrUiView
from addons.base.models.res_company import ResCompany
from addons.base.models.res_users import ResUsers
from addons.website.models.website import Website
from addons.website.models.website_menu import WebsiteMenu
from addons.website.models.website_page import WebsitePage
from addons.website.models.website_rewrite import WebsiteRewrite, WebsiteRoute
from exceptions import UserError, ValidationError
from orm.domains import Domain

pytestmark = [pytest.mark.django_db]


#: Los 14 métodos que #104 porta en website_page.py, por nombre de la fuente
#: (``__init__`` de ``PageCannotBeCached`` aparte). Derivados por AST sobre
#: ``odoo19c: addons/website/models/website_page.py`` (22 métodos en la
#: clase + 1 en la excepción).
PAGE_PORTED = [
    '_compute_is_homepage',
    '_compute_visible',
    '_compute_website_menu',
    '_compute_website_url',
    '_get_most_specific_pages',
    'copy_data',
    'clone_page',
    'delete',            # ≙ unlink — divergencia CRUD declarada
    'save',              # ≙ write — divergencia CRUD declarada
    '_search_get_detail',
    '_search_fetch',
    '_allow_cache_insertion',
    '_get_page_info',
]

#: Los 9 que siguen sin portarse — cada uno lleva su arista con la forma
#: fija en website_page.py. NO deben existir como métodos hasta que su
#: bloqueador se cierre.
PAGE_BLOCKED = [
    '_compute_can_publish',
    'get_website_meta',
    'action_page_debug_view',
    '_allow_to_use_cache',
    '_post_process_response_from_cache',
    '_get_cache_key',
    '_get_response',
    '_get_response_cached',
    '_get_response_raw',
]

#: website_rewrite.py — 11 portados (``unlink``/``create``/``write`` viajan
#: como ``delete``/``save``), 1 bloqueado.
REWRITE_PORTED = [
    '_onchange_route_id',
    '_check_url_to',
    '_compute_display_name',
    'save',
    'delete',
    '_invalidate_routing',
    'refresh_routes',
]
REWRITE_BLOCKED = ['get_import_templates']
ROUTE_PORTED = ['_search_display_name', 'name_search', '_refresh']


class TestCoverage:
    """La cobertura declarada del porte es la real."""

    def test_the_ported_page_methods_exist(self):
        missing = [name for name in PAGE_PORTED
                   if not callable(getattr(WebsitePage, name, None))]
        assert missing == []

    def test_the_blocked_page_methods_are_not_silently_stubbed(self):
        present = [name for name in PAGE_BLOCKED
                   if name in vars(WebsitePage)]
        assert present == []

    def test_the_rewrite_and_route_methods_exist(self):
        missing = [name for name in REWRITE_PORTED
                   if not callable(getattr(WebsiteRewrite, name, None))]
        missing += [name for name in ROUTE_PORTED
                    if not callable(getattr(WebsiteRoute, name, None))]
        assert missing == []

    def test_the_blocked_rewrite_methods_are_not_silently_stubbed(self):
        present = [name for name in REWRITE_BLOCKED
                   if name in vars(WebsiteRewrite)]
        assert present == []

    def test_the_class_attributes_come_from_the_source(self):
        assert WebsitePage._name == 'website.page'
        assert WebsitePage._inherits == {'ir.ui.view': 'view'}
        assert WebsitePage._description == 'Page'
        assert WebsitePage._order == 'website_id'
        assert WebsitePage._CACHE_DURATION == 3600
        assert WebsiteRewrite._name == 'website.rewrite'
        assert WebsiteRoute._name == 'website.route'
        assert WebsiteRoute._rec_name == 'path'
        assert WebsiteRoute._order == 'path'


def _make_website(**overrides):
    # ``company`` y ``user`` son NOT NULL (cabecera de B1); mismo fixture que
    # ``test_website_b6._make_website``.
    values = {'name': 'P104', 'domain': 'https://p104.example.test'}
    if 'company' not in overrides:
        values['company'] = ResCompany.objects.create(name='Kaupamex P104 QA')
    if 'user' not in overrides:
        existing = ResUsers.objects.filter(login='p104@kaupamex.test').first()
        values['user'] = existing or ResUsers.objects.create_user(
            login='p104@kaupamex.test')
    values.update(overrides)
    website = Website(**values)
    website.save()
    return website


def _make_page(website, url='/pagina-104', key='website.pagina-104',
               name='Página 104', **overrides):
    view = overrides.pop('view', None) or IrUiView.objects.create(
        name=name, type='template', key=key, arch_db='<t><div id="wrap"/></t>')
    values = {'url': url, 'view': view, 'website': website}
    values.update(overrides)
    return WebsitePage.objects.create(**values)


class TestInheritsDelegation:
    def test_the_page_exposes_the_view_fields_as_its_own(self):
        website = _make_website()
        page = _make_page(website)
        assert page.name == 'Página 104'          # delegado (view.name)
        assert page.key == 'website.pagina-104'   # delegado (view.key)
        assert page.arch == '<t><div id="wrap"/></t>'
        assert page.view_write_date == page.view.updated_at

    def test_writing_a_delegated_field_lands_on_the_view(self):
        website = _make_website()
        page = _make_page(website)
        page.arch = '<t><div id="wrap">nuevo</div></t>'
        page.view.save()
        page.view.refresh_from_db()
        assert 'nuevo' in page.view.arch_db


class TestMostSpecificPages:
    def test_the_site_page_wins_over_the_generic_twin(self):
        website = _make_website()
        generic_view = IrUiView.objects.create(
            name='Gemela', type='template', key='website.gemela', arch_db='<t/>')
        specific_view = IrUiView.objects.create(
            name='Gemela', type='template', key='website.gemela-w', arch_db='<t/>')
        generic = WebsitePage.objects.create(
            url='/gemela', view=generic_view, website=None)
        specific = WebsitePage.objects.create(
            url='/gemela', view=specific_view, website=website)
        most = WebsitePage._get_most_specific_pages(
            [generic, specific], website=website)
        assert most == [specific]

    def test_a_lone_generic_page_survives(self):
        # La página genérica (``website=None``) se crea suelta: ``_make_page``
        # toma el sitio por posición, así que pasarlo también por nombre sería
        # el mismo argumento dos veces.
        website = _make_website()
        page = _make_page(None)
        most = WebsitePage._get_most_specific_pages([page], website=website)
        assert most == [page]


class TestWebsitePagesApi:
    def test_get_website_pages_filters_by_domain(self):
        website = _make_website()
        page = _make_page(website)
        found = Website._get_website_pages(
            domain=Domain('url', '=', '/pagina-104'))
        assert [entry.pk for entry in found] == [page.pk]
        assert Website._get_website_pages(
            domain=Domain('url', '=', '/no-existe')) == []

    def test_get_website_page_ids_maps_site_to_page_ids(self):
        website = _make_website()
        page = _make_page(website)
        assert website.get_website_page_ids() == {website.pk: [page.pk]}

    def test_get_website_page_ids_without_pk_returns_all_under_none(self):
        website = _make_website()
        page = _make_page(website)
        unsaved = Website(name='sin-pk')
        mapping = unsaved.get_website_page_ids()
        assert list(mapping) == [None]
        assert page.pk in mapping[None]


class TestUniquePathWithPages:
    def test_an_existing_page_url_gets_a_counter(self):
        website = _make_website()
        _make_page(website, url='/acerca', key='website.acerca')
        assert website.get_unique_path('/acerca') == '/acerca-1'

    def test_a_free_url_comes_back_untouched(self):
        website = _make_website()
        assert website.get_unique_path('/ruta-libre') == '/ruta-libre'


class TestCheckExistingPage:
    def test_a_page_record_counts_as_existing(self):
        website = _make_website()
        _make_page(website, url='/acerca', key='website.acerca')
        assert website.check_existing_page('/acerca') is True

    def test_a_301_rewrite_counts_as_existing(self):
        website = _make_website()
        WebsiteRewrite.objects.create(
            name='Vieja a nueva', url_from='/vieja', url_to='/nueva',
            redirect_type='301', website=website)
        assert website.check_existing_page('/vieja') is True

    def test_an_unknown_path_does_not_exist(self):
        website = _make_website()
        assert website.check_existing_page('/no-hay-nada-aqui-104') is False


class TestNewPage:
    def _seed_template(self):
        return IrUiView.objects.create(
            name='Default page', type='template', key='website.default_page',
            arch_db='<t><div id="wrap"/></t>')

    def test_new_page_creates_view_page_and_menu(self):
        website = _make_website()
        self._seed_template()
        result = website.new_page(name='Sobre Kaupamex', add_menu=True)
        assert result['url'] == '/sobre-kaupamex'
        page = WebsitePage.objects.get(pk=result['page_id'])
        assert page.url == '/sobre-kaupamex'
        assert page.website_id == website.pk
        view = IrUiView.objects.get(pk=result['view_id'])
        assert view.key == 'website.sobre-kaupamex'
        # La clave nueva sustituye a la de la plantilla dentro del arch.
        assert 'website.default_page' not in view.arch_db
        menu = WebsiteMenu.objects.get(pk=result['menu_id'])
        assert menu.route == '/sobre-kaupamex'
        assert menu.page_id == page.pk

    def test_new_page_derives_a_unique_url_on_collision(self):
        website = _make_website()
        self._seed_template()
        first = website.new_page(name='Repetida')
        second = website.new_page(name='Repetida')
        assert first['url'] == '/repetida'
        assert second['url'] == '/repetida-1'

    def test_new_page_without_template_cuts_with_user_error(self):
        website = _make_website()
        with pytest.raises(UserError):
            website.new_page(name='Sin plantilla')

    def test_sections_arch_lands_inside_the_wrap(self):
        website = _make_website()
        self._seed_template()
        result = website.new_page(
            name='Con secciones',
            sections_arch='<section class="s_104">hola</section>')
        view = IrUiView.objects.get(pk=result['view_id'])
        assert 's_104' in view.arch_db


class TestPageLifecycle:
    def test_delete_removes_the_orphan_view(self):
        website = _make_website()
        page = _make_page(website)
        view_pk = page.view_id
        page.delete()
        assert not IrUiView.objects.filter(pk=view_pk).exists()

    def test_save_on_url_change_syncs_menus(self):
        website = _make_website()
        page = _make_page(website, url='/vieja-url', key='website.vieja-url')
        WebsiteMenu.objects.create(
            name='Menú 104', route='/vieja-url', key=f'm104-{website.pk}',
            website=website, page=page)
        page.url = '/nueva-url'
        page.save()
        page.refresh_from_db()
        assert page.url == '/nueva-url'
        assert list(page.menu_ids.values_list('route', flat=True)) \
            == ['/nueva-url']


class TestPageSearch:
    def test_search_fetch_finds_by_delegated_name_and_url(self):
        website = _make_website()
        page = _make_page(
            website, url='/sobre-nosotros', key='website.sobre-nosotros',
            name='Sobre nosotros', is_published=True)
        detail = WebsitePage._search_get_detail(website, None, {})
        results, count = WebsitePage._search_fetch(detail, 'sobre', 5, None)
        assert count == 1 and results[0].pk == page.pk

    def test_unpublished_pages_stay_out_of_the_public_recipe(self):
        website = _make_website()
        _make_page(website, url='/oculta', key='website.oculta',
                   name='Oculta', is_published=False)
        detail = WebsitePage._search_get_detail(website, None, {})
        results, count = WebsitePage._search_fetch(detail, 'oculta', 5, None)
        assert (results, count) == ([], 0)


class TestPageInfo:
    def test_get_page_info_serves_the_reference_contract(self, rf):
        website = _make_website()
        page = _make_page(website, url='/acerca', key='website.acerca')
        info = WebsitePage._get_page_info(rf.get('/acerca'))
        assert info == {'id': page.pk, 'url': '/acerca',
                        'view_id': page.view_id, 'group_ids': []}

    def test_get_page_info_falls_back_to_case_insensitive(self, rf):
        website = _make_website()
        page = _make_page(website, url='/Acerca', key='website.acerca-mayus')
        info = WebsitePage._get_page_info(rf.get('/acerca'))
        assert info is not None and info['id'] == page.pk


class TestRewriteInvariant:
    def test_a_redirect_without_target_is_rejected(self):
        with pytest.raises(ValidationError):
            WebsiteRewrite.objects.create(
                name='Sin destino', url_from='/vieja', redirect_type='301')

    def test_a_308_cannot_point_to_the_homepage(self):
        with pytest.raises(ValidationError):
            WebsiteRewrite.objects.create(
                name='A la portada', url_from='/algo', url_to='/',
                redirect_type='308')

    def test_a_308_must_carry_the_from_parameters(self):
        with pytest.raises(ValidationError):
            WebsiteRewrite.objects.create(
                name='Parámetro perdido', url_from='/x/<id>', url_to='/y',
                redirect_type='308')

    def test_display_name_prefixes_the_redirect_type(self):
        rewrite = WebsiteRewrite.objects.create(
            name='Vieja a nueva', url_from='/vieja', url_to='/nueva',
            redirect_type='302')
        assert rewrite.display_name == '302 - Vieja a nueva'


class TestRouteCatalog:
    def test_refresh_populates_from_the_urlconf_and_is_idempotent(self):
        WebsiteRoute._refresh()
        first_count = WebsiteRoute.objects.count()
        assert first_count > 0
        WebsiteRoute._refresh()
        assert WebsiteRoute.objects.count() == first_count

    def test_name_search_returns_pairs_and_refreshes_when_empty(self):
        assert WebsiteRoute.objects.count() == 0
        result = WebsiteRoute.name_search(name='')
        assert result and all(len(pair) == 2 for pair in result)
