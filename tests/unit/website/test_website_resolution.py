"""Contrato de B2 — resolución del sitio actual (tarea **#535**).

Adaptación de ``odoo19c: addons/website/models/website.py`` (``odoo-tools@
622ddc2a``, LGPL-3). B2 declara 15 métodos; **6 están portados** y 9 bloqueados
con su sucesor registrado — la tabla vive en el docstring del módulo portado.
Este archivo ejercita los 6.

**Los casos salen de medir los binarios, no de imaginar entradas.** Cada
sección dice qué se midió y con qué comando, porque tres de los casos existen
sólo porque la medición los destapó:

1. ``python3 -c "'MiDominio.COM'.encode('idna')"`` → ``b'MiDominio.COM'``. El
   codec **no** normaliza mayúsculas (``/usr/lib/python3.12/encodings/idna.py``),
   así que el ``.lower()`` de la comparación es lo único que hace insensible el
   emparejamiento. Sin ese caso, quitar el ``.lower()`` no rompería ningún test.
2. ``RequestFactory().get('/')`` → ``META.get('HTTP_HOST')`` es **None**, no
   cadena vacía (Django 6.0.5). De ahí el caso sin ``Host``.
3. ``hasattr(request, 'session')`` sobre una petición de ``RequestFactory`` es
   **False** hasta que corre ``SessionMiddleware``. De ahí que los tres casos de
   sesión la instalen explícitamente, y que exista el caso sin sesión: es el
   estado real de un cron.
"""

import pytest
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory

from addons.base.models.ir_http import get_current_request, set_current_request
from addons.base.models.res_company import ResCompany
from addons.base.models.res_users import ResUsers
from addons.portal.controllers.portal import pager
from addons.website.models.website import Website
from addons.website.tools import get_base_domain
from orm.environments import company_scope, context_scope

pytestmark = [pytest.mark.django_db]


@pytest.fixture(autouse=True)
def active_company():
    """Una empresa activada en el entorno, porque ``company`` es obligatorio.

    Es ``autouse`` a propósito: **ningún** sitio se puede crear sin empresa
    (``required=True`` en la fuente y ``NOT NULL`` aquí), así que una prueba que
    la olvidara fallaría con un ``IntegrityError`` que no dice nada del caso que
    quería probar.

    Y activa la empresa en el contexto en vez de pasarla a cada ``create``, para
    que los ``create`` de abajo **ejerciten el ``default=``** del campo — que es
    ``env.company`` en la fuente y ``get_current_company`` aquí. Pasarla a mano
    dejaría ese default sin un solo test.
    """
    company = ResCompany.objects.create(name='Kaupamex QA')
    with company_scope(company.pk):
        yield company


def _public_user():
    """El usuario público del sitio — ≙ ``base.public_user`` de la referencia.

    ``user`` es ``required=True`` en la fuente y **no lleva ``default=``**
    (``odoo19c: website.py:193``): quien crea el sitio lo suministra. Allá lo
    suministra la data del addon, que lo apunta a ``base.public_user``
    (``odoo19c: addons/website/data/website_data.xml:527``). Ese seed aún no
    existe en este árbol —es de #104—, así que aquí se materializa una vez por
    prueba en vez de repetirlo en cada ``create``.
    """
    existing = ResUsers.objects.filter(login='public@kaupamex.test').first()
    # ``create_user`` y no ``get_or_create``: el manager es quien crea el
    # ``res.partner`` que la credencial exige (``partner`` es NOT NULL), y
    # saltárselo produce un ``IntegrityError`` que no habla del caso probado.
    return existing or ResUsers.objects.create_user(login='public@kaupamex.test')


def _site(**kwargs):
    """Crea un sitio suministrando lo que la data de la fuente suministra.

    Sólo rellena ``user``; la empresa la pone su ``default=`` desde el contexto
    que fija ``active_company``, y los idiomas los pone ``save()``. Rellenar más
    dejaría esos dos mecanismos sin ejercitar.
    """
    kwargs.setdefault('user', _public_user())
    return Website.objects.create(**kwargs)


def _request(host=None, with_session=False):
    """Una petición como la que llega al middleware, con lo que se pida.

    ``RequestFactory`` no instala sesión (medido: ``hasattr(r, 'session')`` es
    ``False``), así que el que la necesite la pide y aquí se corre el
    ``SessionMiddleware`` real — no un doble de prueba, que es lo que
    escondería un cambio de contrato de Django.
    """
    factory = RequestFactory()
    request = factory.get('/', **({'HTTP_HOST': host} if host else {}))
    if with_session:
        SessionMiddleware(lambda req: None).process_request(request)
    return request


