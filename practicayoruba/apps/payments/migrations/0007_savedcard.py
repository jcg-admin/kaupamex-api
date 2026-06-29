"""Migration: add SavedCard model for customer card management with email verification."""
import apps.payments.models
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0006_alter_webhookevent_unique_together_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SavedCard',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('mp_card_id', models.CharField(db_index=True, max_length=100)),
                ('mp_customer_id', models.CharField(db_index=True, max_length=100)),
                ('last_four_digits', models.CharField(max_length=4)),
                ('first_six_digits', models.CharField(blank=True, default='', max_length=6)),
                ('expiration_month', models.PositiveSmallIntegerField()),
                ('expiration_year', models.PositiveSmallIntegerField()),
                ('payment_method_id', models.CharField(blank=True, default='', max_length=50)),
                ('cardholder_name', models.CharField(blank=True, default='', max_length=200)),
                ('status', models.CharField(
                    choices=[
                        ('pending_verification', 'Pendiente de verificación'),
                        ('active', 'Activa'),
                        ('deleted', 'Eliminada'),
                    ],
                    db_index=True,
                    default='pending_verification',
                    max_length=30,
                )),
                ('verification_token', models.CharField(
                    default=apps.payments.models._make_verification_token,
                    help_text='Token de un solo uso enviado por email para activar la tarjeta.',
                    max_length=100,
                    unique=True,
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='saved_cards',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Tarjeta guardada',
                'db_table': 'payments_saved_card',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='savedcard',
            constraint=models.UniqueConstraint(
                fields=['user', 'mp_card_id'],
                name='unique_user_mp_card',
            ),
        ),
    ]
