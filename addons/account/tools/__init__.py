"""Paquete ``tools`` del addon ``account`` -- utilidades sin dependencia del ORM.

Adaptacion de ``odoo19c: addons/account/tools/__init__.py``
(``odoo-tools@622ddc2a``, LGPL-3 -- atribucion y aviso de licencia
preservados, DEC-KX-03).

Cobertura del porte -- 2 de 2 simbolos
========================================

.. list-table::
   :header-rows: 1

   * - Simbolo
     - Estado
   * - ``from .structured_reference import *``
     - portado verbatim
   * - ``LegacyHTTPAdapter``
     - portado verbatim

``dict_to_xml`` se importa explicito (no via ``*``), fiel a la fuente
(``odoo19c: addons/account/tools/__init__.py:4``, que la lista aparte de la
importacion en estrella de ``structured_reference``).

``requests`` (``>=2.31.0``) y ``urllib3`` ya son dependencias declaradas de
``kaupamex-api`` (``pyproject.toml``), asi que ``LegacyHTTPAdapter`` no
necesita ninguna dependencia nueva -- a diferencia de
``structured_reference.py``, que si tuvo que vendorizar (ver su docstring).
"""
import requests
from urllib3.util.ssl_ import create_urllib3_context

from .dict_to_xml import dict_to_xml
from .structured_reference import *  # noqa: F401,F403  (fiel a la fuente)


class LegacyHTTPAdapter(requests.adapters.HTTPAdapter):
    """Adaptador que permite renegociacion TLS legacy insegura, necesaria
    para conectar contra servidores de produccion de ETA (Egyptian Tax
    Authority) gravemente desactualizados.
    """

    def init_poolmanager(self, *args, **kwargs):
        # No estaba definido antes de Python 3.12
        # cfr. https://github.com/python/cpython/pull/93927
        # Origen: https://github.com/openssl/openssl/commit/ef51b4b9
        legacy_server_connect_flag = 0x04
        context = create_urllib3_context(options=legacy_server_connect_flag)
        kwargs["ssl_context"] = context
        return super().init_poolmanager(*args, **kwargs)
