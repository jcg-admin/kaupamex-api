"""B3 (#536) — la búsqueda del sitio, sobre un universo controlado.

Cinco páginas estáticas con versión publicada (y una sin publicar, el control
negativo del ``base_domain``) bastan para ejercitar el bloque entero:
construcción del dominio, fetch con conteo, render con mapping, el despacho
fuzzy y los dos enumeradores. El enumerador por trigramas se salta solo si la
base no trae ``pg_trgm`` (la migración ``website/0005`` la instala; la sonda
es la misma ``has_trigram`` que usa el despacho).
"""
import pytest

from addons.base.models.res_company import ResCompany
from addons.base.models.res_users import ResUsers
from addons.website.models.mixins import (
    WebsiteSearchableMixin, order_expression_to_order_by,
)
from addons.website.models.static_page import StaticPage, StaticPageVersion
from addons.website.models.website import Website
from modules.db import FunctionStatus, has_trigram, has_unaccent
from orm.domains import Domain
from orm.environments import company_scope, connection
from tools.sql import escape_psql

pytestmark = pytest.mark.django_db


def _page(slug, title, published=True, content='contenido'):
    page = StaticPage.objects.create(slug=slug, title=title)
    StaticPageVersion.objects.create(
        page=page, version=1, content=content,
        status=(StaticPageVersion.STATUS_PUBLISHED if published
                else StaticPageVersion.STATUS_DRAFT))
    return page


@pytest.fixture
def search_universe(db):
    """El universo controlado: 4 publicadas + 1 borrador (control negativo)."""
    return {
        'about': _page('about', 'Acerca de nosotros'),
        'terms': _page('terms', 'Términos y condiciones'),
        'privacy': _page('privacy', 'Política de privacidad'),
        'returns': _page('returns', 'Política de devoluciones'),
        'faq': _page('faq', 'Preguntas frecuentes', published=False),
    }


@pytest.fixture
def website(db):
    """Un sitio mínimo — la búsqueda es lo probado, no la creación del sitio.

    ``company`` y ``user`` son NOT NULL (misma razón que documenta la fixture
    ``active_company`` de ``test_website_resolution.py``): la empresa entra por
    el ``default=`` bajo ``company_scope`` y el usuario público se suministra
    como lo suministra la data de la fuente.
    """
    company = ResCompany.objects.create(name='Kaupamex Search QA')
    user = (ResUsers.objects.filter(login='public@kaupamex.test').first()
            or ResUsers.objects.create_user(login='public@kaupamex.test'))
    with company_scope(company.pk):
        yield Website.objects.create(name='Tienda', sequence=10, user=user)


# ── piezas de soporte ───────────────────────────────────────────────────────

def test_escape_psql_escapes_the_three_wildcards():
    """≙ ``escape_psql`` — el texto del usuario se busca literal."""
    assert escape_psql('100%_off\\x') == r'100\%\_off\\x'


def test_order_expression_translates_to_order_by():
    assert order_expression_to_order_by('name asc, id desc') == ['name', '-id']
    assert order_expression_to_order_by(None) == []


def test_has_unaccent_reports_a_function_status():
    """La sonda devuelve un miembro del enum, sea cual sea el entorno."""
    with connection.cursor() as cr:
        assert has_unaccent(cr) in tuple(FunctionStatus)


# ── el detail y el dominio ──────────────────────────────────────────────────

def test_search_get_detail_names_the_published_recipe():
    detail = StaticPage._search_get_detail(None, None, {})
    assert detail['model'] is StaticPage
    assert detail['search_fields'] == ['title', 'slug']
    assert detail['mapping']['website_url'] == {
        'name': 'url', 'type': 'text', 'truncate': False}


def test_build_domain_ands_each_term_over_an_or_of_fields(search_universe):
    """Dos términos: cada uno debe aparecer en ALGÚN campo (AND de ORs)."""
    domain = WebsiteSearchableMixin._search_build_domain(
        [], 'política privacidad', ['title', 'slug'])
    results, count = StaticPage._search_fetch(
        {'search_fields': ['title', 'slug'], 'base_domain': [domain]},
        None, 10, None)
    assert count == 1
    assert results[0].slug == 'privacy'


def test_search_fetch_escapes_user_wildcards(search_universe):
    """Un ``%`` tecleado no es comodín: 0 resultados, no todos."""
    detail = StaticPage._search_get_detail(None, None, {})
    results, count = StaticPage._search_fetch(detail, '%', 10, None)
    assert count == 0 and results == []


