"""``PeppolIAPConnector`` — el cliente HTTP público del proxy Peppol.

Adaptación de Odoo ``account_peppol/tools/peppol_iap_connector.py``
(``odoo19c: addons/account_peppol/tools/peppol_iap_connector.py``, 64 líneas,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué es: las dos llamadas al proxy Peppol de Odoo S.A. que se hacen **antes**
de existir un usuario de proxy —``can_connect`` y ``create_connection``— y por
tanto no pueden ir firmadas por él. Las autenticadas viven en
``models/account_edi_proxy_user.py`` y pasan por ``_make_request``.

Porte símbolo por símbolo — 5 símbolos, los 5 portados
=======================================================

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Símbolo de la referencia (línea)
     - Desenlace
   * - ``TIMEOUT`` / ``PEPPOL_PROXY_URLS`` (``:11-15``)
     - portados verbatim — los dos hosts del proxy son el contrato.
   * - ``__init__`` (``:20-27``)
     - portado, con las dos aserciones de la fuente.
   * - ``request_public_http`` (``:29-42``)
     - portado — incluida la doble vía del error (mensaje del catálogo si el
       cuerpo trae ``code``; genérico si no).
   * - ``can_connect`` (``:44-52``)
     - portado — los seis parámetros verbatim.
   * - ``create_connection`` (``:54-64``)
     - portado.

Divergencias declaradas
=========================

1. **``self.env = company.env`` cae.** Este árbol no tiene ``env``: la
   traducción la resuelve el hilo y el acceso a modelos es directo. Por eso
   ``get_peppol_error_message`` se llama sin ``env`` (ver el docstring de
   ``exceptions.py``).
2. **``requests`` sí está** — medido en ``uv.lock`` (paquete declarado). Se usa
   tal cual, con el mismo ``timeout``.
"""
import logging

import requests

from addons.account_peppol.exceptions import get_peppol_error_message
from exceptions import UserError
from tools.translate import _
from tools.urls import urljoin

_logger = logging.getLogger(__name__)

TIMEOUT = 10
#: Los hosts del proxy Peppol de Odoo S.A. Verbatim de la referencia
#: (``odoo19c: :12-15``); ``models/account_edi_proxy_user.py`` los publica en
#: ``_get_proxy_urls`` bajo la llave ``'peppol'``, añadiendo ``'demo'``.
PEPPOL_PROXY_URLS = {
    'prod': 'https://peppol.api.odoo.com',
    'test': 'https://peppol.test.odoo.com',
}


class PeppolIAPConnector:
    """≙ ``PeppolIAPConnector`` (``odoo19c: :18-64``) — las llamadas públicas
    (sin firmar) al proxy Peppol."""

    def __init__(self, company):
        """≙ ``__init__`` (``odoo19c: :20-27``).

        :param company: la ``base.ResCompany`` cuya conexión se negocia. El
            modo (``prod``/``test``) sale de ``_get_peppol_edi_mode``; el modo
            ``demo`` no tiene host y por eso la aserción lo excluye, igual que
            la fuente.
        """
        assert company.pk is not None
        self.company = company
        proxy_mode = company._get_peppol_edi_mode()
        assert proxy_mode in ('prod', 'test')
        self.proxy_mode = proxy_mode
        self.base_url = PEPPOL_PROXY_URLS[proxy_mode]

    def request_public_http(self, method, endpoint, data=None, params=None):
        """≙ ``request_public_http`` (``odoo19c: :29-42``).

        Si el proxy devolvió un cuerpo con ``code``, el error se traduce con el
        catálogo de ``exceptions.py``; si ni eso, se levanta el genérico. El
        detalle técnico va al log en ``debug``, como en la fuente.
        """
        headers = {'Content-Type': 'application/json'}
        url = urljoin(self.base_url, endpoint)
        response_vals = {}
        try:
            response = requests.request(
                method, url, json=data, params=params, timeout=TIMEOUT, headers=headers,
            )
            response_vals = response.json()
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            if response_vals and 'code' in response_vals:
                raise UserError(get_peppol_error_message(response_vals))
            _logger.debug('Falló la conexión con el proxy Peppol de Odoo %s, %s', endpoint, e)
            raise UserError(_('Falló la conexión con el proxy Peppol de Odoo.'))
        return response_vals

    def can_connect(self, *, peppol_identifier, db_uuid, callback_url, connect_token,
                    contact_email=None, webhook_url=None):
        """≙ ``can_connect`` (``odoo19c: :44-52``) — ¿puede esta base conectarse
        con ese identificador Peppol?"""
        return self.request_public_http('GET', '/api/peppol/2/can_connect', params={
            'dbuuid': db_uuid,
            'peppol_identifier': peppol_identifier,
            'callback_url': callback_url,
            'connect_token': connect_token,
            'contact_email': contact_email,
            'webhook_url': webhook_url,
        })

    def create_connection(self, *, peppol_identifier, db_uuid, public_key,
                          auth_token=None, **company_details):
        """≙ ``create_connection`` (``odoo19c: :54-64``) — da de alta la
        conexión y devuelve las credenciales del usuario de proxy."""
        params = {
            'peppol_identifier': peppol_identifier,
            'dbuuid': db_uuid,
            'company_id': self.company.pk,
            'public_key': public_key,
            'auth_token': auth_token,
            **company_details,
        }
        return self.request_public_http('POST', '/api/peppol/2/connect', data=params)


__all__ = ['PEPPOL_PROXY_URLS', 'PeppolIAPConnector', 'TIMEOUT']
