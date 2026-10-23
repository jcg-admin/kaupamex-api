from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('base', '0086_enable_profiling_wizard_gana_sus_dos_campos')]
    operations = [
        migrations.AlterField(
            model_name='irmodule',
            name='state',
            field=models.CharField(choices=[('uninstallable', 'No instalable'), ('uninstalled', 'No instalado'), ('installed', 'Instalado'), ('to install', 'Pendiente de instalación'), ('to upgrade', 'Pendiente de actualización'), ('to remove', 'Pendiente de desinstalación')], db_index=True, default='uninstalled', help_text='Estado de instalación persistido en la base del módulo.', max_length=16),
        ),
    ]
