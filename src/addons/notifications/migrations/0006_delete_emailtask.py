"""Retira ``EmailTask`` (cola legacy) — slice 3d de la disolucion
notifications->mail.

A diferencia de 3a/3b/3c (moves state-only lossless), esto es un **retiro real**:
``EmailTask`` no se reubica, se elimina. Sus datos ya se copiaron a su hogar
Odoo ``mail.mail`` en la migracion de datos ``mail.0009`` (idempotente). Por eso
esta migracion depende de ``mail.0009`` — garantiza copy-before-drop: la tabla
``notifications_emailtask`` no se elimina antes de que sus filas esten en
``mail_mail``.

``DeleteModel`` (no ``SeparateDatabaseAndState``) genera el ``DROP TABLE``
``notifications_emailtask`` real.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0005_move_manual_to_mail'),
        ('mail', '0009_migrate_emailtask_data'),
    ]

    operations = [
        migrations.DeleteModel(name='EmailTask'),
    ]
