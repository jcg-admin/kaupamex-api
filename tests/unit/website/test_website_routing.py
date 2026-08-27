"""Contrato de la enumeración de páginas del modelo ``website`` (tarea **#545**).

Adaptación de ``odoo19c: addons/website/models/website.py`` (:1519-1544,
:1546-1668, :1714-1721, :1723-1768; ``odoo-tools@622ddc2a``, LGPL-3). Los
cuatro métodos recorrían el ``routing_map()`` werkzeug de la fuente; aquí el
mapa de rutas es la URLconf de Django, así que las pruebas montan una URLconf
propia (``pytest.mark.urls`` apunta a este mismo módulo) con una vista por
condición de la fuente:

- frontend literal (enumerable), backend (sin ``is_frontend``), excluida de
  sitemap (``sitemap = False``), con converter (sin protocolo ``generate``),
  regex (sin URL literal que construir), restringida a POST, con argumento
  requerido sin converter, con ``default_args``, y anidada por ``include``.

La mitad de páginas usa ``StaticPage`` (el análogo interino de
``website.page`` hasta #104) y su publicación por versión.
"""

import pytest
from django.http import HttpResponse
from django.urls import include, path, re_path
from django.views import View

from addons.base.models.res_company import ResCompany
from addons.base.models.res_users import ResUsers
from addons.website.models.static_page import StaticPage, StaticPageVersion
from addons.website.models.website import Website, _iter_url_patterns

pytestmark = [
    pytest.mark.django_db,
    # La URLconf bajo prueba es la de este módulo (``urlpatterns`` abajo) —
    # así la enumeración se mide contra un mapa conocido, no contra el del
    # proyecto entero.
    pytest.mark.urls('tests.unit.website.test_website_routing'),
]


# ── Las vistas del mapa de prueba ────────────────────────────────────────────

def home(request):
    return HttpResponse('')


home.is_frontend = True


def about(request):
    return HttpResponse('')


about.is_frontend = True


def hidden(request):
    return HttpResponse('')


hidden.is_frontend = True
hidden.sitemap = False


def item(request, item_id):
    return HttpResponse('')


item.is_frontend = True


def backend(request):
    return HttpResponse('')


def legacy(request):
    return HttpResponse('')


legacy.is_frontend = True


def needs_arg(request, slug):
    return HttpResponse('')


needs_arg.is_frontend = True


def with_default_arg(request, slug):
    return HttpResponse('')


with_default_arg.is_frontend = True


def deep(request):
    return HttpResponse('')


deep.is_frontend = True


class PostOnlyView(View):
    """CBV restringida a POST — el ``'GET' in methods`` de la fuente."""

    is_frontend = True
    http_method_names = ['post']

    def post(self, request):
        return HttpResponse('')


urlpatterns = [
    path('', home),
    path('about-us/', about),
    path('hidden/', hidden),
    path('item/<int:item_id>/', item),
    path('backend/', backend),
    re_path(r'^legacy/$', legacy),
    path('broken/', needs_arg),
    path('fixed/', with_default_arg, {'slug': 'inicio'}),
    path('post-only/', PostOnlyView.as_view()),
    path('inc/', include([path('deep/', deep)])),
    re_path(r'^rx/', include([path('deep-two/', deep)])),
]


def _make_website(**overrides):
    # ``company`` y ``user`` son NOT NULL en el modelo (cabecera de B1); el
    # fixture los aporta igual que ``test_website_b6``.
    values = {'name': 'Routing', 'domain': 'https://routing.example.test'}
    if 'company' not in overrides:
        values['company'] = ResCompany.objects.create(name='Kaupamex Routing QA')
    if 'user' not in overrides:
        existing = ResUsers.objects.filter(login='routing@kaupamex.test').first()
        values['user'] = existing or ResUsers.objects.create_user(
            login='routing@kaupamex.test')
    values.update(overrides)
    website = Website(**values)
    website.save()
    return website


def _rule_for(view_name):
    # El URLPattern hoja cuyo callback (o su clase) es la vista dada.
    for _route, rule, _literal in _iter_url_patterns():
        owner = (getattr(rule.callback, 'cls', None)
                 or getattr(rule.callback, 'view_class', None)
                 or rule.callback)
        if getattr(owner, '__name__', None) == view_name:
            return rule
    raise AssertionError('no URL rule found for view %s' % view_name)


