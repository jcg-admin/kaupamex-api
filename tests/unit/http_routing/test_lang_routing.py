"""``_match`` y las utilidades de idioma — las nueve ramas de la fuente.

``_match`` devuelve la decisión (``(respuesta_o_None, path)``) en vez de
abortar con una excepción; por eso se puede medir sin levantar un servidor y
sin tocar la base. Los idiomas se inyectan con ``monkeypatch`` sobre
``ResLang._get_frontend`` y ``_get_default_lang``: lo que estos casos miden es
la **decisión de enrutado**, no el catálogo de idiomas.

Cada clase declara qué la haría fallar.
"""
import pytest
from django.test import RequestFactory

from addons.base.models.ir_http import IrHttp, set_current_request
from addons.http_routing.models import ir_http as mod


class _Lang:
    def __init__(self, code, url_code):
        self.code = code
        self.url_code = url_code

    def __eq__(self, other):
        return isinstance(other, _Lang) and self.code == other.code

    def __hash__(self):
        return hash(self.code)


EN = _Lang('en_US', 'en')
FR = _Lang('fr_FR', 'fr')
FR_BE = _Lang('fr_BE', 'fr_BE')


@pytest.fixture
def langs(monkeypatch):
    """Tres idiomas activos, ``en_US`` por defecto."""
    catalog = {'en_US': EN, 'fr_FR': FR, 'fr_BE': FR_BE}
    monkeypatch.setattr(mod.ResLang, '_get_frontend', classmethod(lambda cls: catalog))
    monkeypatch.setattr(mod, '_get_default_lang', lambda cls: EN)
    by_url = {lang.url_code: lang for lang in catalog.values()}

    class _Objects:
        def filter(self, **kw):
            self._hit = by_url.get(kw.get('url_code')) or catalog.get(kw.get('code'))
            return self

        def first(self):
            return self._hit

    monkeypatch.setattr(mod.ResLang, 'objects', _Objects())
    return catalog


@pytest.fixture
def frontend_view(monkeypatch):
    """Una vista despachable declarada de sitio y multilingüe.

    El ``resolve`` falso **levanta** ``Resolver404`` ante una ruta con prefijo
    de idioma, que es lo que hace el de Django: la URLconf no declara
    ``/fr/shop``, sólo ``/shop``. Sin esa mitad el doble no discrimina las
    ramas 6-9, que son precisamente las que dependen de que la primera
    resolución falle.
    """
    def view(request):
        return None

    view.is_frontend = True

    class _Match:
        func = view
        view_name = 'shop'
        args = ()
        kwargs = {}

    prefixes = tuple(f'/{code}/' for code in ('en', 'fr', 'fr_FR', 'fr_BE'))

    def _resolve(path):
        if path.startswith(prefixes) or path in tuple(p[:-1] for p in prefixes):
            raise mod.Resolver404({'path': path})
        return _Match()

    monkeypatch.setattr(mod, 'resolve', _resolve)
    return view


def _request(path, method='GET', cookies=None, user_agent=''):
    request = RequestFactory().generic(method, path)
    request.COOKIES.update(cookies or {})
    request.META['HTTP_USER_AGENT'] = user_agent
    request.is_frontend = False
    set_current_request(request)
    return request


@pytest.fixture(autouse=True)
def _clear_request():
    yield
    set_current_request(None)


class TestBranch1ANonFrontendEndpointIsLeftAlone:
    """Falla si ``_match`` reescribiera URLs de backend."""

    def test_a_backend_view_returns_the_path_unchanged(self, langs, monkeypatch):
        def view(request):
            return None

        class _Match:
            func = view
            view_name = 'api'
            args = ()
            kwargs = {}

        monkeypatch.setattr(mod, 'resolve', lambda path: _Match())
        request = _request('/api/v2/orders/')
        assert IrHttp._match('/api/v2/orders/') == (None, '/api/v2/orders/')
        assert request.is_frontend is False


class TestBranch2NoLangAndDefaultLangContinues:
    """Falla si se inyectara el idioma por defecto en la URL."""

    def test_the_path_is_untouched(self, langs, frontend_view):
        _request('/shop')
        response, path = IrHttp._match('/shop')
        assert (response, path) == (None, '/shop')


class TestBranch3ABotKeepsTheUrlAsIs:
    """Falla si un bot recibiera un 302 al idioma de su cookie."""

    def test_a_bot_is_not_redirected(self, langs, frontend_view):
        request = _request('/shop', cookies={'frontend_lang': 'fr_FR'},
                           user_agent='Googlebot/2.1')
        response, path = IrHttp._match('/shop')
        assert (response, path) == (None, '/shop')
        assert request.lang == EN

    def test_the_same_request_without_the_bot_agent_is_redirected(
            self, langs, frontend_view):
        # Discrimina: el control que aísla la rama del bot de la rama /5.
        _request('/shop', cookies={'frontend_lang': 'fr_FR'})
        response, __ = IrHttp._match('/shop')
        assert response is not None and response['Location'] == '/fr/shop'


