"""Reubica el modelo ``Notification`` (buzón) al addon ``mail`` — slice 3a de la
disolución notifications→mail.

State-only: la tabla ``notifications_notification`` NO se toca (la conserva el
``CreateModel`` gemelo en ``mail.0010``). Aquí sólo se retira ``Notification``
del **estado** del app ``notifications`` para que el registro histórico refleje
que su hogar es ahora ``mail`` (mismo patrón lossless que un move de modelo
entre apps). Los datos permanecen intactos.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0002_notification_mail_message'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='Notification'),
            ],
            database_operations=[],
        ),
    ]
