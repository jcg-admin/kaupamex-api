import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailTask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('to', models.TextField(help_text='Email destino. Multiples separados por coma.')),
                ('subject', models.CharField(max_length=255)),
                ('body', models.TextField()),
                ('from_email', models.CharField(blank=True, default='', max_length=254)),
                ('scheduled_at', models.DateTimeField(auto_now_add=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pendiente'),
                        ('sent', 'Enviado'),
                        ('failed', 'Fallido (max reintentos)'),
                        ('retrying', 'Reintentando'),
                    ],
                    default='pending',
                    max_length=10,
                )),
                ('attempts', models.PositiveSmallIntegerField(default=0)),
                ('last_error', models.TextField(blank=True)),
                ('max_attempts', models.PositiveSmallIntegerField(default=3)),
            ],
            options={
                'verbose_name': 'Tarea de email',
                'verbose_name_plural': 'Tareas de email',
                'db_table': 'notifications_emailtask',
                'ordering': ['scheduled_at'],
                'indexes': [
                    models.Index(fields=['status', 'scheduled_at'], name='notifications_emailtask_status_idx'),
                ],
            },
        ),
    ]
