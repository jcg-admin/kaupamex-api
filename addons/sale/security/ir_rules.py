"""Record rules de ``sale`` — el rol de ``sale/security/ir_rules.xml``.

Fiel a la fuente (``odoo19c: addons/sale/security/ir_rules.xml:6-8``):
regla GLOBAL *"Sales Order multi-company"* con dominio verbatim
``[('company_id', 'in', company_ids)]``. Sembrada idempotente vía
``seed()`` (registrado en ``tests/conftest.py`` ``_SEEDERS``).
"""
from addons.base.models.ir_rule import IrRule
from addons.base.security.base_security import DOMAIN_MULTICOMPANY

_RULES = (
    ('Sales Order multi-company', 'sale.SaleOrder'),
)


def seed(using='default'):
    """Siembra las record rules de ``sale`` — idempotente por nombre."""
    for name, model_name in _RULES:
        IrRule.objects.using(using).get_or_create(
            name=name,
            defaults={
                'model_name': model_name,
                'domain_force': DOMAIN_MULTICOMPANY,
            },
        )
