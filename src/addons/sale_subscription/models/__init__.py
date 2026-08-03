"""Models — addons.sale_subscription (billing recurrente L0).

Espejo del patrón de la referencia (``odoo19e: sale_subscription/models/``):
extensiones del núcleo (``res_company.py`` — análogo de ``_inherit``) +
modelos propios del eje. Un archivo por modelo.
"""
from addons.sale_subscription.models import res_company  # noqa: F401 — _inherit
from addons.sale_subscription.models.company_module_subscription import (
    CompanyModuleSubscription,
)
from addons.sale_subscription.models.module_price import ModulePrice
from addons.sale_subscription.models.subscription_billing_run import (
    SubscriptionBillingRun,
)
from addons.sale_subscription.models.subscription_invoice import (
    SubscriptionInvoice,
)

__all__ = [
    'CompanyModuleSubscription',
    'ModulePrice',
    'SubscriptionBillingRun',
    'SubscriptionInvoice',
]