@pytest.fixture
def clean_request_context():
    """Deja el ``ContextVar`` de petición como estaba — pase lo que pase.

    Sin esto una prueba que falle a mitad dejaría la petición fijada y la
    siguiente heredaría su sitio: exactamente la fuga entre peticiones que el
    ``ContextVar`` existe para impedir bajo WSGI.
    """
    yield
    set_current_request(None)


# ── get_base_domain ─────────────────────────────────────────────────────────

@pytest.mark.parametrize('given,expected', [
    ('', ''),
    ('https://www.midominio.com/', 'www.midominio.com'),
    ('http://localhost:8000', 'localhost:8000'),
    ('https://WWW.Midominio.com', 'WWW.Midominio.com'),
    # Sin esquema NO hay netloc: todo cae en `path`. Medido con
    # `urlsplit('midominio.com/x').netloc` -> ''. La fuente hereda lo mismo de
    # `url_parse`, y el llamador trata la cadena vacía como "sin dominio".
    ('midominio.com/x', ''),
])
def test_get_base_domain_returns_the_netloc(given, expected):
    """≙ ``get_base_domain`` (``odoo19c: addons/website/tools.py:96-112``).

    El puerto **se conserva** y las mayúsculas **también**: quien compara es
    quien decide si importan. Es lo que permite que
    ``_get_current_website_id`` intente primero con puerto y luego sin él.
    """
    assert get_base_domain(given) == expected


def test_get_base_domain_strips_www_only_when_asked():
    """``strip_www`` es opcional y por defecto NO actúa."""
    assert get_base_domain('https://www.midominio.com') == 'www.midominio.com'
    assert get_base_domain('https://www.midominio.com', strip_www=True) == 'midominio.com'


# ── _get_current_website_id ─────────────────────────────────────────────────

def test_matches_the_site_whose_domain_equals_the_host():
    """El emparejamiento exacto, que es el caso normal."""
    # El señuelo va con ``sequence`` MENOR a propósito: es quien ganaría si el
    # emparejamiento fallara y la resolución cayera al fallback. Sin él este
    # test pasa aunque el emparejamiento esté roto — y pasó: la primera versión
    # daba verde con ``domain_punycode`` devolviendo ``None`` (:ref:`h-api-697`).
    _site(name='Señuelo', domain='https://otro.example', sequence=1)
    store = _site(name='Tienda', domain='https://tienda.example', sequence=99)

    assert Website._get_current_website_id('tienda.example') == store.pk


def test_the_host_match_is_case_insensitive():
    """El caso que sólo existe porque se midió el codec.

    ``'MiDominio.COM'.encode('idna')`` devuelve ``b'MiDominio.COM'`` — el codec
    no baja a minúsculas. Si el ``.lower()`` de la comparación desapareciera,
    este es el único test que se pondría rojo.
    """
    _site(name='Señuelo', domain='https://otro.example', sequence=1)
    store = _site(name='Tienda', domain='https://Tienda.Example', sequence=99)

    assert Website._get_current_website_id('TIENDA.EXAMPLE') == store.pk


def test_a_subdomain_does_not_match_the_parent_domain():
    """El filtro exacto tras el ``ilike``, que es para lo que está.

    La consulta a la base usa ``icontains`` para acotar; sin el filtro posterior
    ``mala-tienda.example`` entraría por contener ``tienda.example``.
    """
    _site(name='Tienda', domain='https://tienda.example')

    assert Website._get_current_website_id('mala-tienda.example', fallback=False) is False


def test_the_port_is_ignored_on_the_second_pass():
    """Un sitio declarado sin puerto responde a una petición con puerto.

    Es la segunda vuelta de la fuente, y es lo que hace que el desarrollo en
    ``localhost:8000`` funcione contra un sitio configurado como ``localhost``.
    """
    _site(name='Señuelo', domain='https://otro.example', sequence=1)
    localsite = _site(name='Local', domain='http://localhost', sequence=99)

    assert Website._get_current_website_id('localhost:8000') == localsite.pk


def test_falls_back_to_the_first_site_by_sequence():
    """Sin coincidencia y con ``fallback``, el primero — por ``sequence``."""
    _site(name='Segundo', domain='https://b.example', sequence=20)
    first = _site(name='Primero', domain='https://a.example',
                                     sequence=10)

    assert Website._get_current_website_id('nada-que-ver.example') == first.pk


