"""``buyer_id``, el comprador que ``purchase`` cuelga en ``res.partner``
(``odoo19c: addons/purchase/models/res_partner.py:45``)."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0116_partner_commercial_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="respartner",
            name="buyer_id",
            field=models.ForeignKey(
                blank=True,
                db_column="buyer_id",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Buyer",
            ),
        ),
    ]
