"""Specs de siembra del addon ``account_edi``."""

# ≙ ``ir_cron_edi_network``
# (``odoo19c: addons/account_edi/data/cron.xml:2-10``):
# cada día, **inactivo** hasta que se crea un formato que necesita
# web-service (``account_edi_format.py:40-42``), con su identificador externo
# porque cuatro sitios de la fuente lo piden por ``env.ref``.
#
# ``code`` es el de la fuente, con ``job_count=20``: el cron ejecuta su
# acción con ``run()`` (``designs/cron-runs-server-action.md``).
CRON_EDI_NETWORK = {
    'name': 'EDI: Perform web services operations',
    'model_name': 'account.edi.document',
    'method_name': '_cron_process_documents_web_services',
    'interval_number': 1,
    'interval_type': 'days',
    'priority': 5,
    'code': 'model._cron_process_documents_web_services(job_count=20)',
    'active': False,
    'xml_id': 'account_edi.ir_cron_edi_network',
}

__all__ = ['CRON_EDI_NETWORK']
