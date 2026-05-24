from django.db import migrations, models


class Migration(migrations.Migration):
    """
    T-119 merge-safe: ShippingZone may already exist from 0009_shipping_zone
    (Branch B). Use SeparateDatabaseAndState so the state is updated without
    failing when the table is already present.
    """

    dependencies = [
        ('orders', '0010_alter_order_status'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        CREATE TABLE IF NOT EXISTS `orders_shipping_zone` (
                            `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
                            `name` varchar(100) NOT NULL,
                            `zip_code_prefix` varchar(5) NOT NULL,
                            `is_active` bool NOT NULL
                        )
                    """,
                    reverse_sql="DROP TABLE IF EXISTS `orders_shipping_zone`",
                ),
                migrations.RunSQL(
                    sql="CREATE INDEX IF NOT EXISTS `orders_shipping_zone_zip_code_prefix_idx` ON `orders_shipping_zone` (`zip_code_prefix`)",
                    reverse_sql="DROP INDEX IF EXISTS `orders_shipping_zone_zip_code_prefix_idx` ON `orders_shipping_zone`",
                ),
            ],
            state_operations=[
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
            ],
        ),
    ]
