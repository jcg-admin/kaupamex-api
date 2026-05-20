"""
Migracion 0007: tabla users_deactivation_event (audit log de bajas).

Cierra GAP 10 del audit profundo de UC-AUTH-16: las transiciones
is_active=True -> False no dejaban rastro mas alla del estado actual
en users_user.deactivated_reason. Esta tabla append-only registra
cada evento.

No backfilla — solo se llena hacia adelante. Las transiciones
historicas no son recuperables.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0006_user_deactivation_reason'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserDeactivationEvent',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID',
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reason', models.CharField(
                    max_length=20,
                    choices=[
                        ('unverified',   'No verificada (email pendiente)'),
                        ('suspended',    'Suspendida por administrador'),
                        ('self_deleted', 'Dada de baja por el usuario'),
                    ],
                )),
                ('source', models.CharField(
                    max_length=20,
                    choices=[
                        ('register', 'Registro (cuenta nueva inactiva por verificar)'),
                        ('self',     'Auto-baja del propio usuario'),
                        ('admin',    'Suspension por administrador'),
                    ],
                )),
                ('note', models.CharField(blank=True, default='', max_length=255)),
                ('actor', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to='users.user',
                    help_text=(
                        'Quien disparo el evento. NULL para SOURCE_REGISTER o '
                        'SOURCE_SELF. Solo SOURCE_ADMIN registra al admin.'
                    ),
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='deactivation_events', to='users.user',
                )),
            ],
            options={
                'verbose_name':       'Evento de desactivacion',
                'verbose_name_plural': 'Eventos de desactivacion',
                'db_table':            'users_deactivation_event',
                'ordering':            ['-created_at'],
                'indexes': [
                    models.Index(
                        fields=['user', '-created_at'],
                        name='users_deact_user_id_4c2e_idx',
                    ),
                    models.Index(
                        fields=['source'],
                        name='users_deact_source_8a31_idx',
                    ),
                ],
            },
        ),
    ]
