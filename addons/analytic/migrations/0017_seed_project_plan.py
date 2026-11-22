"""Siembra el plan «Project» y ``analytic.project_plan``.

≙ ``odoo19c: addons/analytic/data/analytic_data.xml:13-17``: el parámetro
nombra el plan cuyas cuentas viven en ``account_id``; ``_get_all_plans``
levanta sin él (``designs/analytic-plan-methods.md``). Como la fuente
(``noupdate``), no se toca un parámetro ya fijado. La siembra vive en
``addons.analytic.data``, que el catálogo de ``tests/conftest.py`` también
llama.
"""
from django.db import migrations

from addons.analytic.data import seed_project_plan


def seed(apps, schema_editor):
    seed_project_plan(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ('analytic', '0016_plan_parent_id_complete_name'),
        ('base', '0126_fill_cron_action_code'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