class TestBranch4APostIsNotRedirected:
    """Falla si un POST perdiera su cuerpo en un 302."""

    def test_a_post_without_lang_continues(self, langs, frontend_view):
        _request('/shop', method='POST', cookies={'frontend_lang': 'fr_FR'})
        response, path = IrHttp._match('/shop')
        assert (response, path) == (None, '/shop')


class TestBranch5TheRequestedLangIsInjected:
    """``/home`` con cookie ``fr_FR`` a ``/fr/home``."""

    def test_the_lang_is_prefixed(self, langs, frontend_view):
        _request('/home', cookies={'frontend_lang': 'fr_FR'})
        response, __ = IrHttp._match('/home')
        assert response.status_code == 302
        assert response['Location'] == '/fr/home'

    def test_the_redirect_carries_the_cookie(self, langs, frontend_view):
        _request('/home', cookies={'frontend_lang': 'fr_FR'})
        response, __ = IrHttp._match('/home')
        assert response.cookies['frontend_lang'].value == 'fr_FR'


class TestBranch6TheDefaultLangIsRemoved:
    """``/en/home`` a ``/home`` — dos URLs para el mismo recurso es el defecto."""

    def test_the_default_lang_prefix_is_dropped(self, langs, frontend_view):
        _request('/en/home')
        response, __ = IrHttp._match('/en/home')
        assert response['Location'] == '/home'


class TestBranch7AnAliasBecomesThePreferredUrlCode:
    """``/fr_FR/home`` a ``/fr/home``, y con 301 porque es permanente."""

    def test_the_alias_is_rewritten(self, langs, frontend_view):
        _request('/fr_FR/home')
        response, __ = IrHttp._match('/fr_FR/home')
        assert (response.status_code, response['Location']) == (301, '/fr/home')


class TestBranch8TheHomepageLosesItsTrailingSlash:
    """``/fr_BE/`` a ``/fr_BE`` — 301."""

    def test_the_trailing_slash_is_dropped(self, langs, frontend_view):
        _request('/fr_BE/')
        response, __ = IrHttp._match('/fr_BE/')
        assert (response.status_code, response['Location']) == (301, '/fr_BE')


class TestBranch9AValidLangIsRewrittenAway:
    """``/fr/home`` sigue sirviendo ``/home`` — sin redirección."""

    def test_the_path_is_rewritten_not_redirected(self, langs, frontend_view):
        request = _request('/fr/home', cookies={'frontend_lang': 'fr_FR'})
        response, path = IrHttp._match('/fr/home')
        assert response is None
        assert path == '/home'
        assert request.lang == FR


class TestTheDoubleSlashIsMerged:
    """Dos URLs concatenadas dejan ``//``; la fuente lo funde con un 301."""

    def test_it_is_merged_permanently(self, langs, frontend_view):
        _request('/shop//product')
        response, __ = IrHttp._match('/shop//product')
        assert (response.status_code, response['Location']) == (301, '/shop/product')


class TestTheReentryGuard:
    """Falla si ``_match`` reescribiera dos veces la misma petición."""

    def test_the_second_call_is_a_no_op(self, langs, frontend_view):
        _request('/home', cookies={'frontend_lang': 'fr_FR'})
        first, __ = IrHttp._match('/home')
        second, path = IrHttp._match('/home')
        assert first is not None
        assert (second, path) == (None, '/home')


class TestGetNearestLang:
    """``fr_BE`` cae en ``fr_FR`` cuando aquél no está activo."""

    def test_an_exact_code_is_kept(self, langs):
        assert IrHttp.get_nearest_lang('fr_FR') == 'fr_FR'

    def test_a_sibling_falls_back_to_the_same_short_code(self, langs, monkeypatch):
        monkeypatch.setattr(mod.ResLang, '_get_frontend',
                            classmethod(lambda cls: {'fr_FR': FR}))
        assert IrHttp.get_nearest_lang('fr_CA') == 'fr_FR'

    @pytest.mark.parametrize('value', [None, '', 'zz_ZZ'])
    def test_what_has_no_neighbour_gives_nothing(self, langs, value):
        assert IrHttp.get_nearest_lang(value) is None


class TestTheTranslationModuleHooks:
    """Los dos puntos de extensión que la fuente deja para que otro los llene."""

    def test_the_domain_starts_empty(self):
        assert IrHttp._get_translation_frontend_modules_domain() == []

    def test_web_is_the_module_the_source_names(self):
        assert IrHttp._get_translation_frontend_modules_name() == ['web']
