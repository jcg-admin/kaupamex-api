"""Record rules de ``sale`` — el rol de ``sale/security/ir_rules.xml``.

Fiel a la fuente (``odoo19c: addons/sale/security/ir_rules.xml:6-8``):
regla GLOBAL *"Sales Order multi-company"* con dominio verbatim
``[('company_id', 'in', company_ids)]``. Sembrada por **migración de
datos** (``0007_seed_sale_security``), con las dos entradas de
``base_security``: viva para los tests, histórica para la migración.
"""
from django.db import DEFAULT_DB_ALIAS

from addons.base.models.ir_rule import IrRule as _IrRule
from addons.base.security.base_security import DOMAIN_MULTICOMPANY, _seed

_RULES = (
    ('Sales Order multi-company', 'sale.SaleOrder'),
)


def seed(using=DEFAULT_DB_ALIAS):
    """Sobre los modelos vivos — entrada del catálogo de tests."""
    return _seed(_IrRule, _RULES, using)


def seed_sale_rules(apps, alias):
    """Sobre los modelos históricos — entrada de la migración.

    El modelo histórico es el de ``base``: ``ir.rule`` vive allí y esta
    migración sólo añade filas suyas.
    """
    return _seed(apps.get_model('base', 'IrRule'), _RULES, alias)
