"""AppConfig — ``addons.crm_sms``.

Sin modelos ni extensiones: la referencia tampoco aporta código Python de
modelos (ver ``__init__.py``). El config existe para que el addon figure en
el grafo de manifiestos como el puente ``crm`` + ``sms`` que es.
"""
from django.apps import AppConfig


class CrmSmsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.crm_sms'
    label = 'crm_sms'
    verbose_name = 'CRM ↔ SMS (crm_sms)'
