"""Record rules de ``sale_subscription`` — reglas multi-company.

``sale_subscription`` en la referencia es Enterprise (OEEL-1 →
reimplementación nativa, DEC-KX-03), así que aquí no se copia su XML: se
declara el MISMO patrón canónico que ``sale/security/ir_rules.xml`` usa
para sus modelos con ``company_id`` — regla GLOBAL con dominio verbatim
``[('company_id', 'in', company_ids)]``. Sembrado idempotente vía
``seed()`` (registrado en ``tests/conftest.py`` ``_SEEDERS``).
"""
from addons.base.models.ir_rule import IrRule
from addons.base.security.base_security import DOMAIN_MULTICOMPANY

_RULES = (
    ('Company Module Subscription multi-company',
     'sale_subscription.CompanyModuleSubscription'),
    ('Subscription Invoice multi-company',
     'sale_subscription.SubscriptionInvoice'),
)


def seed(using='default'):
    """Siembra las record rules del addon — idempotente por nombre."""
    for name, model_name in _RULES:
        IrRule.objects.using(using).get_or_create(
            name=name,
            defaults={
                'model_name': model_name,
                'domain_force': DOMAIN_MULTICOMPANY,
            },
        )
