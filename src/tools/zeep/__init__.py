"""``tools.zeep`` — la fachada restringida sobre el cliente SOAP ``zeep``.

Adaptación de ``odoo/tools/zeep/`` (``odoo19c``, LGPL-3: copia + adaptación
con atribución). El paquete de la referencia **no** es un fork de ``zeep``:
son 204 líneas que re-exportan lo que el árbol usa y, sobre todo, envuelven
``zeep.Client`` en un contrato más estrecho — ver ``client.py``.

Los consumidores de la referencia son sus localizaciones fiscales
(``l10n_es_edi_verifactu``, ``l10n_es_edi_sii``): un servicio web de una
autoridad tributaria se consume por SOAP, se describe con un WSDL, y ese WSDL
se cachea. El mecanismo es el mismo que exige el SAT.
"""
from zeep.plugins import Plugin
from zeep.settings import Settings
from zeep.transports import Transport

from . import exceptions
from . import ns
from . import wsdl
from .client import Client

__all__ = ['Client', 'Plugin', 'Settings', 'Transport', 'exceptions', 'ns', 'wsdl']
