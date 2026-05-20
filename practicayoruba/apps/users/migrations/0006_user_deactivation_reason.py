"""
Migracion 0006: cierra GAP-3 del mapeo del flujo de auth
(db/scripts/mapping/flow-register-activate-checkout.sql B.6).

Agrega a ``users_user`` los campos:

- ``deactivated_reason`` CharField(max_length=20, choices, null) —
  causa por la que ``is_active=False`` (unverified, suspended,
  self_deleted). Permite distinguir cuentas reactivables por
  email de las suspendidas por admin.
- ``deactivated_at`` DateTimeField(null) — timestamp del cambio.

Backfill: las filas existentes con ``is_active=False`` se rellenan
con ``deactivated_reason='unverified'`` (asuncion mas comun:
cuentas que nunca activaron el email). Si en produccion hay
cuentas suspendidas por admin antes de esta migracion, requieren
fix manual via shell.

Refs: UC-AUTH-01 Alt-A (refinada), UC-AUTH-13, UC-AUTH-14, UC-AUTH-16.
"""
from django.db import migrations, models


def _backfill_unverified(apps, schema_editor):
    User = apps.get_model('users', 'User')
    User.objects.filter(
        is_active=False, deactivated_reason__isnull=True,
    ).update(deactivated_reason='unverified')


def _noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_address_deleted_at_address_is_deleted'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='deactivated_reason',
            field=models.CharField(
                blank=True, null=True, max_length=20,
                choices=[
                    ('unverified',   'No verificada (email pendiente)'),
                    ('suspended',    'Suspendida por administrador'),
                    ('self_deleted', 'Dada de baja por el usuario'),
                ],
                help_text=(
                    'Causa por la que is_active=False. NULL cuando la '
                    'cuenta esta activa. Distingue cuentas reactivables '
                    'por email (unverified, self_deleted) de las que '
                    'requieren UC-AUTH-14 (suspended). Ver UC-AUTH-01 '
                    'Alt-A.'
                ),
                verbose_name='Causa de inactividad',
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='deactivated_at',
            field=models.DateTimeField(
                blank=True, null=True,
                help_text='Timestamp del cambio is_active True -> False.',
                verbose_name='Fecha de desactivacion',
            ),
        ),
        migrations.RunPython(_backfill_unverified, _noop_reverse),
    ]
