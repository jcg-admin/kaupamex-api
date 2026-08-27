"""El firmador de peticiones al proxy EDI — ``KaupaMexEdiProxyAuth``.

Porta ``odoo19c: account_edi_proxy_client/models/account_edi_proxy_auth.py``
(LGPL-3). Es una clase Python plana, no un modelo: subclase de
``requests.auth.AuthBase`` que se pasa como ``auth=`` a cada petición.

Por qué estos casos existen
----------------------------

El módulo llegó al árbol **sin un solo test** — medido antes de escribir
éstos: ``grep -rl account_edi_proxy tests/`` daba cero. Un firmador sin
cobertura es la peor clase de código sin red: falla en silencio y el fallo se
manifiesta como un 401 del otro extremo, lejos de aquí.

El control que puede fallar
---------------------------

La firma se recomputa **en el test**, desde el formato de mensaje documentado,
en vez de comparar contra una constante grabada. Así, si el orden de los
campos del mensaje cambia —o se pierde el ``sort_keys=True`` que lo hace
determinista— el caso cae. Una constante grabada pasaría igual con el mensaje
mal formado, porque mediría que el código coincide consigo mismo.
"""
import base64
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qs, urlsplit

import pytest
import requests

from addons.account_edi_proxy_client.models.account_edi_proxy_auth import (
    KaupaMexEdiProxyAuth)

pytestmark = pytest.mark.unit

TOKEN = base64.b64encode(b'secreto-de-refresco').decode()


class _StubUser:
    """El usuario del proxy, reducido a los cuatro atributos que el firmador lee."""

    def __init__(self, id_client='cliente-1', refresh_token=TOKEN, private_key=None):
        self.id_client = id_client
        self.refresh_token = refresh_token
        self.private_key = private_key


class _StubPrivateKey:
    """≙ ``certificate.key._sign`` — devuelve una firma reconocible."""

    def __init__(self):
        self.seen = []

    def _sign(self, message, formatting='encodebytes'):
        self.seen.append((message, formatting))
        # El real devuelve **bytes**; el firmador los decodifica. Devolver aquí
        # un marcador legible deja el aserto directo sin falsear el contrato.
        return b'firma-asimetrica'


def _prepared(body=None, url='https://proxy.test/api/enviar?b=2&a=1'):
    """Una petición ya preparada, que es lo que ``requests`` pasa al firmador."""
    return requests.Request(
        'POST', url, json=body if body is not None else {'z': 1, 'a': 2}).prepare()


def _expected_message(request, timestamp, id_client):
    """Recomputa el mensaje canónico desde el formato documentado.

    Es la mitad que hace al control capaz de fallar: si el firmador cambia el
    orden o deja de ordenar las claves, este mensaje deja de coincidir.
    """
    parsed = urlsplit(request.path_url)
    body = request.body
    if isinstance(body, bytes):
        body = body.decode()
    return '%s|%s|%s|%s|%s' % (
        timestamp, parsed.path, id_client,
        json.dumps(parse_qs(parsed.query), sort_keys=True),
        json.dumps(json.loads(body), sort_keys=True))


# --------------------------------------------------------------------------
# La salida temprana — ≙ ``:49-50``
# --------------------------------------------------------------------------

def test_a_request_without_client_id_is_returned_untouched():
    """Sin ``id_client`` no hay a quién firmar: la petición sale igual."""
    request = _prepared()
    before = dict(request.headers)
    signed = KaupaMexEdiProxyAuth(user=_StubUser(id_client=None))(request)
    assert signed is request
    assert dict(signed.headers) == before


def test_no_user_at_all_is_also_a_pass_through():
    """El constructor admite ``user=None`` — sin él, tampoco firma."""
    request = _prepared()
    assert 'odoo-edi-signature' not in KaupaMexEdiProxyAuth()(request).headers


# --------------------------------------------------------------------------
# La rama HMAC — ≙ ``:40-42`` y ``:62-66``
# --------------------------------------------------------------------------

def test_the_hmac_signature_matches_the_documented_message():
    """La firma se recomputa aquí desde el formato, no se compara con una
    constante grabada."""
    request = _prepared()
    signed = KaupaMexEdiProxyAuth(user=_StubUser())(request)

    assert signed.headers['odoo-edi-signature-type'] == 'hmac'
    assert signed.headers['odoo-edi-client-id'] == 'cliente-1'

    timestamp = signed.headers['odoo-edi-timestamp']
    esperada = hmac.new(
        base64.b64decode(TOKEN),
        _expected_message(request, timestamp, 'cliente-1').encode(),
        digestmod=hashlib.sha256).hexdigest()
    assert signed.headers['odoo-edi-signature'] == esperada


def test_the_timestamp_is_the_current_epoch_second():
    """El sello va en la cabecera y entra en el mensaje firmado."""
    antes = int(time.time())
    signed = KaupaMexEdiProxyAuth(user=_StubUser())(_prepared())
    assert antes <= int(signed.headers['odoo-edi-timestamp']) <= int(time.time())


def test_the_query_is_sorted_so_the_message_is_deterministic():
    """Dos URL con los mismos parámetros en distinto orden firman igual.

    Es lo que ``sort_keys=True`` compra, y sin él el otro extremo rechazaría
    una petición legítima.
    """
    firmante = KaupaMexEdiProxyAuth(user=_StubUser())
    uno = firmante(_prepared(url='https://proxy.test/api/x?a=1&b=2'))
    otro = firmante(_prepared(url='https://proxy.test/api/x?b=2&a=1'))
    if uno.headers['odoo-edi-timestamp'] != otro.headers['odoo-edi-timestamp']:
        pytest.skip('los dos sellos cayeron en segundos distintos')
    assert uno.headers['odoo-edi-signature'] == otro.headers['odoo-edi-signature']


# --------------------------------------------------------------------------
# La rama asimétrica — ≙ ``:44-46`` y ``:57-61``
# --------------------------------------------------------------------------

def test_the_asymmetric_branch_signs_with_the_private_key():
    """≙ ``:57-61`` — con llave privada y el tipo pedido, firma con ella."""
    key = _StubPrivateKey()
    signed = KaupaMexEdiProxyAuth(
        user=_StubUser(private_key=key), auth_type='asymmetric')(_prepared())

    assert signed.headers['odoo-edi-signature-type'] == 'asymmetric'
    assert signed.headers['odoo-edi-signature'] == 'firma-asimetrica'
    assert len(key.seen) == 1
    mensaje, formato = key.seen[0]
    assert formato == 'base64'
    assert mensaje.decode() == _expected_message(
        _prepared(), signed.headers['odoo-edi-timestamp'], 'cliente-1')


def test_asking_for_asymmetric_without_a_key_falls_back_to_hmac():
    """≙ ``:57`` — la condición exige **ambos**: el tipo y la llave."""
    signed = KaupaMexEdiProxyAuth(
        user=_StubUser(private_key=None), auth_type='asymmetric')(_prepared())
    assert signed.headers['odoo-edi-signature-type'] == 'hmac'


def test_without_token_nor_key_nothing_is_signed():
    """La rama negativa: hay ``id_client``, pero no con qué firmar."""
    signed = KaupaMexEdiProxyAuth(
        user=_StubUser(refresh_token=None, private_key=None))(_prepared())
    assert signed.headers['odoo-edi-client-id'] == 'cliente-1'
    assert 'odoo-edi-signature' not in signed.headers