def test_without_fallback_an_unmatched_host_returns_false():
    """``False``, no ``None``: es el valor que la fuente documenta y devuelve."""
    _site(name='Tienda', domain='https://tienda.example')

    assert Website._get_current_website_id('nada.example', fallback=False) is False


def test_a_punycode_host_matches_a_unicode_domain():
    """Las dos formas del mismo dominio, que es para lo que está el doble intento.

    Medido: ``'münchen.de'.encode('idna')`` → ``b'xn--mnchen-3ya.de'``, y el
    camino inverso también resuelve. Un navegador puede mandar cualquiera de
    las dos.
    """
    _site(name='Señuelo', domain='https://otro.example', sequence=1)
    munich = _site(name='München', domain='https://münchen.de', sequence=99)

    assert Website._get_current_website_id('xn--mnchen-3ya.de') == munich.pk


# ── get_current_website: los cuatro escalones, en orden ─────────────────────

def test_the_session_forced_site_wins_over_the_host(clean_request_context):
    """Escalón 1. El conmutador del administrador gana sobre el dominio.

    Es el orden de la fuente y no es indiferente: un administrador que fuerza
    un sitio lo hace **desde** el dominio de otro.
    """
    store = _site(name='Tienda', domain='https://tienda.example')
    forced = _site(name='Forzado', domain='https://forzado.example')

    request = _request(host='tienda.example', with_session=True)
    request.session['force_website_id'] = forced.pk
    set_current_request(request)

    assert Website.get_current_website().pk == forced.pk


def test_a_deleted_forced_site_is_dropped_from_the_session(clean_request_context):
    """Escalón 1, rama de borrado — la fuente hace ``session.pop`` y sigue.

    Sin esta rama, borrar un sitio dejaría la sesión apuntando a un id muerto y
    **cada** petición de ese usuario reventaría hasta que cerrara sesión.
    """
    store = _site(name='Tienda', domain='https://tienda.example')

    request = _request(host='tienda.example', with_session=True)
    request.session['force_website_id'] = 999999
    set_current_request(request)

    assert Website.get_current_website().pk == store.pk
    assert 'force_website_id' not in request.session


def test_the_context_site_wins_when_there_is_no_session(clean_request_context):
    """Escalón 2 — ``env.context['website_id']`` de la fuente.

    Es la vía de un cron o de una llamada interna que ya sabe sobre qué sitio
    opera. Aquí el contexto es el ``ContextVar`` de ``orm.environments``, el
    tercer eje del entorno.
    """
    _site(name='Tienda', domain='https://tienda.example')
    other = _site(name='Otro', domain='https://otro.example')

    set_current_request(_request(host='tienda.example'))
    with context_scope(website_id=other.pk):
        assert Website.get_current_website().pk == other.pk


def test_resolves_by_host_when_there_is_no_session_or_context(clean_request_context):
    """Escalón 3 — el ``Host`` de la petición."""
    _site(name='Otro', domain='https://otro.example', sequence=1)
    store = _site(name='Tienda', domain='https://tienda.example',
                                    sequence=99)

    set_current_request(_request(host='tienda.example'))

    assert Website.get_current_website().pk == store.pk


def test_without_a_request_it_still_falls_back(clean_request_context):
    """Escalón 4 sin petición ninguna — el caso del cron.

    Medido: ``RequestFactory().get('/')`` no trae ``HTTP_HOST`` (es ``None``) y
    tampoco trae sesión. Un cron no trae ni petición. La resolución no puede
    reventar por eso, porque el mismo código corre en los dos sitios.
    """
    first = _site(name='Primero', domain='https://a.example')

    set_current_request(None)

    assert Website.get_current_website().pk == first.pk


def test_no_fallback_outside_a_frontend_request_returns_none(clean_request_context):
    """La rama que devuelve vacío antes de mirar el ``Host``.

    **Este test fija una divergencia medida, no una conducta deseada.** La
    fuente sólo entra aquí en peticiones de backend, porque su despachador
    marca ``request.is_frontend``. Medido sobre Django 6.0.5: ``HttpRequest``
    no tiene ese atributo y nada en este árbol lo pone, así que la rama se
    dispara **siempre** que ``fallback=False``. Sucesor: **#546**.

    Se prueba para que el día que #546 marque la petición, este test se ponga
    rojo y obligue a revisar la expectativa — que es justo lo que un test que
    pinta una divergencia debe hacer.
    """
    _site(name='Tienda', domain='https://tienda.example')

    set_current_request(_request(host='tienda.example'))

    assert Website.get_current_website(fallback=False) is None


