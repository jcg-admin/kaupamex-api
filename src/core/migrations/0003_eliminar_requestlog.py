# DEC-08/DEC-12 slice 3 (adoptar-arquitectura-server-service-odoo): elimina
# RequestLog de core/ una vez que sus filas ya fueron copiadas de forma no
# destructiva a observability.RequestLog (ver
# addons/observability/migrations/0002_copiar_requestlog_a_observability.py,
# de la cual esta migración depende explícitamente para garantizar el orden).
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_eliminar_applog"),
        ("observability", "0002_copiar_requestlog_a_observability"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="requestlog",
            name="requestlog_created_idx",
        ),
        migrations.DeleteModel(
            name="RequestLog",
        ),
    ]
