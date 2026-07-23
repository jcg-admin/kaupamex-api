# DEC-08 slice 2 (adoptar-arquitectura-server-service-odoo): elimina AppLog
# de core/ una vez que sus filas ya fueron copiadas de forma no destructiva a
# base.IrLogging (ver addons/base/migrations/0007_copiar_applog_a_irlogging.py,
# de la cual esta migración depende explícitamente para garantizar el orden).
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
        ("base", "0007_copiar_applog_a_irlogging"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="applog",
            name="applog_created_idx",
        ),
        migrations.DeleteModel(
            name="AppLog",
        ),
    ]
