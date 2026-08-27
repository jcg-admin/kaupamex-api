"""Los tres motivos de baja maestros — ≙ ``odoo19c: hr/data/hr_data.xml:56-73``.

La referencia los declara como registros XML del módulo, y su instalador los
carga en cada ``-i``/``-u``. Aquí ese cargador no existe, así que el mecanismo
equivalente es doble y **los dos consumen esta misma tabla**:

- la migración ``hr/0003_seed_default_departure_reasons`` los siembra una vez,
  sobre los modelos **históricos**;
- ``seed()`` los repone sobre los modelos **vivos** — es la entrada del
  catálogo de ``tests/conftest.py``, que la re-aplica al arrancar la sesión y
  tras cada test transaccional.

Sin la segunda entrada, un ``flush`` borra las filas que sembró la migración y
``django_migrations`` las sigue dando por aplicadas: la sesión siguiente
arranca sin motivos maestros y el fallo aparece lejos de su causa
(:ref:`h-api-337`, y su reincidencia medida en :ref:`h-api-757`).

Tres decisiones que salen de leer la fuente, no de la costumbre:

``sequence`` **0, 1, 2** — verbatim del XML, no el ``default=10`` del campo.
La fuente numera los tres maestros por debajo de cualquier motivo que un
usuario añada después, que es lo que los mantiene arriba en el catálogo.

``country`` **explícitamente nulo** — ≙ ``<field name="country_id" eval="False"/>``.
El campo tiene ``default=_default_country`` (el país de la compañía activa),
así que crear sin pasarlo ataría los tres maestros a la compañía que estuviera
activa al sembrar. La fuente lo anula a propósito: son universales.

Los nombres van **en español** porque son dato visible para el usuario final
—la fuente los declara ``translate=True``— y el L0 opera en México. No es
drift: ``identificadores-en-ingles.md`` gobierna identificadores, no
contenido.
"""
from django.db import DEFAULT_DB_ALIAS

from addons.base.models.ir_model import IrModelData
from addons.hr.models import HrDepartureReason

#: ``(nombre del identificador externo, etiqueta, sequence)`` — el orden y los
#: tres ``sequence`` son los del XML de la fuente.
DEFAULT_DEPARTURE_REASONS = (
    ('departure_fired', 'Despedido', 0),
    ('departure_resigned', 'Renunció', 1),
    ('departure_retired', 'Jubilado', 2),
)

#: Módulo del identificador externo — ≙ el prefijo ``hr.`` de los tres
#: ``self.env.ref('hr.departure_…')`` de ``_get_default_departure_reasons``.
MODULE = 'hr'


def _seed(departure_reason_model, ir_model_data_model, using):
    """Crea (o respeta) los tres motivos y sus identificadores externos.

    Idempotente por ``(module, name)`` de ``ir.model.data``: un segundo pase
    repunta la fila en vez de duplicarla, y **no pisa** un motivo existente —
    la fuente marca su bloque de datos ``noupdate``, así que un cambio del
    usuario sobrevive a la recarga.
    """
    label = departure_reason_model._meta.label
    seeded = []

    for name, label_text, sequence in DEFAULT_DEPARTURE_REASONS:
        row = ir_model_data_model.objects.using(using).filter(
            module=MODULE, name=name).first()
        existing = None
        if row is not None:
            existing = departure_reason_model.objects.using(using).filter(
                pk=row.res_id).first()
        if existing is None:
            existing = departure_reason_model.objects.using(using).filter(
                name=label_text).first()
        if existing is None:
            existing = departure_reason_model.objects.using(using).create(
                name=label_text, sequence=sequence, country=None)
        ir_model_data_model.objects.using(using).update_or_create(
            module=MODULE, name=name,
            defaults={'model': label, 'res_id': existing.pk, 'noupdate': True},
        )
        seeded.append(existing)

    return seeded


def seed(using=DEFAULT_DB_ALIAS):
    """Siembra sobre los modelos vivos — entrada del catálogo de semillas."""
    return _seed(HrDepartureReason, IrModelData, using)


def seed_departure_reasons(apps, alias):
    """Siembra sobre los modelos históricos — entrada de la migración.

    ``apps.get_model`` y no el modelo vivo porque ejecutar comportamiento de la
    app viva desde una migración la ata a un estado del código que cambia bajo
    sus pies. Mismo criterio que ``base: data/res_country_data.py``.
    """
    return _seed(
        apps.get_model('hr', 'HrDepartureReason'),
        apps.get_model('base', 'IrModelData'),
        alias,
    )
