"""Siembra las record rules de ``sale``.

≙ ``odoo19c: addons/sale/security/ir_rules.xml:6-8``, que la referencia carga
al instalar el módulo. Hasta este pase la siembra existía **sólo** en
``tests/conftest.py``, así que una base de producción no tenía la regla
multi-empresa de ``sale.order`` y **cada empresa veía los pedidos de las
demás** — el aislamiento por fila de este árbol es dato, no código
(DEC-AISL-04 §4).

La definición vive en ``addons/sale/security/ir_rules.py`` y esta migración
sólo la invoca sobre los modelos históricos; ver el docstring de
``base/0059_seed_base_security`` para por qué el dato no vive aquí.
"""
from django.db import migrations

from addons.sale.security.ir_rules import seed_sale_rules


def seed(apps, schema_editor):
    return seed_sale_rules(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ('sale', '0006_saleorderline_has_displayed_warning_upsell'),
        # La fila es de ``ir.rule``, que ``base`` declara: sin esta arista el
        # orden entre las dos apps no está garantizado y el modelo histórico
        # podría no existir todavía.
        ('base', '0059_seed_base_security'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
