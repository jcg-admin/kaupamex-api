"""Constantes del addon ``sale`` — ≙ ``odoo19c: sale/const.py``.

LGPL-3 según su ``__manifest__.py``: copia + adaptación con atribución.
"""

#: ≙ ``PARAM_CRON_MAPPING`` (``odoo19c: sale/const.py:4-7``). Mapea el
#: parámetro de configuración al identificador externo de la tarea periódica
#: que enciende o apaga. Lo consume
#: ``addons.sale.models.ir_config_parameter._sale_sync_linked_crons``.
#:
#: Las **claves** son las de la referencia verbatim: son lo que se guarda en
#: ``ir.config_parameter`` y lo que un despliegue existente ya tendría escrito.
PARAM_CRON_MAPPING = {
    'sale.async_emails': 'sale.send_pending_emails_cron',
    'sale.automatic_invoice': 'sale.send_invoice_cron',
}
