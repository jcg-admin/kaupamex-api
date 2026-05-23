from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0010_alter_order_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='ShippingZone',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('zip_code_prefix', models.CharField(db_index=True, max_length=5)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'db_table': 'orders_shipping_zone',
            },
        ),
    ]
