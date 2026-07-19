"""Reubica ``NotificationPreference`` al addon ``mail`` — slice 3b de la
disolucion notifications->mail.

State-only: la tabla ``notifications_preference`` NO se toca (la conserva el
``CreateModel`` gemelo en ``mail.0011``). Aqui solo se retira
``NotificationPreference`` del **estado** del app ``notifications`` para que el
registro historico refleje que su hogar es ahora ``mail`` (mismo patron lossless
que el buzon ``Notification`` en el slice 3a). Los datos permanecen intactos.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0003_move_notification_to_mail'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='NotificationPreference'),
            ],
            database_operations=[],
        ),
    ]
