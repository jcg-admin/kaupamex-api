"""
Migración de infraestructura: herencia-modelos-django — apps.voucher

Voucher: refactor puro (ya tenía created_at + updated_at) — sin cambios en BD.
VoucherChangeLog: RENAME changed_at → created_at + ADD updated_at.
  H-INH-003: VoucherChangeLog usaba changed_at en lugar del nombre estándar.
"""
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('voucher', '0001_initial')]
    operations = [
        # VoucherChangeLog: RENAME changed_at → created_at
        migrations.RenameField(
            model_name='voucherchangelog',
            old_name='changed_at',
            new_name='created_at',
        ),
        migrations.AlterModelOptions(
            name='voucherchangelog',
            options={'ordering': ['-created_at'], 'verbose_name': 'Cambio de voucher'},
        ),
        # ADD updated_at
        migrations.AddField(model_name='voucherchangelog', name='updated_at',
            field=models.DateTimeField(auto_now=True)),
    ]
