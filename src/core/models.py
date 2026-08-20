"""
core/models.py — vacío tras la disolución de ``core/`` (DEC-08).

Los modelos que antes vivían aquí ya migraron a addons fieles a Odoo o al
addon net-new ``observability``:

- Bases abstractas (``TimeStampedModel``/``AppendOnlyModel``/``SoftDeleteModel``)
  -> ``addons/base/models/{timestamped,append_only,soft_delete}_mixin.py`` (slice 1 de
  ``adoptar-arquitectura-server-service-odoo``).
- ``AppLog`` -> ``IrLogging`` en ``addons/base`` (slice 2, DEC-08). Ver
  ``addons/base/models/ir_logging.py``.
- ``RequestLog`` -> ``addons/observability`` (slice 3, DEC-08/DEC-12), y de
  ahí **retirado** por DEC-AF-11: su mitad de error vive en ``ir.logging`` y
  la de acceso en el ``access_log`` del proxy inverso.

Este módulo se mantiene vacío (sin modelos) para no romper el import de
``core.models`` mientras ``core`` como app Django siga registrada en
``INSTALLED_APPS`` — su retiro definitivo llega en un slice posterior de la
misma iniciativa (ver ``docs/source/gestion/pm/api/iniciativas/
adoptar-arquitectura-server-service-odoo/``).
"""
