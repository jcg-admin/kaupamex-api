"""
UC-ORD-10: agregar payment_timeout_minutes a SiteSettings (H-ADM-004).
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('settings_app', '0005_timestampedmodel_settings'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='payment_timeout_minutes',
            field=models.PositiveIntegerField(
                default=30,
                help_text='Minutos hasta que una orden PENDING se cancela por timeout (UC-SYS-01).',
            ),
        ),
    ]
