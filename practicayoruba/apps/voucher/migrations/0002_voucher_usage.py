# T-119 merge-safe: VoucherUsage DB table is created by 0005_voucherusage (Branch B).
# State operations declare the canonical model (matching 0005) so the final
# accumulated state always matches the DB schema.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('voucher', '0001_squashed_0004_voucher_softdelete'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                # No-op: 0005_voucherusage handles the actual table creation.
                migrations.RunSQL(sql="SELECT 1", reverse_sql="SELECT 1"),
            ],
            state_operations=[
                # Declare the canonical model so accumulated state matches DB.
                migrations.CreateModel(
                    name='VoucherUsage',
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
                        ('used_at', models.DateTimeField(auto_now_add=True)),
                        (
                            'user',
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name='voucher_usages',
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                        (
                            'voucher',
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name='usages',
                                to='voucher.voucher',
                            ),
                        ),
                    ],
                    options={
                        'verbose_name': 'Voucher usage',
                        'db_table': 'voucher_usage',
                        'unique_together': {('user', 'voucher')},
                    },
                ),
            ],
        ),
    ]
