"""Reubica ``ManualNotification`` al addon ``mail`` — slice 3c de la disolucion
notifications->mail.

State-only: la tabla ``notifications_manual`` NO se toca (la conserva el
``CreateModel`` gemelo en ``mail.0012``). Aqui solo se retira
``ManualNotification`` del **estado** del app ``notifications`` (mismo patron
lossless que ``Notification`` en 3a y ``NotificationPreference`` en 3b). Los
datos permanecen intactos.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0004_move_preference_to_mail'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='ManualNotification'),
            ],
            database_operations=[],
        ),
    ]
