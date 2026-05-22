from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0001_squashed_0002_sync_model_drift"),
    ]

    operations = [
        migrations.CreateModel(
            name="WebhookEvent",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ("gateway", models.CharField(
                    choices=[("MERCADOPAGO", "MercadoPago"), ("PAYPAL", "PayPal")],
                    db_index=True,
                    max_length=20,
                )),
                ("event_id", models.CharField(max_length=200)),
                ("transmission_id", models.CharField(blank=True, default="", max_length=200)),
                ("raw_body", models.TextField()),
                ("processed_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Evento de webhook",
                "db_table": "payments_webhook_event",
            },
        ),
        migrations.AddConstraint(
            model_name="webhookevent",
            constraint=models.UniqueConstraint(
                fields=["gateway", "event_id", "transmission_id"],
                name="unique_webhook_event",
            ),
        ),
    ]
