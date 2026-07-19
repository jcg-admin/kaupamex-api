"""Recibe el modelo ``NotificationPreference`` reubicado desde ``notifications``
— slice 3b de la disolucion notifications->mail.

State-only (gemelo de ``notifications.0004``): registra
``NotificationPreference`` en el **estado** del app ``mail`` sobre la tabla
existente ``notifications_preference`` (``db_table`` sin cambio) — no crea ni
copia datos. Depende de ``notifications.0004`` para que el borrado de estado en
aquel app preceda a esta alta, y de ``mail.0010`` para encadenar en el grafo de
``mail``.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mail', '0010_notification_inbox'),
        ('notifications', '0004_move_preference_to_mail'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='NotificationPreference',
                    fields=[
                        (
                            'id',
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name='ID',
                            ),
                        ),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        (
                            'type',
                            models.CharField(
                                choices=[
                                    ('ORDER_UPDATE', 'Actualizacion de orden'),
                                    ('RETURN_UPDATE', 'Actualizacion de devolucion'),
                                    ('PROMOTION', 'Promocion'),
                                    ('SYSTEM', 'Sistema'),
                                    ('SUPPORT_UPDATE', 'Actualizacion de soporte'),
                                ],
                                max_length=32,
                            ),
                        ),
                        ('enabled', models.BooleanField(default=True)),
                        (
                            'user',
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name='notification_preferences',
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={
                        'verbose_name': 'Preferencia de notificacion',
                        'verbose_name_plural': 'Preferencias de notificacion',
                        'db_table': 'notifications_preference',
                    },
                ),
                migrations.AddConstraint(
                    model_name='notificationpreference',
                    constraint=models.UniqueConstraint(
                        fields=('user', 'type'),
                        name='unique_notification_preference',
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]
