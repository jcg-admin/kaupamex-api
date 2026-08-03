"""Record rules de ``base`` — el rol de ``base_security.xml``.

En la referencia las record rules de un addon son DATO declarado en su
``security/`` (``odoo19c: odoo/addons/base/security/base_security.xml``;
en ``sale`` el archivo se llama ``security/ir_rules.xml``). Aquí el dato se
siembra idempotente con ``seed()``, registrado en ``tests/conftest.py``
(``_SEEDERS``) y disponible para provisioning.

La regla multi-company canónica es GLOBAL (sin grupos) y su dominio es
verbatim el de la fuente: ``[('company_id', 'in', company_ids)]``
(``odoo19c: addons/account/security/account_security.xml:131``, y el mismo
en ``sale/security/ir_rules.xml``). ``company_ids`` en el contexto de
evaluación son las compañías ACTIVADAS (canal del dato, DEC-AISL-04): con
cero activadas la regla da ``IN []`` → cero filas (fail-closed como dato).
"""
from addons.base.models.ir_rule import IrRule

#: El dominio multi-company de la fuente, verbatim.
DOMAIN_MULTICOMPANY = "[('company_id', 'in', company_ids)]"

#: (nombre de la regla, label Django del modelo). ``CompanySetting`` es el
#: único modelo de ``base`` con columna ``company_id`` scopeada por fila.
_RULES = (
    ('Company Setting multi-company', 'base.CompanySetting'),
)


def seed(using='default'):
    """Siembra las record rules de ``base`` — idempotente por nombre."""
    for name, model_name in _RULES:
        IrRule.objects.using(using).get_or_create(
            name=name,
            defaults={
                'model_name': model_name,
                'domain_force': DOMAIN_MULTICOMPANY,
            },
        )
