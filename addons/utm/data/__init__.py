"""Semilla del addon ``utm`` — un archivo por XML de ``data``, como la fuente.

``odoo19c: addons/utm/__manifest__.py:11-14`` lista cuatro XML bajo ``data``, y
aquí hay cuatro módulos con el mismo nombre. **El ``demo`` no se porta**
(``utm_campaign_demo.xml``, ``utm_stage_demo.xml``): la referencia separa los
dos y aquí se respeta esa separación — la data es infraestructura, la demo es
relleno de escaparate.

El spec vive como constante y lo consume la data-migration
``0002_seed_utm_data``. Es el patrón que ``mail`` y su
``0002_seed_message_subtypes`` ya fijan: la migración importa **el dato**, no
el comportamiento.
"""
from .utm_medium_data import UTM_MEDIUMS
from .utm_source_data import UTM_SOURCES
from .utm_stage_data import UTM_STAGES
from .utm_tag_data import UTM_TAGS

__all__ = ['UTM_MEDIUMS', 'UTM_SOURCES', 'UTM_STAGES', 'UTM_TAGS']
