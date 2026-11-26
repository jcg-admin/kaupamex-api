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
from orm import registry
from orm.environments import user_scope
from orm.utils import SUPERUSER_ID

#: El dominio multi-company de la fuente, verbatim.
DOMAIN_MULTICOMPANY = "[('company_id', 'in', company_ids)]"

#: (nombre de la regla, label Django del modelo). ``CompanySetting`` es el
#: único modelo de ``base`` con columna ``company_id`` scopeada por fila.
_RULES = (('Company Setting multi-company', 'base.CompanySetting'),)


#: Los permisos de un ``ir.rule`` sin declarar, como el ``default=True`` de
#: sus cuatro campos.
_RULE_PERMS = ('perm_read', 'perm_write', 'perm_create', 'perm_unlink')


def _seed(IrRule, rules, using):
    """El cuerpo, sobre el modelo que le den — idempotente por nombre.

    Una entrada ``(nombre, modelo)`` es la regla multicompañía global. Una
    entrada ``dict`` es un ``<record model="ir.rule">`` de la fuente con sus
    claves: ``name``, ``model``, ``domain_force``, ``groups`` (identificadores
    externos) y ``perm_*`` (``odoo19c: odoo/addons/base/security/
    base_security.xml``). Los grupos se resuelven con el ``IrModelData`` del
    mismo registro de apps que ``IrRule``, así que vale igual sobre los
    modelos vivos y sobre los históricos de una migración.

    Corre como superusuario, como la carga de ``base_security.xml`` en la
    fuente: ``IrRule`` valida su dominio evaluándolo, y un dominio con
    ``user.id`` necesita un usuario.
    """
    with user_scope(SUPERUSER_ID):
        _seed_rules(IrRule, rules, using)


def _seed_rules(IrRule, rules, using):
    """El recorrido de :func:`_seed`, dentro del alcance del superusuario."""
    for rule in rules:
        if not isinstance(rule, dict):
            name, model_name = rule
            rule = {'name': name, 'model': model_name,
                    'domain_force': DOMAIN_MULTICOMPANY}
        defaults = {
            'model_name': registry.identity_for_key(rule['model']),
            'domain_force': rule['domain_force'],
            **{perm: rule.get(perm, True) for perm in _RULE_PERMS},
        }
        record, _created = IrRule.objects.using(using).get_or_create(
            name=rule['name'], defaults=defaults)
        if rule.get('groups'):
            data = IrRule._meta.apps.get_model('base', 'IrModelData')
            group_ids = [
                data.objects.using(using).get(
                    module=xmlid.split('.', 1)[0],
                    name=xmlid.split('.', 1)[1]).res_id
                for xmlid in rule['groups']
            ]
            record.groups.set(group_ids)


def seed(using=DEFAULT_DB_ALIAS):
    """Sobre los modelos vivos — entrada del catálogo de tests."""
    return _seed(_IrRule, _RULES, using)


def seed_base_rules(apps, alias):
    """Sobre los modelos históricos — entrada de la migración."""
    return _seed(apps.get_model('base', 'IrRule'), _RULES, alias)