# ── _force / _force_website ─────────────────────────────────────────────────

def test_force_writes_the_site_into_the_session(clean_request_context):
    """``_force`` es la puerta del escalón 1: escribe lo que aquél lee."""
    store = _site(name='Tienda', domain='https://tienda.example')
    request = _request(with_session=True)
    set_current_request(request)

    store._force()

    assert request.session['force_website_id'] == store.pk
    assert Website.get_current_website().pk == store.pk


def test_a_non_numeric_forced_id_does_not_land_in_the_session(clean_request_context):
    """La guarda ``isdigit`` de la fuente, que no es decorativa.

    El valor entra desde un parámetro de URL. Sin la guarda, ``?website_id=x``
    dejaría basura en la sesión y el escalón 1 la consultaría en cada petición.
    """
    request = _request(with_session=True)
    set_current_request(request)

    Website._force_website('no-soy-un-numero')

    assert request.session['force_website_id'] is False


def test_forcing_without_a_session_does_not_explode(clean_request_context):
    """Sin sesión no hay dónde escribir, y eso no es un error.

    Medido: una petición de ``RequestFactory`` sin ``SessionMiddleware`` no
    tiene ``.session``. Un cron tampoco. La fuente guarda con ``if request``;
    aquí se guarda con ``getattr(request, 'session', None)``.
    """
    set_current_request(_request())

    Website._force_website(1)  # no debe levantar


# ── is_public_user ──────────────────────────────────────────────────────────

def test_is_public_user_is_false_when_the_site_declares_no_user(clean_request_context):
    """Sin ``user`` configurado no hay usuario público que reconocer.

    Devolver ``False`` —y no reventar— es lo que permite que un sitio recién
    creado, todavía sin configurar, sirva peticiones.
    """
    _site(name='Tienda', domain='https://tienda.example')
    set_current_request(_request(host='tienda.example'))

    assert Website.is_public_user() is False


# ── pager ───────────────────────────────────────────────────────────────────

def test_pager_computes_pages_and_offset():
    """≙ ``pager`` (``odoo19c: addons/portal/controllers/portal.py:22-93``).

    El ``offset`` es lo que el llamador usa para cortar el queryset; que sea
    ``(page-1)*step`` y no ``page*step`` es la diferencia entre mostrar la
    página pedida y mostrar la siguiente.
    """
    resultado = pager('/tienda', total=95, page=2, step=30)

    assert resultado['page_count'] == 4
    assert resultado['offset'] == 30
    assert resultado['page'] == {'url': '/tienda/page/2', 'num': 2}
    assert resultado['page_first']['url'] == '/tienda'


def test_pager_clamps_a_page_out_of_range():
    """Una página fuera de rango se recorta, no devuelve vacío.

    ``max(1, min(page, page_count))`` de la fuente. Importa porque el número de
    página llega de la URL: ``?page=9999`` debe mostrar la última, no un 500 ni
    una lista vacía.
    """
    assert pager('/x', total=10, page=99, step=30)['page']['num'] == 1
    assert pager('/x', total=100, page=0, step=30)['page']['num'] == 1


def test_pager_inserts_ellipsis_only_when_it_does_not_fit():
    """La lógica de elipsis, que la fuente añadió por SEO.

    Con pocas páginas se listan todas; con muchas aparecen la primera y la
    última **siempre**, que es lo que permite a un rastreador alcanzar el fondo
    del catálogo sin recorrer página por página.
    """
    corto = [p['num'] for p in pager('/x', total=100, step=30)['pages']]
    assert corto == [1, 2, 3, 4]

    largo = [p['num'] for p in pager('/x', total=1000, page=10, step=30)['pages']]
    assert largo == [1, '…', 9, 10, 11, '…', 34]
    assert largo[0] == 1 and largo[-1] == 34


def test_pager_appends_url_args_as_query_string():
    """Los filtros vigentes sobreviven al cambio de página."""
    resultado = pager('/tienda', total=100, page=2, step=30,
                      url_args={'categoria': 'velas'})

    assert resultado['page']['url'] == '/tienda/page/2?categoria=velas'


# ── el ContextVar de la petición ────────────────────────────────────────────

def test_the_request_context_var_is_none_outside_a_request():
    """Fuera de petición devuelve ``None``, no levanta — el caso del cron.

    Es la conducta de la fuente: ``website.py`` escribe ``if request and …`` una
    y otra vez porque el mismo código corre bajo WSGI y bajo el cron.
    """
    set_current_request(None)

    assert get_current_request() is None
