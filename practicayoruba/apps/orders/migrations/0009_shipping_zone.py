from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0008_alter_orderaddress_created_at_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShippingZone",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("zip_code_prefix", models.CharField(db_index=True, max_length=5)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "db_table": "orders_shipping_zone",
            },
        ),
    ]
