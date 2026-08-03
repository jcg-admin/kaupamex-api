"""Siembra los proveedores OAuth2 y el config-param del transporte del token
(≙ ``data/auth_oauth_data.xml`` ``noupdate="1"`` de la referencia — ver el
porqué de cada omisión en ``addons.authz_oauth.data``).

El spec vive en ``addons.authz_oauth.data`` — fuente única para esta
migración y para la re-aplicación sobre el modelo vivo (``seed()``,
H-API-22).
"""
from django.db import migrations

from addons.authz_oauth.data import OAUTH_PARAMETERS, OAUTH_PROVIDERS


def seed_oauth_data(apps, schema_editor):
    SystemParameter = apps.get_model('base', 'SystemParameter')
    OauthProvider = apps.get_model('authz_oauth', 'OauthProvider')
    db = schema_editor.connection.alias
    for key, value in OAUTH_PARAMETERS.items():
        if not SystemParameter.objects.using(db).filter(key=key).exists():
            SystemParameter.objects.using(db).create(key=key, value=value)
    for spec in OAUTH_PROVIDERS:
        if not OauthProvider.objects.using(db).filter(
                name=spec['name']).exists():
            OauthProvider.objects.using(db).create(**spec)


def unseed_oauth_data(apps, schema_editor):
    SystemParameter = apps.get_model('base', 'SystemParameter')
    OauthProvider = apps.get_model('authz_oauth', 'OauthProvider')
    db = schema_editor.connection.alias
    SystemParameter.objects.using(db).filter(
        key__in=list(OAUTH_PARAMETERS)).delete()
    OauthProvider.objects.using(db).filter(
        name__in=[s['name'] for s in OAUTH_PROVIDERS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('authz_oauth', '0001_initial'),
        ('base', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_oauth_data, unseed_oauth_data),
    ]
