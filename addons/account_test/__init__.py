# Odoo importa aquí `models`/`report`; en Django NO se puede: el `__init__`
# del app corre durante la carga del registro, antes de que
# `apps.get_containing_app_config` esté listo, y cualquier modelo importado
# desde aquí revienta con `AppRegistryNotReady`. Los modelos los descubre
# Django por convención (`models/`); los controladores se cablean desde
# `controllers/urls.py` (fuera de este alcance, ver `apps.py`). Mismo patrón
# que `account_debit_note`/`l10n_mx` y el resto de satélites del árbol, cuyo
# `__init__` está vacío a propósito.
