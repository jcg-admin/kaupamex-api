"""Recibe el modelo ``ManualNotification`` reubicado desde ``notifications`` —
slice 3c de la disolucion notifications->mail.

State-only (gemelo de ``notifications.0005``): registra ``ManualNotification``
en el **estado** del app ``mail`` sobre la tabla existente
``notifications_manual`` (``db_table`` sin cambio) — no crea ni copia datos.
Depende de ``notifications.0005`` para que el borrado de estado en aquel app
preceda a esta alta, y de ``mail.0011`` para encadenar en el grafo de ``mail``.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mail', '0011_notificationpreference'),
        ('notifications', '0005_move_manual_to_mail'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='ManualNotification',
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
                            'recipient_type',
                            models.CharField(
                                choices=[
                                    ('USER', 'Usuario especifico'),
                                    ('PRODUCT_BUYERS', 'Compradores de producto'),
                                ],
                                max_length=24,
                            ),
                        ),
                        (
                            'recipient_identifier',
                            models.CharField(blank=True, default='', max_length=150),
                        ),
                        ('product_id', models.PositiveIntegerField(blank=True, null=True)),
                        ('subject', models.CharField(max_length=200)),
                        ('message', models.TextField()),
                        ('recipients_count', models.PositiveIntegerField(default=0)),
                        (
                            'status',
                            models.CharField(
                                choices=[
                                    ('PENDING', 'Pendiente'),
                                    ('SENT', 'Enviado'),
                                    ('FAILED', 'Fallido'),
                                ],
                                default='PENDING',
                                max_length=16,
                            ),
                        ),
                        (
                            'sender',
                            models.ForeignKey(
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name='manual_notifications_sent',
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={
                        'verbose_name': 'Notificacion manual',
                        'verbose_name_plural': 'Notificaciones manuales',
                        'db_table': 'notifications_manual',
                        'ordering': ['-created_at'],
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
