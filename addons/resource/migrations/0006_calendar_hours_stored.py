"""``hours_per_day`` y ``hours_per_week`` como calculados almacenados.

≙ ``odoo19c: addons/resource/models/resource_calendar.py:102-106``. Las
columnas nacen en cero y ``ComputeStoredFields`` las calcula sobre las filas
existentes (``odoo19c: odoo/orm/models.py:3220-3238``); el cómputo sólo lee
los tramos del propio calendario, de esta misma app.
"""
import orm.fields_numeric
from django.db import migrations, models

from orm.migration_operations import ComputeStoredFields


class Migration(migrations.Migration):

    dependencies = [
        ("resource", "0005_log_access_user_column_names"),
    ]

    operations = [
        migrations.AddField(
            model_name="resourcecalendar",
            name="hours_per_day",
            field=orm.fields_numeric.NumericFloat(
                default=0.0, verbose_name="Average Hour per Day"
            ),
        ),
        migrations.AddField(
            model_name="resourcecalendar",
            name="hours_per_week",
            field=models.FloatField(default=0.0),
        ),
        ComputeStoredFields('resource', 'resourcecalendar',
                            ['hours_per_day', 'hours_per_week']),
    ]
