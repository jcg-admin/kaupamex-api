"""``SPECTACULAR_TAGS`` — ``addons.account``.

Layout plano (``<app>.schema``, no ``<app>.controllers.schema``): ``account``
no tiene capa DRF propia (0 ``controllers/``, H-API-406) — es un addon de
modelo puro. Declara el tag ``finance`` porque es el **dueño del módulo**
(``authz_catalog.py``: *"finance — los movimientos financieros"*), aunque
los primeros consumidores del tag vivan en los tres wizards de la familia
(``account_check_printing``/``account_debit_note``/``account_update_tax_tags``,
tareas #50/#51/#52) — Open/Closed (``config/spectacular_hooks.py``): el tag
se declara una sola vez, donde vive el dominio, no en cada addon que lo usa.
"""

SPECTACULAR_TAGS = [
    {'name': 'finance',
     'description': 'Movimientos financieros y sus asistentes: cheques '
                    'prenumerados, notas de débito, recálculo de casillas '
                    'fiscales (~ Odoo account, group_account_manager).'},
]
