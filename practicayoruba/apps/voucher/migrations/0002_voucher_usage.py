from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('voucher', '0001_squashed_0004_voucher_softdelete'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name='VoucherUsage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='voucher_usages',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('voucher', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='usages',
                    to='voucher.voucher',
                )),
            ],
            options={'db_table': 'voucher_usage'},
        ),
        migrations.AlterUniqueTogether(
            name='voucherusage',
            unique_together={('user', 'voucher')},
        ),
    ]
