"""Modelos del addon ``utm`` (estructura Odoo: un archivo por modelo).

Puerto de Odoo Community ``utm/`` (``odoo-tools@622ddc2a``, ``odoo19c:``,
LGPL-3). Los tres ejes de marketing —campaña, fuente, medio— y las dos
mitades que los hacen funcionar: la **entrada** (``ir_http`` guarda el
parámetro de URL en una cookie) y la **lectura** (``utm.mixin.default_get``
rellena los campos del registro que se está creando).

Los 7 archivos de modelo de la referencia están presentes, y sus **25
símbolos** portados — ninguno omitido (``porte-completo-no-parcial.md``):

===========================  ====  ======================================
Archivo                      def   Modelos
===========================  ====  ======================================
``utm_campaign.py``             3  ``utm.campaign``
``utm_medium.py``               4  ``utm.medium``
``utm_mixin.py``                7  ``utm.mixin`` (abstracto)
``utm_source.py``               7  ``utm.source`` · ``utm.source.mixin``
``utm_stage.py``                0  ``utm.stage``
``utm_tag.py``                  1  ``utm.tag``
``ir_http.py``                  3  ``ir.http`` (extensión)
===========================  ====  ======================================

Cada archivo declara en su docstring sus propias divergencias. Las tres que
se repiten, y que son el idioma del árbol y no una decisión de este addon:

1. ``create`` (``@api.model_create_multi``) → ``save()``, el único punto de
   persistencia de Django.
2. ``@api.ondelete`` → el método privado se **conserva con su nombre** y lo
   invoca ``delete()``.
3. El contexto ``utm_check_skip_record_ids`` → un **parámetro**
   ``skip_record_ids``: este ORM no tiene contexto de entorno, y el dato es
   un argumento de la llamada, no ambiente.

Lo que la referencia tiene y este puerto **no**, con su razón:

- ``static/src/**`` y las vistas XML — es el cliente web de Odoo. Por eso el
  ``depends`` omite ``web`` (ver ``__manifest__.py``).
- El filtro por vendedor de ``default_get`` — ``has_group`` no existe en este
  árbol; sucesor: tarea **#399** (ver ``utm_mixin.py``).
"""
from .ir_http import IrHttp, UtmCookieMiddleware
from .utm_campaign import UtmCampaign
from .utm_medium import UtmMedium
from .utm_mixin import UtmMixin
from .utm_source import UtmSource, UtmSourceMixin
from .utm_stage import UtmStage
from .utm_tag import UtmTag

__all__ = [
    'IrHttp',
    'UtmCookieMiddleware',
    'UtmCampaign',
    'UtmMedium',
    'UtmMixin',
    'UtmSource',
    'UtmSourceMixin',
    'UtmStage',
    'UtmTag',
]
