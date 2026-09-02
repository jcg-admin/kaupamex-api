"""``IrHttp`` de ``web`` — el único eslabón que este addon cuelga sobre
``base.IrHttp``: detección de bots, y NADA más.

Discrimina el estado que ``models/ir_http.py`` declara (Tarea #250,
re-verificación 2026-09-02): ``is_a_bot``/``bots`` es lo único portado; los
diez símbolos restantes de la referencia se declinan con razón medida, y en
particular ``_sanitize_cookies`` (cookie ``cids`` de compañías activas) no
tiene contraparte porque este árbol no selecciona compañía por cookie —
``CompanyContextMiddleware`` la fija desde ``request.user``.

Estos casos son el control de esa declinación: si algún día alguien cuelga
un ``_sanitize_cookies`` real sobre ``IrHttp`` (aquí o en otro addon), el
segundo grupo de abajo empieza a fallar y obliga a releer el docstring del
módulo antes de aceptar el cambio — no se puede mutar en silencio.
"""
import pytest

from addons.base.models.ir_http import IrHttp
from addons.web.models.ir_http import BOTS


def test_bots_list_is_the_verbatim_reference_list():
    """``BOTS`` — ``odoo19c: web/models/ir_http.py:30``, copiado literal."""
    assert BOTS == [
        "bot", "crawl", "slurp", "spider", "curl", "wget",
        "facebookexternalhit", "whatsapp", "trendsmapresolver", "pinterest",
        "instagram", "google-pagerenderer", "preview",
    ]


def test_the_web_extension_installs_the_reference_list_on_base_ir_http():
    """``apply_web_extensions`` corrió ya en ``WebConfig.ready()`` — no hace
    falta invocarla a mano: el registro de apps de Django ya la disparó al
    arrancar el proceso de test."""
    assert IrHttp.bots == BOTS


@pytest.mark.parametrize('user_agent', [
    'curl/7.68.0',
    'Wget/1.20.3 (linux-gnu)',
    'Mozilla/5.0 (compatible; Googlebot-PageRenderer)',
    'facebookexternalhit/1.1',
    'WhatsApp/2.19.81 A',
    'Some-Preview-Bot/1.0',
])
def test_is_a_bot_recognizes_known_crawler_substrings(user_agent):
    assert IrHttp.is_a_bot(user_agent) is True


@pytest.mark.parametrize('user_agent', [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
    '',
    None,
])
def test_is_a_bot_rejects_ordinary_browsers_and_empty_input(user_agent):
    assert IrHttp.is_a_bot(user_agent) is False


def test_is_a_bot_is_case_insensitive():
    """La referencia compara en minúsculas — un bot con mayúsculas también
    debe detectarse."""
    assert IrHttp.is_a_bot('CURL/7.68.0 SOME-BOT-HEADER') is True


# --- El control de la declinación: `_sanitize_cookies` no existe aquí -----

def test_web_does_not_override_sanitize_cookies():
    """``web`` no encadena ``sanitize_cookies``: el símbolo que ``IrHttp``
    expone sigue siendo el que ``base`` declaró, sin envoltorio.

    Si esto empieza a fallar, alguien colgó una extensión sobre
    ``sanitize_cookies`` — el docstring del módulo (punto 1) deja de
    describir el estado real y hay que releerlo antes de aceptar el cambio.

    El discriminador es dónde vive el ``__func__`` real, no si
    ``IrHttp.sanitize_cookies`` es invocable (siempre lo es: el atributo
    existe desde ``base``). ``chain_method`` instala su envoltorio
    ``chained``, definido en ``orm.method_chain`` — si alguien encadenara
    aquí, el módulo de origen dejaría de ser ``base``.
    """
    assert (IrHttp.sanitize_cookies.__func__.__module__
            == 'addons.base.models.ir_http')


def test_sanitize_cookies_does_not_reformat_a_cids_shaped_cookie():
    """El control conductual: si `cids` viajara con el formato de la
    referencia (lista separada por comas) y `_sanitize_cookies` estuviera
    portado, saldría con guiones (``odoo19c: web/models/ir_http.py:39-41``:
    ``'-'.join(cids.split(','))``). Aquí sale sin tocar — ``base`` es un
    passthrough vacío por diseño y ``web`` no lo extiende."""
    cookies = {'cids': '1,2,3'}
    assert IrHttp.sanitize_cookies(cookies) == {'cids': '1,2,3'}
