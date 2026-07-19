"""Recibe el modelo ``Notification`` (buzón del comprador) reubicado desde
``notifications`` — slice 3a de la disolución notifications→mail.

State-only (gemelo de ``notifications.0003``): registra ``Notification`` en el
**estado** del app ``mail`` sobre la tabla existente ``notifications_notification``
(``db_table`` sin cambio) — no crea ni copia datos. Depende de
``notifications.0003`` para que el borrado de estado en aquel app preceda a esta
alta, y de ``mail.0009`` para encadenar en el grafo de ``mail``.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mail', '0009_migrate_emailtask_data'),
        ('notifications', '0003_move_notification_to_mail'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='Notification',
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
                                default='SYSTEM',
                                max_length=32,
                            ),
                        ),
                        ('subject', models.CharField(max_length=200)),
                        ('body', models.TextField()),
                        ('read', models.BooleanField(default=False)),
                        (
                            'mail_message',
                            models.ForeignKey(
                                blank=True,
                                help_text='Mensaje de chatter que origino esta notificacion (familia mail).',
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name='inbox_notifications',
                                to='mail.mailmessage',
                            ),
                        ),
                        (
                            'user',
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name='notifications',
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={
                        'verbose_name': 'Notificacion',
                        'verbose_name_plural': 'Notificaciones',
                        'db_table': 'notifications_notification',
                        'ordering': ['-created_at'],
                        'indexes': [
                            models.Index(fields=['user', 'read'], name='notificatio_user_id_878a13_idx'),
                            models.Index(fields=['user', '-created_at'], name='notificatio_user_id_05b4bc_idx'),
                        ],
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
