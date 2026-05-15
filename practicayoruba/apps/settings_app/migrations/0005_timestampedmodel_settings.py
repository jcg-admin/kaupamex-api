"""
Migración de infraestructura: herencia-modelos-django — apps.settings_app

H-INH-004: SiteSettings, PaymentGateway, ShippingMethod, StaticPage
solo tenían updated_at — se agrega created_at.
StaticPageVersion solo tenía created_at — se agrega updated_at.
"""
import django.utils.timezone
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('settings_app', '0004_sitesettings_contact_staticpage')]
    operations = [
        # SiteSettings: ADD created_at
        migrations.AddField(model_name='sitesettings', name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False),
        # PaymentGateway: ADD created_at
        migrations.AddField(model_name='paymentgateway', name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False),
        # ShippingMethod: ADD created_at
        migrations.AddField(model_name='shippingmethod', name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False),
        # StaticPage: ADD created_at
        migrations.AddField(model_name='staticpage', name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False),
        # StaticPageVersion: ADD updated_at
        migrations.AddField(model_name='staticpageversion', name='updated_at',
            field=models.DateTimeField(auto_now=True)),
    ]
