"""Siembra las record rules de ``sale_subscription``.

``sale_subscription`` es Enterprise en la referencia (OEEL-1 →
reimplementación nativa, DEC-KX-03), así que la regla no se copia de un XML:
es el **mismo patrón canónico** que ``sale/security/ir_rules.xml`` aplica a
sus modelos con ``company_id``. Hasta este pase la siembra existía **sólo** en
``tests/conftest.py``, con la misma consecuencia silenciosa que en ``sale``:
sin la regla, la suscripción y su factura de una empresa son visibles desde
otra.

La definición vive en ``addons/sale_subscription/security/ir_rules.py``.
"""
from django.db import migrations

from addons.sale_subscription.security.ir_rules import seed_subscription_rules


def seed(apps, schema_editor):
    return seed_subscription_rules(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ('sale_subscription', '0001_initial'),
        ('base', '0059_seed_base_security'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
