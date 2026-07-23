"""
core/models.py — vacío tras la disolución de ``core/`` (DEC-08).

Los modelos que antes vivían aquí ya migraron a addons fieles a Odoo o al
addon net-new ``observability``:

- Bases abstractas (``TimeStampedModel``/``AppendOnlyModel``/``SoftDeleteModel``)
  -> ``addons/base/models/mixins.py`` (slice 1 de
  ``adoptar-arquitectura-server-service-odoo``).
- ``AppLog`` -> ``IrLogging`` en ``addons/base`` (slice 2, DEC-08). Ver
  ``addons/base/models/ir_logging_log.py``.
- ``RequestLog`` -> ``addons/observability`` (slice 3, DEC-08/DEC-12). Ver
  ``addons/observability/models/request_log.py``.

Este módulo se mantiene vacío (sin modelos) para no romper el import de
``core.models`` mientras ``core`` como app Django siga registrada en
``INSTALLED_APPS`` — su retiro definitivo llega en un slice posterior de la
misma iniciativa (ver ``docs/source/gestion/pm/api/iniciativas/
adoptar-arquitectura-server-service-odoo/``).
"""
