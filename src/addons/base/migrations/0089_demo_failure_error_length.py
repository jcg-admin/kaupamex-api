"""Preserve complete demo errors without allowing a lossy schema reversal."""
from django.db import migrations, models
from django.db.migrations.exceptions import IrreversibleError
from django.db.models.functions import Length


def guard_short_error_column(apps, schema_editor):
    failure = apps.get_model('base', 'IrDemoFailure')
    if failure.objects.using(schema_editor.connection.alias).annotate(
            error_length=Length('error')).filter(error_length__gt=255).exists():
        raise IrreversibleError(
            'Cannot restore varchar(255) while complete demo errors exceed 255 characters')


class Migration(migrations.Migration):
    dependencies = [('base', '0088_module_installed_version')]
    operations = [
        migrations.AlterField(
            model_name='irdemofailure', name='error',
            field=models.CharField(blank=True, default='', verbose_name='Error'),
        ),
        migrations.RunPython(migrations.RunPython.noop, guard_short_error_column),
    ]
