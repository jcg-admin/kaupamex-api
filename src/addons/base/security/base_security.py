"""Record rules de ``base`` — el rol de ``base_security.xml``.

En la referencia las record rules de un addon son DATO declarado en su
``security/`` (``odoo19c: odoo/addons/base/security/base_security.xml``;
en ``sale`` el archivo se llama ``security/ir_rules.xml``). Allá lo carga el
instalador del módulo; aquí lo siembra una **migración de datos**, que es el
camino que este árbol ya usa para lo que la referencia instala con el módulo
(``0017`` países, ``0026`` idiomas, ``0027`` grupos).

**Dos entradas, un solo cuerpo**, como ``res_groups_data``: :func:`seed` sobre
los modelos vivos —la que ``tests/conftest.py`` re-aplica tras un ``flush``
transaccional (:ref:`h-api-337`)— y :func:`seed_base_rules` sobre los
históricos, que es la de la migración. Ejecutar comportamiento de la app viva
desde una migración la ata a un estado del código que cambia bajo sus pies.

La regla multi-company canónica es GLOBAL (sin grupos) y su dominio es
verbatim el de la fuente: ``[('company_id', 'in', company_ids)]``
(``odoo19c: addons/account/security/account_security.xml:131``, y el mismo
en ``sale/security/ir_rules.xml``). ``company_ids`` en el contexto de
evaluación son las compañías ACTIVADAS (canal del dato, DEC-AISL-04): con
cero activadas la regla da ``IN []`` → cero filas (fail-closed como dato).
"""
from django.db import DEFAULT_DB_ALIAS

from addons.base.models.ir_rule import IrRule as _IrRule

#: El dominio multi-company de la fuente, verbatim.
DOMAIN_MULTICOMPANY = "[('company_id', 'in', company_ids)]"

#: (nombre de la regla, label Django del modelo). ``CompanySetting`` es el
#: único modelo de ``base`` con columna ``company_id`` scopeada por fila.
_RULES = (
    ('Company Setting multi-company', 'base.CompanySetting'),
)


def _seed(IrRule, rules, using):
    """El cuerpo, sobre el modelo que le den — idempotente por nombre."""
    for name, model_name in rules:
        IrRule.objects.using(using).get_or_create(
            name=name,
            defaults={
                'model_name': model_name,
                'domain_force': DOMAIN_MULTICOMPANY,
            },
        )


def seed(using=DEFAULT_DB_ALIAS):
    """Sobre los modelos vivos — entrada del catálogo de tests."""
    return _seed(_IrRule, _RULES, using)


def seed_base_rules(apps, alias):
    """Sobre los modelos históricos — entrada de la migración."""
    return _seed(apps.get_model('base', 'IrRule'), _RULES, alias)