def test_search_fetch_honors_base_domain_and_limit(search_universe):
    detail = StaticPage._search_get_detail(None, None, {})
    # 'Política' aparece en dos títulos publicados.
    results, count = StaticPage._search_fetch(detail, 'política', 10, None)
    assert count == 2
    # El borrador no entra aunque el término matchee.
    results, count = StaticPage._search_fetch(detail, 'preguntas', 10, None)
    assert count == 0
    # limit == len(resultados) → el conteo consulta el total real.
    results, count = StaticPage._search_fetch(detail, 'política', 1, None)
    assert len(results) == 1 and count == 2


# ── el flujo del sitio ──────────────────────────────────────────────────────

def test_search_exact_annotates_each_detail(website, search_universe):
    details = website._search_get_details('pages', None, {})
    total, all_results = website._search_exact(details, 'términos', 5, None)
    assert total == 1
    assert all_results[0]['count'] == 1
    assert all_results[0]['results'][0].slug == 'terms'


def test_search_render_results_applies_the_mapping(website, search_universe):
    details = website._search_get_details('pages', None, {})
    website._search_exact(details, 'acerca', 5, None)
    rendered = website._search_render_results(details, 5)
    row = rendered[0]['results_data'][0]
    assert row['title'] == 'Acerca de nosotros'
    assert row['url'] == '/pages/about'      # la property, vía getattr
    assert row['_fa'] == 'fa-file-o'
    assert row['_mapping'] is rendered[0]['mapping']


def test_search_with_fuzzy_exact_hit_reports_no_fuzzy_term(
        website, search_universe):
    count, results, fuzzy = website._search_with_fuzzy(
        'pages', 'privacidad', 5, None, {})
    assert count == 1 and fuzzy is False


def test_search_with_fuzzy_recovers_from_a_typo(website, search_universe):
    """'privasidad' no matchea exacto; el fuzzy devuelve la palabra real."""
    count, results, fuzzy = website._search_with_fuzzy(
        'pages', 'privasidad', 5, None, {})
    assert fuzzy == 'privacidad'
    assert count == 1
    assert results[0]['results'][0].slug == 'privacy'


def test_search_with_fuzzy_disabled_by_option(website, search_universe):
    count, results, fuzzy = website._search_with_fuzzy(
        'pages', 'privasidad', 5, None, {'allowFuzzy': False})
    assert count == 0 and fuzzy is False


# ── el término difuso y sus atajos ──────────────────────────────────────────

def test_fuzzy_shortcuts_return_the_search_untouched(website):
    """Los tres atajos verbatim: corto, frase, y 80 %+ dígitos."""
    assert website._search_find_fuzzy_term([], 'abc') == 'abc'
    assert website._search_find_fuzzy_term([], 'dos palabras') == 'dos palabras'
    assert website._search_find_fuzzy_term([], '12345678a9') == '12345678a9'


def test_fuzzy_term_prefers_the_most_similar_word(website):
    """Con word_list explícita no hay base de por medio: puntúa y elige."""
    found = website._search_find_fuzzy_term(
        [], 'devolusiones', word_list=['devoluciones', 'direcciones'])
    assert found == 'devoluciones'


def test_fuzzy_term_requires_the_same_first_letter(website):
    assert website._search_find_fuzzy_term(
        [], 'zapato', word_list=['sapato']) is None


# ── los enumeradores ────────────────────────────────────────────────────────

def test_basic_enumerate_words_yields_lowercase_candidates(
        website, search_universe):
    details = website._search_get_details('pages', None, {})
    words = set(website._basic_enumerate_words(details, 'polí', 100))
    assert 'política' in words
    # El borrador (no publicado) no aporta palabras.
    assert 'preguntas' not in words


def test_trigram_enumerate_words_uses_word_similarity(
        website, search_universe):
    with connection.cursor() as cr:
        if not has_trigram(cr):
            pytest.skip('pg_trgm ausente — el despacho degrada al básico')
    details = website._search_get_details('pages', None, {})
    words = set(website._trigram_enumerate_words(details, 'privasidad', 100))
    assert 'privacidad' in words
    assert 'preguntas' not in words          # el borrador queda fuera


# ── campos punteados ────────────────────────────────────────────────────────

def test_indirect_fields_resolve_the_reverse_relation(website):
    indirect = website._search_get_indirect_fields(
        ['title', 'versions.content'], StaticPage)
    assert list(indirect) == ['versions.content']
    info = indirect['versions.content']
    assert info['comodel'] is StaticPageVersion
    assert info['cofield'] == 'page'         # la FK de vuelta (≙ relation_field)


def test_indirect_fields_ignore_unknown_paths(website):
    assert website._search_get_indirect_fields(
        ['nope.title', 'title.too.deep', 'slug'], StaticPage) == {}


def test_search_text_from_html_keeps_technical_nodes():
    """El casi-homónimo del modelo NO poda ``script`` — contrato distinto."""
    text = Website._search_text_from_html(
        '<div>hola<script>x()</script></div>')
    assert 'hola' in text and 'x()' in text
