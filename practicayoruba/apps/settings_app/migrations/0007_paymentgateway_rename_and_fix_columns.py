"""
Corrección de drift entre el modelo PaymentGateway y la migración 0003.

La migración 0003 creó la tabla con los nombres originales del Sprint 8:
  - provider (CharField) → gateway (CharField)
  - credentials_enc (TextField) → credentials (BinaryField)
  - sin campo name

El modelo fue actualizado en Sprint 15/16 para coincidir con el
esquema de gateways múltiples (MP + PayPal), pero la migración
que capturara esos cambios nunca fue creada.

Este migration corrige el drift:
  1. Renombra provider → gateway
  2. Agrega name (CharField)
  3. Renombra credentials_enc → credentials
  4. Altera credentials de TextField a BinaryField (longblob en MySQL)
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('settings_app', '0006_sitesettings_payment_timeout'),
    ]

    operations = [
        # 1. Renombrar provider → gateway
        migrations.RenameField(
            model_name='paymentgateway',
            old_name='provider',
            new_name='gateway',
        ),
        # 2. Agregar campo name (faltaba en 0003)
        migrations.AddField(
            model_name='paymentgateway',
            name='name',
            field=models.CharField(max_length=50, default=''),
            preserve_default=False,
        ),
        # 3. Renombrar credentials_enc → credentials
        migrations.RenameField(
            model_name='paymentgateway',
            old_name='credentials_enc',
            new_name='credentials',
        ),
        # 4. Alterar credentials de TextField a BinaryField
        migrations.AlterField(
            model_name='paymentgateway',
            name='credentials',
            field=models.BinaryField(
                help_text='Credenciales cifradas con Fernet (apps.settings_app.models._fernet_key)',
            ),
        ),
        # 5. Eliminar db_index de is_active (el modelo actual no lo tiene)
        migrations.AlterField(
            model_name='paymentgateway',
            name='is_active',
            field=models.BooleanField(default=False),
        ),
    ]
