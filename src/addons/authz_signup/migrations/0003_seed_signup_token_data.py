"""Siembra los config-params de validez del token, la URL de set-password y
las dos plantillas de correo (set-password / reset), ≙ los ``data/*.xml`` de
la referencia.

El spec vive en ``addons.authz_signup.data`` — fuente única para esta
migración y para ``seed()`` (H-API-22). ``0001`` ya sembró los flags de
política; ésta añade lo del signup-token core (2º pase).
"""
from django.db import migrations

from addons.authz_signup.data import SIGNUP_PARAMETERS, SIGNUP_TEMPLATES

# Sólo las claves nuevas de este pase (0001 ya sembró las dos primeras).
_NEW_PARAMS = {
    k: v for k, v in SIGNUP_PARAMETERS.items()
    if k not in ('authz.signup_allow_uninvited', 'authz.signup_reset_password')
}


def seed_token_data(apps, schema_editor):
    SystemParameter = apps.get_model('base', 'SystemParameter')
    MailTemplate = apps.get_model('mail', 'MailTemplate')
    db = schema_editor.connection.alias
    for key, value in _NEW_PARAMS.items():
        if not SystemParameter.objects.using(db).filter(key=key).exists():
            SystemParameter.objects.using(db).create(key=key, value=value)
    for spec in SIGNUP_TEMPLATES:
        if not MailTemplate.objects.using(db).filter(
                name=spec['name']).exists():
            MailTemplate.objects.using(db).create(**spec)


def unseed_token_data(apps, schema_editor):
    SystemParameter = apps.get_model('base', 'SystemParameter')
    MailTemplate = apps.get_model('mail', 'MailTemplate')
    db = schema_editor.connection.alias
    SystemParameter.objects.using(db).filter(
        key__in=list(_NEW_PARAMS)).delete()
    MailTemplate.objects.using(db).filter(
        name__in=[s['name'] for s in SIGNUP_TEMPLATES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('authz_signup', '0002_signup_request'),
        ('base', '0001_initial'),
        ('mail', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_token_data, unseed_token_data),
    ]
