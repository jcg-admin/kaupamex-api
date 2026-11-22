"""Specs de siembra del addon ``account_edi``."""

# ≙ ``ir_cron_edi_network``
# (``odoo19c: addons/account_edi/data/cron.xml:2-10``):
# cada día, **inactivo** hasta que se crea un formato que necesita
# web-service (``account_edi_format.py:40-42``), con su identificador externo
# porque cuatro sitios de la fuente lo piden por ``env.ref``.
#
# La fuente llama ``_cron_process_documents_web_services(job_count=20)``; el
# runner de este árbol invoca el método sin argumentos
# (``ir_cron.py:808-810``),
# así que aquí procesa todos los documentos pendientes de una vez. Sucesor:
# ``cron-runner-method-arguments-0397`` en
# ``designs/account-edi-network-cron.md``.
CRON_EDI_NETWORK = {
    'name': 'EDI: Perform web services operations',
    'model_name': 'account_edi.AccountEdiDocument',
    'method_name': '_cron_process_documents_web_services',
    'interval_number': 1,
    'interval_type': 'days',
    'priority': 5,
    'active': False,
    'xml_id': 'account_edi.ir_cron_edi_network',
}

__all__ = ['CRON_EDI_NETWORK']
