"""Separa la versión instalada del manifiesto sin inventar historia."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('base', '0087_module_lifecycle_states')]
    operations = [
        migrations.AddField(
            model_name='irmodule',
            name='installed_version',
            field=models.CharField(
                blank=True, null=True, default=None, editable=False,
                help_text='Versión realmente instalada; NULL si no existe evidencia de instalación.',
            ),
        ),
    ]
