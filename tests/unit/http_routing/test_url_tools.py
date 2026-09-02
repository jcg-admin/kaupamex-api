"""``url_rewrite``, ``_is_multilang_url``, ``_url_lang``/``_url_for`` y el entorno de plantilla.

Es la mitad del porte que no toca el slug: las utilidades que en la fuente se
apoyan en ``werkzeug.routing`` y aquí en ``django.urls``. Se miden contra la
URLconf **real** del proyecto —no un doble— porque lo que se quiere saber es
que el sustituto de ``MapAdapter.match`` resuelve de verdad.

Que estos casos existan es consecuencia de haberlos escrito: el primer intento
de ``url_rewrite`` llevaba el decorador ``@ormcache`` de la fuente y reventaba
con ``AttributeError: 'str' object has no attribute '_name'`` en la primera
llamada, porque su clave evalúa ``<primer_parámetro>._name`` y
``base.IrHttp`` todavía no declara ``_name``. Ningún gate estático lo vio.
"""
import pytest

from addons.base.models.ir_http import IrHttp
from addons.base.models.ir_template_expressions import IrTemplateExpressions
from addons.base.models.res_lang import ResLang
from addons.http_routing.models import ir_http as mod
from orm.registry import cache_of

#: Una ruta que la URLconf del proyecto declara de verdad, sin parámetros.
#: Si desapareciera, estos casos fallarían en vez de pasar en falso.
REAL_PATH = '/api/v2/notifications/'


class TestUrlRewriteResolvesAgainstTheRealUrlconf:
    """Falla si ``resolve`` no estuviera ocupando el sitio de ``MapAdapter.match``."""

    def test_an_existing_path_gives_its_endpoint(self):
        url, endpoint = IrHttp.url_rewrite(REAL_PATH)
        assert url == REAL_PATH
        assert endpoint is not None

    def test_an_unknown_path_gives_itself_and_no_endpoint(self):
        assert IrHttp.url_rewrite('/no/existe/') == ('/no/existe/', None)

    def test_the_missing_trailing_slash_is_the_append_slash_rewrite(self):
        # ≙ ``werkzeug.routing.RequestRedirect``: la reescritura que el
        # resolutor provoca por sí mismo.
        url, endpoint = IrHttp.url_rewrite(REAL_PATH.rstrip('/'))
        assert url == REAL_PATH
        assert endpoint is not None

    def test_the_second_call_comes_from_the_cache(self):
        IrHttp.url_rewrite('/otro/que/no/existe/')
        key = (mod._REWRITE_MODEL_NAME, mod.url_rewrite, '/otro/que/no/existe/', None)
        assert key in cache_of('routing.rewrites')

    def test_query_args_is_part_of_the_key(self):
        # Discrimina: si la clave ignorara ``query_args``, las dos entradas
        # serían la misma y este caso pasaría con una caché mal indexada.
        IrHttp.url_rewrite('/con/qs/', query_args='a=1')
        cache = cache_of('routing.rewrites')
        con = (mod._REWRITE_MODEL_NAME, mod.url_rewrite, '/con/qs/', 'a=1')
        sin = (mod._REWRITE_MODEL_NAME, mod.url_rewrite, '/con/qs/', None)
        assert con in cache and sin not in cache


