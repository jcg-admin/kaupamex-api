"""Semilla del addon ``utm`` — un archivo por XML de ``data``, como la fuente.

``odoo19c: addons/utm/__manifest__.py:11-14`` lista cuatro XML bajo ``data``, y
aquí hay cuatro módulos con el mismo nombre. **El ``demo`` no se porta**
(``utm_campaign_demo.xml``, ``utm_stage_demo.xml``): la referencia separa los
dos y aquí se respeta esa separación — la data es infraestructura, la demo es
relleno de escaparate.

El spec vive como constante y lo consumen dos escritores distintos:

- la data-migration ``0002_seed_utm_data`` (arranque, sobre el modelo
  histórico), y
- ``seed()`` (re-aplicación sobre el modelo vivo, H-API-22) — el mismo patrón
  que ``mail`` fija con ``0002_seed_message_subtypes`` + ``mail/data/
  __init__.py::seed``.

**Por qué hace falta el segundo escritor** (H-API-674): un test
``django_db(transaction=True)`` en *cualquier* addon de la suite deja la BD
compartida (``--reuse-db``) sin filas de modelo — ``django_migrations`` no es
tabla de modelo y sobrevive al ``flush``, así que la migración queda
"aplicada" sobre una tabla vacía y **nunca vuelve a correr**. Sin un
``seed()`` que el ``pytest_runtest_teardown`` de ``tests/conftest.py`` pueda
re-invocar, las cuatro familias sembradas aquí quedan en cero para el resto de
la sesión — el defecto exacto que ``tests/integration/base/
test_migration_seeds_survive_flush.py`` documenta para ``base``/``mail``/
``base_geolocalize``.

``utm`` todavía **no** está en ``tests/conftest.py::_SEEDERS`` — ver
:ref:`h-api-674` para el sucesor que lo cablea.
"""
from django.db import DEFAULT_DB_ALIAS

from addons.base.models import IrModelData
from addons.utm.models import UtmMedium, UtmSource, UtmStage, UtmTag

from .utm_medium_data import UTM_MEDIUMS
from .utm_source_data import UTM_SOURCES
from .utm_stage_data import UTM_STAGES
from .utm_tag_data import UTM_TAGS

__all__ = ['UTM_MEDIUMS', 'UTM_SOURCES', 'UTM_STAGES', 'UTM_TAGS', 'seed']


def seed(using=DEFAULT_DB_ALIAS):
    """Re-siembra las cuatro familias, idempotente por identificador externo.

    Mismo contrato que ``mail.data.seed`` / ``base_geolocalize.data.seed``:
    llamarlo dos veces no duplica, y no pisa un registro ya editado (se
    detiene en el primer ``IrModelData.ref`` que resuelve).

    ``addons.utm.models`` no importa ``addons.utm.data`` en ningún archivo
    (verificado: ``grep -rn "addons.utm.data" addons/utm/models/`` da 0
    hits), así que importar los cuatro modelos al top de este módulo no
    cierra ningún ciclo — y es lo que ``no-lazy-imports.md`` exige por
    defecto.
    """
    _seed_family(UtmStage, UTM_STAGES, using)
    _seed_family(UtmMedium, UTM_MEDIUMS, using)
    _seed_family(UtmSource, UTM_SOURCES, using)
    _seed_family(UtmTag, UTM_TAGS, using)


def _seed_family(model, specs, using):
    """Crea lo ausente de una familia y registra su identificador externo.

    ``IrModelData.ref`` primero: si el identificador ya resuelve, la fila
    puede haberse editado en caliente (un color, un nombre) y no se toca —
    el mismo contrato que ``test_seed_no_pisa_un_valor_editado`` fija para
    las otras familias. Sólo cuando el identificador NO resuelve —falta la
    fila de ``ir_model_data``, o la que apuntaba ya no existe— se busca por
    ``name`` (única por restricción de modelo) y, si tampoco está, se crea.
    """
    for spec in specs:
        xmlid = spec['xmlid']
        name = spec['name']
        defaults = {k: v for k, v in spec.items() if k not in ('xmlid', 'name')}

        record = IrModelData.ref(xmlid, raise_if_not_found=False)
        if record is not None:
            continue

        record, _created = model.objects.using(using).get_or_create(
            name=name, defaults=defaults)
        IrModelData.set_xmlid(record, xmlid, noupdate=True)
