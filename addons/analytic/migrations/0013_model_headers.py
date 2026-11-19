# ≙ log-access de account.analytic.line, que ahora declara _name
# (odoo19c: odoo/orm/models.py:283-296, LOG_ACCESS_COLUMNS); misma forma
# que account/0038_model_headers.

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("analytic", "0012_restrict_ondelete_block_f"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="accountanalyticline",
            name="create_date",
            field=models.DateTimeField(
                auto_now_add=True, default=django.utils.timezone.now
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="accountanalyticline",
            name="create_uid",
            field=models.ForeignKey(
                blank=True,
                db_column="create_uid",
                db_index=False,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="accountanalyticline",
            name="write_date",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name="accountanalyticline",
            name="write_uid",
            field=models.ForeignKey(
                blank=True,
                db_column="write_uid",
                db_index=False,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