@pytest.mark.django_db
class TestIsMultilangUrl:
    """Las dos exclusiones de la fuente, y la lectura de la declaración de la vista.

    Marcada ``django_db`` porque ``_is_multilang_url`` lee el catálogo de
    idiomas activos, igual que la fuente: la lista de ``url_code`` es lo que
    le permite quitar el prefijo de idioma antes de mirar la ruta.
    """

    @pytest.mark.parametrize('path', ['/web/algo', '/a/static/b.css'])
    def test_web_and_static_are_never_translated(self, path):
        assert IrHttp._is_multilang_url(path) is False

    def test_a_backend_endpoint_is_not_translated(self):
        assert IrHttp._is_multilang_url(REAL_PATH) is False

    def test_a_path_with_no_endpoint_is_translated(self, monkeypatch):
        # ≙ "/page/xxx has no endpoint/func but is multilang" de la fuente.
        monkeypatch.setattr(mod, 'url_rewrite',
                            lambda cls, path, query_args=None: (path, None))
        assert IrHttp._is_multilang_url('/pagina/libre') is True

    def test_a_frontend_multilang_endpoint_is_translated(self, monkeypatch):
        def view(request):
            return None

        view.is_frontend = True
        monkeypatch.setattr(mod, 'url_rewrite',
                            lambda cls, path, query_args=None: (path, view))
        assert IrHttp._is_multilang_url('/shop') is True

    def test_the_same_endpoint_declaring_multilang_false_is_not(self, monkeypatch):
        # Discrimina: aísla la lectura de ``multilang`` de la de ``website``.
        def view(request):
            return None

        view.is_frontend = True
        view.is_frontend_multilang = False
        monkeypatch.setattr(mod, 'url_rewrite',
                            lambda cls, path, query_args=None: (path, view))
        assert IrHttp._is_multilang_url('/shop') is False


@pytest.mark.django_db
class TestUrlLangLeavesAloneWhatItMust:
    """Nada se hace con una URL absoluta, ni con un solo idioma instalado.

    ``django_db`` por la misma razón que la clase de arriba.
    """

    def test_an_absolute_url_is_untouched(self):
        assert IrHttp._url_for('https://example.com/x') == 'https://example.com/x'

    def test_a_relative_path_with_one_installed_lang_is_untouched(self):
        assert IrHttp._url_for(REAL_PATH) == REAL_PATH

    def test_an_invalid_url_does_not_raise(self):
        # ≙ el ``except ValueError`` de la fuente (IPv6 inválida).
        assert IrHttp._url_for('http://]') == 'http://]'


class TestTheTemplateEnvironment:
    """``ir.qweb`` publica los nombres con que una plantilla construye enlaces."""

    def test_slug_and_unslug_url_are_published_always(self):
        values = {}
        qweb = IrTemplateExpressions()
        assert qweb._prepare_environment(values) is qweb
        assert values['slug'] == IrHttp._slug
        assert values['unslug_url'] == IrHttp._unslug_url

    def test_the_published_slug_is_the_readable_one(self):
        # Discrimina: publicar ``base.slug`` daría '42' y pasaría el caso de
        # arriba igual, porque aquél sólo compara identidad de función.
        values = {}
        IrTemplateExpressions()._prepare_environment(values)
        assert values['slug']((42, 'Silla de Oficina')) == 'silla-de-oficina-42'

    def test_the_frontend_only_names_are_not_published_by_default(self):
        values = {}
        IrTemplateExpressions()._prepare_environment(values)
        assert 'url_for' not in values and 'url_localized' not in values

    def test_the_frontend_environment_adds_the_two_url_builders(self):
        values = {}
        qweb = IrTemplateExpressions()
        assert qweb._prepare_frontend_environment(values) is qweb
        assert values['url_for'] == IrHttp._url_for
        assert values['url_localized'] == IrHttp._url_localized


class TestTheFrontendLangsCatalogue:
    """``res.lang._get_frontend`` — los activos indexados por código."""

    @pytest.mark.django_db
    def test_only_active_langs_are_listed(self):
        catalogue = ResLang._get_frontend()
        assert all(lang.active for lang in catalogue.values())
        assert all(code == lang.code for code, lang in catalogue.items())

    @pytest.mark.django_db
    def test_an_inactive_lang_is_absent(self):
        # Discrimina: sin el filtro ``active=True`` el catálogo traería los
        # cientos de idiomas sembrados y esta afirmación caería.
        inactive = ResLang.objects.filter(active=False).first()
        if inactive is None:
            pytest.skip('no hay idioma inactivo sembrado que discrimine')
        assert inactive.code not in ResLang._get_frontend()
