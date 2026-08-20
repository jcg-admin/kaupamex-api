"""Specs de siembra del addon ``base``."""
from addons.base.data.cron import sembrar_cron

# El barrido de ``@api.autovacuum``, verbatim de
# ``odoo19c: odoo/addons/base/data/ir_cron_data.xml:3-11``
# (``autovacuum_job``): un día, prioridad 3, y ``model._run_vacuum_cleaner()``
# sobre ``ir.autovacuum``.
#
# Es el ÚNICO cron del barrido: los métodos decorados no llevan cron propio —
# los recoge el colector. Por eso ``observability`` retira el suyo en su 0004
# cuando ``IrLogging._purge_expired`` gana el decorador.
CRON_AUTOVACUUM = {
    'name': 'Base: Auto-vacuum internal data',
    'model_name': 'base.IrAutovacuum',
    'method_name': '_run_vacuum_cleaner',
    'interval_number': 1,
    'interval_type': 'days',
    'priority': 3,
}

__all__ = ['sembrar_cron', 'CRON_AUTOVACUUM']