class TestRuleIsEnumerable:
    """≙ ``rule_is_enumerable`` (``odoo19c: :1519-1544``), condición a condición."""

    def test_literal_frontend_route_is_enumerable(self):
        assert Website().rule_is_enumerable(_rule_for('about')) is True

    def test_route_without_frontend_declaration_is_not(self):
        # ≙ ``routing.get('website', False)`` — la vista no declara
        # ``is_frontend``.
        assert Website().rule_is_enumerable(_rule_for('backend')) is False

    def test_route_with_converters_is_not(self):
        # Sin protocolo ``generate`` en los converters de Django, una ruta
        # parametrizada no es enumerable (divergencia declarada).
        assert Website().rule_is_enumerable(_rule_for('item')) is False

    def test_regex_route_is_not(self):
        # ``re_path`` no produce una URL literal que construir.
        assert Website().rule_is_enumerable(_rule_for('legacy')) is False

    def test_view_restricted_to_post_is_not(self):
        # ≙ ``'GET' in methods``.
        assert Website().rule_is_enumerable(_rule_for('PostOnlyView')) is False

    def test_required_view_arg_without_converter_is_not(self):
        # ≙ el chequeo de firma de la fuente: argumento requerido sin
        # converter ni default.
        assert Website().rule_is_enumerable(_rule_for('needs_arg')) is False

    def test_default_args_of_the_pattern_count_as_provided(self):
        assert Website().rule_is_enumerable(
            _rule_for('with_default_arg')) is True

    def test_non_pattern_object_is_not_enumerable(self):
        assert Website().rule_is_enumerable(object()) is False


class TestEnumeratePages:
    """≙ ``_enumerate_pages`` (``odoo19c: :1546-1668``)."""

    def test_yields_only_enumerable_literal_frontend_routes(self):
        website = _make_website()
        locs = {record['loc'] for record in website._enumerate_pages()}
        assert locs == {'/', '/about-us', '/fixed', '/inc/deep'}

    def test_nested_route_behind_regex_prefix_is_excluded(self):
        # La cadena entera debe ser ``path()`` literal: un prefijo
        # ``re_path`` invalida la construcción de la URL.
        website = _make_website()
        locs = {record['loc'] for record in website._enumerate_pages()}
        assert not any('deep-two' in loc for loc in locs)

    def test_unpublished_static_page_needs_force(self):
        website = _make_website()
        page = StaticPage.objects.create(slug='faq', title='Preguntas frecuentes')
        default_locs = {r['loc'] for r in website._enumerate_pages()}
        forced_locs = {r['loc'] for r in website._enumerate_pages(force=True)}
        assert page.url not in default_locs
        assert page.url in forced_locs

    def test_published_static_page_is_yielded_with_its_metadata(self):
        website = _make_website()
        page = StaticPage.objects.create(slug='terms', title='Términos')
        StaticPageVersion.objects.create(
            page=page, version=1, content='<p>t</p>',
            status=StaticPageVersion.STATUS_PUBLISHED)
        records = {r['loc']: r for r in website._enumerate_pages()}
        record = records[page.url]
        assert record['id'] == page.pk
        assert record['name'] == 'Términos'
        assert record['lastmod'] == page.updated_at.date()

    def test_query_string_filters_by_url_fragment(self):
        website = _make_website()
        locs = [r['loc'] for r in website._enumerate_pages(
            query_string='about', force=True)]
        assert locs == ['/about-us']


class TestSearchPages:
    """≙ ``search_pages`` (``odoo19c: :1714-1721``)."""

    def test_needle_is_slugified_before_matching(self):
        website = _make_website()
        assert website.search_pages('About') == [{'loc': '/about-us'}]

    def test_limit_caps_the_results(self):
        website = _make_website()
        results = website.search_pages(limit=2)
        assert len(results) == 2

    def test_unmatched_needle_yields_nothing(self):
        website = _make_website()
        assert website.search_pages('no-such-needle') == []


class TestCheckExistingPage:
    """≙ ``check_existing_page`` (``odoo19c: :1723-1768``)."""

    def test_resolvable_route_exists(self):
        website = _make_website()
        assert website.check_existing_page('/about-us/') is True

    def test_unknown_path_does_not_exist(self):
        website = _make_website()
        assert website.check_existing_page('/no-such-page/') is False

    def test_static_page_counts_even_outside_the_urlconf(self):
        # El escalón 1 (registro de página) decide antes que el resolver.
        website = _make_website()
        page = StaticPage.objects.create(slug='privacy', title='Privacidad')
        assert website.check_existing_page(page.url) is True
