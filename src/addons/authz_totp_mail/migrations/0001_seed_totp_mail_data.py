"""Siembra plantillas de correo + config-params del 2FA por correo
(≙ ``data/mail_template_data.xml`` ``noupdate`` de la referencia).

El spec vive en ``addons.authz_totp_mail.data`` — fuente única para esta
migración y para ``seed()`` (H-API-22). Este addon no declara modelos
propios (la referencia tampoco: solo ``_inherit``).
"""
from django.db import migrations

from addons.authz_totp_mail.data import (
    TOTP_MAIL_PARAMETERS,
    TOTP_MAIL_TEMPLATES,
)


def seed_totp_mail_data(apps, schema_editor):
    SystemParameter = apps.get_model('base', 'SystemParameter')
    MailTemplate = apps.get_model('mail', 'MailTemplate')
    db = schema_editor.connection.alias
    for key, value in TOTP_MAIL_PARAMETERS.items():
        if not SystemParameter.objects.using(db).filter(key=key).exists():
            SystemParameter.objects.using(db).create(key=key, value=value)
    for spec in TOTP_MAIL_TEMPLATES:
        if not MailTemplate.objects.using(db).filter(
                name=spec['name']).exists():
            MailTemplate.objects.using(db).create(**spec)


def unseed_totp_mail_data(apps, schema_editor):
    SystemParameter = apps.get_model('base', 'SystemParameter')
    MailTemplate = apps.get_model('mail', 'MailTemplate')
    db = schema_editor.connection.alias
    SystemParameter.objects.using(db).filter(
        key__in=list(TOTP_MAIL_PARAMETERS)).delete()
    MailTemplate.objects.using(db).filter(
        name__in=[s['name'] for s in TOTP_MAIL_TEMPLATES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0001_initial'),
        ('mail', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_totp_mail_data, unseed_totp_mail_data),
    ]
