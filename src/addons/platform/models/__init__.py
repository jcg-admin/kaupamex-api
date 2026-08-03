"""Models — addons.platform (capa L1 de la plataforma Kaupamex).

Diseño: :ref:`analisis-modelo-tenant-l1-foundation` (plataforma-kaupamex).
Entidad L1 = ``Company`` (DEC-T7; converge Odoo ``res.company`` / NetSuite).

- ``Company`` — el cliente/organización que contrata Kaupamex. Raíz L1: **no**
  tiene FK a la capa L0 (la relación operador↔company es operacional, no de
  datos). Paralelo ``res.company`` de Odoo / ``Organizer`` de pretix.
- ``CompanyModuleSubscription`` — qué ``Module`` (``addons.authz``) tiene
  contratado cada company, con vigencia. Es la puerta **L1-a** (módulo activo
  sí/no) que el resolver compone con el catálogo L2 (DEC-11), expuesta como
  ``Company.active_module_codes()``.

Layout ``models/`` con **un archivo por modelo**, espejo de odoo-tools
(``odoo19c: <addon>/models/<modelo>.py``). Este ``__init__`` re-exporta la
superficie pública: ``from addons.platform.models import Company`` sigue
siendo la forma de importar, igual que antes del desagrupado.
"""
from addons.platform.models.company import (
    FOUNDER_COMPANY_CODE,
    FOUNDER_L1_SETTINGS,
    SYSTEM_COMPANY_CODE,
    Company,
    CompanyScopedManager,
)
from addons.platform.models.company_module_subscription import (
    CompanyModuleSubscription,
)
from addons.platform.models.company_setting import CompanySetting
from addons.platform.models.module_price import ModulePrice
from addons.platform.models.subscription_billing_run import (
    SubscriptionBillingRun,
)
from addons.platform.models.subscription_invoice import SubscriptionInvoice
from addons.platform.models.subsidiary import Subsidiary

__all__ = [
    'FOUNDER_COMPANY_CODE',
    'FOUNDER_L1_SETTINGS',
    'SYSTEM_COMPANY_CODE',
    'Company',
    'CompanyModuleSubscription',
    'CompanyScopedManager',
    'CompanySetting',
    'ModulePrice',
    'SubscriptionBillingRun',
    'SubscriptionInvoice',
    'Subsidiary',
]
