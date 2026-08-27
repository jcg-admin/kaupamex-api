r"""``KaupaMexEdiProxyAuth`` — firma las peticiones al proxy EDI.

Renombrado desde ``OdooEdiProxyAuth``, que es como se llama en la
referencia: el nombre del proveedor no va en un identificador de este
árbol (directiva del ejecutor 2026-08-27). La cita ``≙`` de la clase sí
conserva el nombre original — nombra el símbolo de la fuente, no el nuestro.

Adaptación de ``odoo19c: account_edi_proxy_client/models/
account_edi_proxy_auth.py`` (``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a
43eb31de``, LGPL-3, 74 líneas) — atribución y aviso de licencia preservados
(DEC-KX-03).

Clase Python, no modelo — auth handler de ``requests``
============================================================

Subclase de ``requests.auth.AuthBase`` (mismo mecanismo que en la
referencia — Odoo también usa la librería ``requests``, medido: ``grep -ic
requests uv.lock`` → 1, disponible). No es un modelo Django; se instancia
por-petición y se pasa como ``auth=`` a ``requests.post`` (ver
``account_edi_proxy_user.py``).

Ocho símbolos, los 8 portados
=================================

``__init__``, ``__get_payload`` (name-mangled, privado a la clase — se
preserva el mismo esquema), ``__sign_request_with_token``,
``__sign_with_private_key``, ``__call__`` — los 5 métodos de la clase, más
las 3 constantes de cabecera (``odoo-edi-client-id``, ``odoo-edi-
timestamp``, ``odoo-edi-signature``/``-type``).

Divergencia declarada — ``werkzeug.urls`` → ``urllib.parse`` (stdlib)
============================================================================

``werkzeug`` NO es dependencia de este árbol (medido: ``grep -ic werkzeug
uv.lock`` → 0). Es la librería de utilidades URL/HTTP de Odoo (Flask la usa
también); el stdlib de Python cubre exactamente el mismo contrato:

===============================  ================================================
Referencia (``werkzeug.urls``)    Aquí (``urllib.parse``, stdlib)
===============================  ================================================
``url_parse(request.path_url)``   ``urlsplit(request.path_url)`` — mismo
                                   resultado con nombre distinto (``.path``,
                                   ``.query`` idénticos en ambos)
``url_decode(parsed_url.query)``  ``parse_qs(parsed_url.query)`` — devuelve
                                   listas por valor en vez de escalares;
                                   ``json.dumps(..., sort_keys=True)`` serializa
                                   igual de determinista en ambos casos, así que
                                   el contrato de la firma (mensaje determinista
                                   para HMAC) se conserva
===============================  ================================================

``sudo()`` — divergencia uniforme del módulo: ``user.sudo().refresh_token``/
``.private_key_id`` → acceso directo (sin ACL de campo en este puerto).
"""
import base64
import hashlib
import hmac
import json
import time
from typing import Literal
from urllib.parse import parse_qs, urlsplit

import requests


class KaupaMexEdiProxyAuth(requests.auth.AuthBase):
    """≙ ``OdooEdiProxyAuth`` (``odoo19c: :12-19``).

    Firma cada petición al proxy con HMAC (token de refresco) o firma
    asimétrica (llave privada), y añade las cabeceras ``odoo-edi-*``.
    """

    def __init__(self, user=None, auth_type: Literal['hmac', 'asymmetric'] = 'hmac'):
        self.id_client = user.id_client if user else None
        self.auth_type = auth_type
        self.refresh_token = user.refresh_token if user else None
        self.private_key = user.private_key if user else None

    def __get_payload(self, request, msg_timestamp):
        """≙ ``__get_payload`` (``odoo19c: :26-38``)."""
        parsed_url = urlsplit(request.path_url)

        body = request.body
        if isinstance(body, bytes):
            body = body.decode()
        body = json.loads(body)

        return '%s|%s|%s|%s|%s' % (
            msg_timestamp,
            parsed_url.path,
            self.id_client,
            json.dumps(parse_qs(parsed_url.query), sort_keys=True),
            json.dumps(body, sort_keys=True))

    def __sign_request_with_token(self, message):
        """≙ ``__sign_request_with_token`` (``odoo19c: :40-42``)."""
        h = hmac.new(base64.b64decode(self.refresh_token), message.encode(),
                     digestmod=hashlib.sha256)
        return h.hexdigest()

    def __sign_with_private_key(self, message):
        """≙ ``__sign_with_private_key`` (``odoo19c: :44-46``).

        Reintenta la resincronización del token tras un desajuste
        (restauración de backup, copia sin neutralizar) firmando con la
        llave privada en vez del token.
        """
        return self.private_key._sign(message.encode(), formatting='base64').decode()

    def __call__(self, request):
        """≙ ``__call__`` (``odoo19c: :48-68``)."""
        if not self.id_client:
            return request

        timestamp = int(time.time())
        request.headers.update({
            'odoo-edi-client-id': self.id_client,
            'odoo-edi-timestamp': timestamp,
        })
        message = self.__get_payload(request, timestamp)

        if self.auth_type == 'asymmetric' and self.private_key:
            request.headers.update({
                'odoo-edi-signature': self.__sign_with_private_key(message),
                'odoo-edi-signature-type': 'asymmetric',
            })
        elif self.refresh_token:
            request.headers.update({
                'odoo-edi-signature': self.__sign_request_with_token(message),
                'odoo-edi-signature-type': 'hmac',
            })

        return request
