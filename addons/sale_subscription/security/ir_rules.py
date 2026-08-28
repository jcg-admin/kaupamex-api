"""Record rules de ``sale_subscription`` — reglas multi-company.

``sale_subscription`` en la referencia es Enterprise (OEEL-1 →
reimplementación nativa, DEC-KX-03), así que aquí no se copia su XML: se
declara el MISMO patrón canónico que ``sale/security/ir_rules.xml`` usa
para sus modelos con ``company_id`` — regla GLOBAL con dominio verbatim
``[('company_id', 'in', company_ids)]``. Sembrado por **migración de
datos** (``0002_seed_subscription_security``), con las dos entradas de
``base_security``: viva para los tests, histórica para la migración.
"""
from django.db import DEFAULT_DB_ALIAS

from addons.base.models.ir_rule import IrRule as _IrRule
from addons.base.security.base_security import DOMAIN_MULTICOMPANY, _seed

_RULES = (
    ('Company Module Subscription multi-company',
     'sale_subscription.CompanyModuleSubscription'),
    ('Subscription Invoice multi-company',
     'sale_subscription.SubscriptionInvoice'),
)


def seed(using=DEFAULT_DB_ALIAS):
    """Sobre los modelos vivos — entrada del catálogo de tests."""
    return _seed(_IrRule, _RULES, using)


def seed_subscription_rules(apps, alias):
    """Sobre los modelos históricos — entrada de la migración.

    El modelo histórico es el de ``base``: ``ir.rule`` vive allí y esta
    migración sólo añade filas suyas.
    """
    return _seed(apps.get_model('base', 'IrRule'), _RULES, alias)
