"""Los dos índices parciales de ``res.device.log`` (≙ ``odoo19c:
res_device.py:37-38``).

La referencia los declara como objetos de tabla en la cabecera del modelo;
aquí su hogar es ``Meta.indexes``, y por eso hacen falta estas dos
operaciones. Son **parciales** —``WHERE revoked IS NOT TRUE``—: cubren sólo
las sesiones vivas, que es lo único que la vista ``res.device`` consulta
(``0004_resdevice.py``).

Tarea #70.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0043_iractionsserver_parent"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="resdevicelog",
            index=models.Index(
                condition=models.Q(("revoked", True), _negated=True),
                fields=[
                    "user",
                    "session_identifier",
                    "platform",
                    "browser",
                    "last_activity",
                    "id",
                ],
                name="res_device_log_composite_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="resdevicelog",
            index=models.Index(
                condition=models.Q(("revoked", True), _negated=True),
                fields=["revoked"],
                name="res_device_log_revoked_idx",
            ),
        ),
    ]
