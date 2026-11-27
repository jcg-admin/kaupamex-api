"""Retira la tabla-liga ``BaseAutomationAction``.

Sustituía el ``base_automation_id`` de la referencia
(``odoo19c: addons/base_automation/models/ir_actions_server.py:17``); su
contenido ya está en esa columna (``base/0150``).
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('base_automation', '0009_rewrite_model_identities'),
        ('base', '0150_ir_actions_server_base_automation_id'),
    ]

    operations = [
        migrations.DeleteModel(
            name='BaseAutomationAction',
        ),
    ]
