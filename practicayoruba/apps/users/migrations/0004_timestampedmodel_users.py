"""
Migración de infraestructura: herencia-modelos-django — apps.users

Address: ADD created_at + updated_at (sin timestamps previos).
PasswordResetToken: ADD updated_at (ya tenía created_at).
EmailVerificationToken: ADD updated_at (ya tenía created_at).
User: excluido (DEC-005 — hereda de AbstractUser).
"""
import django.utils.timezone
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('users', '0003_emailverificationtoken_passwordresettoken')]
    operations = [
        # Address: ADD ambos campos
        migrations.AddField(model_name='address', name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False),
        migrations.AddField(model_name='address', name='updated_at',
            field=models.DateTimeField(auto_now=True)),
        # Tokens: ADD updated_at
        migrations.AddField(model_name='passwordresettoken', name='updated_at',
            field=models.DateTimeField(auto_now=True)),
        migrations.AddField(model_name='emailverificationtoken', name='updated_at',
            field=models.DateTimeField(auto_now=True)),
    ]
