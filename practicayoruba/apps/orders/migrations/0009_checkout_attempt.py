from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0008_alter_orderaddress_created_at_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CheckoutAttempt",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="checkout_attempts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("idempotency_key", models.CharField(max_length=200)),
                ("response_json", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Intento de checkout",
                "db_table": "orders_checkout_attempt",
            },
        ),
        migrations.AddConstraint(
            model_name="checkoutattempt",
            constraint=models.UniqueConstraint(
                fields=["user", "idempotency_key"],
                name="unique_checkout_attempt",
            ),
        ),
    ]
