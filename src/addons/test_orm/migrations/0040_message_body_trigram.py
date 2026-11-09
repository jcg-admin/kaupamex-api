"""``test_orm.message.body`` con ``index='trigram'`` — ≙
``odoo19c: odoo/addons/test_orm/models/test_orm.py:143``.

El índice ``gin`` con ``gin_trgm_ops`` exige ``pg_trgm``. La crea también
``website/0005``, pero ninguna dependencia ordena esa migración antes que ésta
en una base nueva; ``TrigramExtension`` usa ``CREATE EXTENSION IF NOT EXISTS``.
"""
import django.contrib.postgres.indexes
from django.contrib.postgres.operations import TrigramExtension
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("test_orm", "0039_field_index_btree"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        TrigramExtension(),
        migrations.AddField(
            model_name="testormmessage",
            name="body",
            field=models.TextField(null=True),
        ),
        migrations.AddIndex(
            model_name="testormmessage",
            index=django.contrib.postgres.indexes.GinIndex(
                django.contrib.postgres.indexes.OpClass(
                    models.F("body"), name="gin_trgm_ops"
                ),
                name="test_orm_message__body_index",
            ),
        ),
    ]
