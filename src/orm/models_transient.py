"""``TransientModel`` — fiel a ``odoo/orm/models_transient.py`` (Odoo 19).

En Odoo un ``TransientModel`` es un modelo **persistente temporal**: se escribe a
una tabla real pero se recolecta (vacuum) periódicamente; sirve a wizards y
asistentes de un solo uso. Provee ``_transient = True``,
``_transient_max_count`` y ``_transient_max_hours`` para el vacuum.

Mapeo a Django (por qué es un stub delgado y no una reimplementación):

- **El motor de vacuum es de Odoo, no del modelo.** El barrido lo dispara
  ``ir.autovacuum`` (un cron): eso es responsabilidad del scheduler, no de esta
  clase. Aquí ``ir.cron`` se porta como modelo de control aparte; el barrido
  concreto de filas viejas se implementa cuando un wizard real lo requiera.
- **Django ya modela "no persistente" de dos formas** —
  ``class Meta: managed = False`` (tabla existe pero Django no la migra) o un
  modelo sin tabla para formularios efímeros. Un wizard normalmente NO necesita
  tabla: su estado vive en la sesión/request. Por eso el equivalente idiomático
  es un modelo ``abstract``/``managed=False`` + limpieza por ``clearsessions`` o
  un management command, no una tabla que hay que aspirar.

Este ``TransientModel`` preserva el **contrato público** (``_transient`` y los
umbrales) sobre ``models.Model`` (≙ ``orm/models``) para que un addon portado que
declare ``class MyWizard(models.TransientModel)`` compile y lea como su fuente
Odoo; la política de vacuum se ancla a ``ir.cron`` cuando el wizard exista.
"""
from orm.models import Model


class TransientModel(Model):
    """Modelo transitorio (wizard/asistente). Fiel al contrato Odoo 19; el
    vacuum se delega a ``ir.cron`` (no se reimplementa el motor de barrido)."""
    class Meta:
        abstract = True
        managed = False  # Django no migra tabla para el transitorio

    _transient = True
    # nº máximo de registros transitorios (0 = ilimitado)
    _transient_max_count = 0
    # vida ociosa máxima en horas (0 = ilimitado)
    _transient_max_hours = 0
