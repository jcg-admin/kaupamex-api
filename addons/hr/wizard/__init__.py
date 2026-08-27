"""Wizards del addon ``hr`` — espejo de ``odoo19c: hr/wizard/``.

``mail_activity_schedule`` no se importa aquí: su extensión se aplica
tarde desde ``HrConfig.ready()`` (registro de modelos aún no poblado en
tiempo de import de este paquete).
"""
from . import hr_bank_account_allocation_wizard_line  # noqa: F401
from . import hr_bank_account_wizard  # noqa: F401
from . import hr_contract_template_wizard  # noqa: F401
from . import hr_departure_wizard  # noqa: F401
