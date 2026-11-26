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
    'model_name': 'ir.autovacuum',
    'method_name': '_run_vacuum_cleaner',
    'xml_id': 'base.autovacuum_job',
    'interval_number': 1,
    'interval_type': 'days',
    'priority': 3,
}

# El barrido de bajas de portal, verbatim de
# ``odoo19c: odoo/addons/base/data/ir_cron_data.xml:13-21``
# (``ir_cron_res_users_deletion``): un día, prioridad 8, y
# ``model._gc_portal_users(batch_size=50)`` sobre ``res.users.deletion``.
CRON_RES_USERS_DELETION = {
    'name': 'Base: Portal Users Deletion',
    'model_name': 'res.users.deletion',
    'method_name': '_gc_portal_users',
    'code': 'model._gc_portal_users(batch_size=50)',
    'xml_id': 'base.ir_cron_res_users_deletion',
    'interval_number': 1,
    'interval_type': 'days',
    'priority': 8,
}

__all__ = ['sembrar_cron', 'CRON_AUTOVACUUM', 'CRON_RES_USERS_DELETION']
